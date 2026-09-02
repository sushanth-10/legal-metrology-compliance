from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import dataclasses
import time
import uuid
from functools import lru_cache
from threading import Lock
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
from PIL import Image

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from compliance_engine import (
    ComplianceEngine,
    ExtractedPackage,
    FieldObservation,
    ObservationState,
    PackageContext,
    QuantityBasis,
)
from database import STORAGE_DIR, connect, create_token, create_user, init_db, iso_datetime, json_value, new_id, user_from_token, verify_password
from pdf_reports import create_pdf

app = FastAPI(title="NIRIKSHA Package Compliance API")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

logger = logging.getLogger("niriksha")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "").strip()
ORGANIZATION_OTP_REQUIRED = (os.getenv("ORGANIZATION_OTP_REQUIRED", "false").strip().lower() in {"1", "true", "yes", "on"})
ORGANIZATION_OTP_VERIFY_URL = (os.getenv("ORGANIZATION_OTP_VERIFY_URL") or "").strip()
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_SECRET_KEY = (os.getenv("SUPABASE_SECRET_KEY") or "").strip()
SUPABASE_STORAGE_BUCKET = (os.getenv("SUPABASE_STORAGE_BUCKET") or "scan-images").strip() or "scan-images"
SUPABASE_STORAGE_SIGNED_URL_TTL = max(60, int(os.getenv("SUPABASE_STORAGE_SIGNED_URL_TTL", "3600")))
MAX_UPLOAD_BYTES = max(1, int(os.getenv("MAX_UPLOAD_BYTES", "10485760")))
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
GEMINI_MAX_IMAGE_DIMENSION = 3000
GEMINI_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_SUPABASE_BUCKET_READY = False
_SUPABASE_BUCKET_LOCK = Lock()


def _slugify_storage_object_name(filename: str) -> str:
    name = Path(filename or "upload").name
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    safe_stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", stem).strip("-._") or "upload"
    safe_suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,8}", suffix) else ".jpg"
    return f"{safe_stem}{safe_suffix}"


def _build_supabase_storage_key(user_id: str, scan_id: str, filename: str, unique_suffix: str | None = None) -> str:
    generated_name = _slugify_storage_object_name(filename)
    if unique_suffix:
        generated_name = f"{unique_suffix}-{generated_name}"
    return f"{SUPABASE_STORAGE_BUCKET}/{user_id}/{scan_id}/{generated_name}"


@lru_cache(maxsize=1)
def _supabase_storage_client() -> Any | None:
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        logger.warning("Supabase Storage is not configured: missing SUPABASE_URL or SUPABASE_SECRET_KEY in the backend .env file.")
        return None
    try:
        from supabase import create_client
    except ImportError:
        logger.warning("Supabase Python client is not installed. Install requirements.txt to enable Storage uploads.")
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
    except Exception as error:
        logger.warning("Supabase client initialization failed: %s", error)
        return None


def _supabase_bucket_names(response: Any) -> set[str]:
    """Support supabase-py versions that return either a list or a response object."""
    items = getattr(response, "data", response) or []
    names: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = getattr(item, "name", None)
        if name:
            names.add(str(name))
    return names


def _ensure_supabase_storage_bucket(client: Any) -> None:
    global _SUPABASE_BUCKET_READY
    if _SUPABASE_BUCKET_READY:
        return
    with _SUPABASE_BUCKET_LOCK:
        if _SUPABASE_BUCKET_READY:
            return
        _ensure_supabase_storage_bucket_unlocked(client)
        _SUPABASE_BUCKET_READY = True


def _ensure_supabase_storage_bucket_unlocked(client: Any) -> None:
    try:
        response = client.storage.list_buckets()
        names = _supabase_bucket_names(response)
        if SUPABASE_STORAGE_BUCKET not in names:
            result = client.storage.create_bucket(SUPABASE_STORAGE_BUCKET, public=False)
            if getattr(result, "error", None):
                raise RuntimeError(str(getattr(result, "error")))
            logger.info("Created Supabase Storage bucket %s.", SUPABASE_STORAGE_BUCKET)
    except Exception as error:
        raise RuntimeError(f"Supabase Storage bucket '{SUPABASE_STORAGE_BUCKET}' could not be validated or created: {error}") from error


@lru_cache(maxsize=512)
def _supabase_storage_signed_url(storage_ref: str | None) -> str:
    if not storage_ref:
        return ""
    if storage_ref.startswith("http://") or storage_ref.startswith("https://"):
        return storage_ref
    if storage_ref.startswith("/"):
        return storage_ref

    bucket_name = SUPABASE_STORAGE_BUCKET
    if storage_ref.startswith(f"{bucket_name}/"):
        object_key = storage_ref[len(bucket_name) + 1:]
    else:
        object_key = storage_ref

    if not object_key:
        return ""

    client = _supabase_storage_client()
    if not client:
        logger.warning("Supabase Storage is not configured; cannot generate a signed URL for %s.", storage_ref)
        return ""

    try:
        response = client.storage.from_(bucket_name).create_signed_url(object_key, expires_in=SUPABASE_STORAGE_SIGNED_URL_TTL)
        url = response and getattr(response, "data", None)
        if isinstance(url, dict):
            signed = url.get("signedUrl") or url.get("url")
            if isinstance(signed, str) and signed:
                return signed
        if isinstance(response, dict):
            signed = response.get("signedUrl") or response.get("url")
            if isinstance(signed, str) and signed:
                return signed
    except Exception as error:
        logger.warning("Could not generate a signed URL for Supabase object %s: %s", storage_ref, error)
    return ""


def _supabase_storage_object_key(storage_ref: str) -> str:
    bucket_prefix = f"{SUPABASE_STORAGE_BUCKET}/"
    return storage_ref[len(bucket_prefix):] if storage_ref.startswith(bucket_prefix) else storage_ref


def _download_storage_image(storage_ref: str | None) -> bytes | None:
    """Read an evidence image for server-side PDF embedding.

    Supabase Storage references are downloaded with the backend secret. Legacy
    local upload references remain supported while old scans are migrated.
    """
    if not storage_ref:
        return None
    if storage_ref.startswith("/api/uploads/"):
        try:
            path = (STORAGE_DIR / Path(storage_ref).name).resolve()
            if path.parent == STORAGE_DIR and path.is_file():
                return path.read_bytes()
        except OSError:
            return None
        return None
    if storage_ref.startswith("http://") or storage_ref.startswith("https://"):
        return None
    client = _supabase_storage_client()
    if not client:
        return None
    try:
        response = client.storage.from_(SUPABASE_STORAGE_BUCKET).download(_supabase_storage_object_key(storage_ref))
        if isinstance(response, bytes):
            return response
        if isinstance(response, bytearray):
            return bytes(response)
        if isinstance(response, dict) and isinstance(response.get("data"), (bytes, bytearray)):
            return bytes(response["data"])
    except Exception as error:
        logger.warning("Could not download Supabase evidence image %s for PDF generation: %s", storage_ref, error)
    return None


def _report_image_sources(scan_id: str, cursor: Any = None) -> list[dict[str, Any]]:
    """Return every stored scan image as a PDF-ready source, in upload order."""
    owns_connection = cursor is None
    connection = None
    try:
        if owns_connection:
            connection = connect()
            cursor = connection.cursor()
        cursor.execute("SELECT image_ref, filename, sort_index FROM scan_images WHERE scan_id = %s ORDER BY sort_index, created_at", (scan_id,))
        rows = cursor.fetchall()
        if not rows:
            cursor.execute("SELECT image_ref, NULL AS filename, 1 AS sort_index FROM scans WHERE scan_id = %s", (scan_id,))
            rows = cursor.fetchall()
        sources = []
        for index, row in enumerate(rows, 1):
            reference = row.get("image_ref") or ""
            data = _download_storage_image(reference)
            filename = row.get("filename") or Path(reference).name or "Evidence View"
            sources.append({
                "label": filename,
                "bytes": data,
                "path": (STORAGE_DIR / Path(reference).name) if reference.startswith("/api/uploads/") else None,
                "reference": reference,
                "sort_index": row.get("sort_index", index),
            })
        return sources
    finally:
        if connection is not None:
            connection.close()


def _upload_to_supabase_storage(user_id: str, scan_id: str, filename: str, mime_type: str, data: bytes) -> str:
    client = _supabase_storage_client()
    if not client:
        raise RuntimeError("Supabase Storage is not configured. Add SUPABASE_URL and SUPABASE_SECRET_KEY to the backend .env file and create the scan-images bucket in Supabase.")

    _ensure_supabase_storage_bucket(client)
    storage_ref = _build_supabase_storage_key(user_id, scan_id, filename, uuid.uuid4().hex[:12])
    object_key = storage_ref.replace(f"{SUPABASE_STORAGE_BUCKET}/", "", 1)

    try:
        upload_response = client.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
            path=object_key,
            file=data,
            file_options={"content-type": mime_type or "application/octet-stream"},
        )
        if hasattr(upload_response, "error") and upload_response.error:
            raise RuntimeError(str(upload_response.error))
        if isinstance(upload_response, dict) and upload_response.get("error"):
            raise RuntimeError(str(upload_response["error"]))
    except Exception as error:
        logger.warning("Supabase Storage upload failed for user %s, scan %s, file %s: %s", user_id, scan_id, filename, error)
        raise RuntimeError(f"Supabase Storage upload failed for {filename}: {error}") from error

    return storage_ref


class LoginRequest(BaseModel):
    login_id: str
    password: str
    role: str | None = None
    otp: str | None = None


class RegisterRequest(BaseModel):
    login_id: str
    password: str
    name: str
    email: str | None = None
    role: str = "organization"
    organization_name: str | None = None
    organization_type: str | None = None
    official_mobile: str | None = None
    state: str | None = None
    district: str | None = None
    address: str | None = None
    pin_code: str | None = None
    gstin: str | None = None
    registration_number: str | None = None
    authorized_representative_name: str | None = None
    authorized_representative_designation: str | None = None
    authorized_representative_contact: str | None = None
    website: str | None = None
    industry: str | None = None


ACTIVE_ROLES = {"organization", "officer", "admin"}


def _user_payload(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"], "loginId": user["login_id"], "name": user["name"], "role": user["role"],
        "email": user.get("email") or "", "location": user.get("location") or "",
        "officerId": user.get("officer_id"), "organizationId": user.get("organization_id"), "orgId": user.get("organization_id"),
        "state": user.get("state"), "district": user.get("district"),
    }


def _verify_organization_otp(login_id: str, otp: str) -> bool:
    """Delegate OTP verification to the configured provider; never generate OTPs here."""
    if not ORGANIZATION_OTP_VERIFY_URL:
        return False
    body = json.dumps({"login_id": login_id, "otp": otp}).encode("utf-8")
    request = UrlRequest(
        ORGANIZATION_OTP_VERIFY_URL,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            return response.status == 200 and result.get("verified") is True
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return False


def _user_or_401(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication is required.")
    user = user_from_token(authorization[7:].strip())
    if not user:
        raise HTTPException(status_code=401, detail="Your session is invalid or has expired. Please sign in again.")
    if user.get("role") not in ACTIVE_ROLES:
        raise HTTPException(status_code=403, detail="This account type is no longer supported. Please contact an administrator.")
    return user


def _officer_or_403(authorization: str | None) -> dict[str, Any]:
    user = _user_or_401(authorization)
    if user["role"] != "officer":
        raise HTTPException(status_code=403, detail="Only officers can generate or access official reports.")
    return user


def _report_user_or_403(authorization: str | None) -> dict[str, Any]:
    user = _user_or_401(authorization)
    if user["role"] not in {"organization", "officer", "admin"}:
        raise HTTPException(status_code=403, detail="This account cannot access reports.")
    return user


def _admin_or_403(authorization: str | None) -> dict[str, Any]:
    user = _user_or_401(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can manage complaints in this jurisdiction.")
    return user


def _role_allowed(user: dict[str, Any], *allowed_roles: str) -> bool:
    return user.get("role") in allowed_roles


def _complaint_scope(user: dict[str, Any], *, requested_state: str | None = None, requested_district: str | None = None, alias: str = "c") -> tuple[str, list[Any]]:
    """Return a database scope for complaints; jurisdiction is never trusted from the client."""
    role = user.get("role")
    if role == "organization":
        return f"({alias}.organization_id = %s OR ({alias}.organization_id IS NULL AND {alias}.submitted_by = %s))", [user.get("organization_id"), user.get("name")]
    if role not in {"officer", "admin"}:
        raise HTTPException(status_code=403, detail="This account cannot access complaint records.")

    conditions: list[str] = []
    params: list[Any] = []
    admin_state = (user.get("state") or "").strip()
    admin_district = (user.get("district") or "").strip()
    state = (requested_state or "").strip()
    district = (requested_district or "").strip()
    if role in {"admin", "officer"}:
        # Both administrative roles are scoped by the jurisdiction attached
        # to their authenticated account. Admin filters may narrow that scope,
        # but neither role can broaden it from the client.
        if admin_state:
            if state and state.casefold() != admin_state.casefold():
                return "1 = 0", []
            state = admin_state
        if admin_district:
            if district and district.casefold() != admin_district.casefold():
                return "1 = 0", []
            district = admin_district
    if state:
        conditions.append(f"LOWER(COALESCE({alias}.state, '')) = LOWER(%s)")
        params.append(state)
    if district:
        conditions.append(f"LOWER(COALESCE({alias}.district, '')) = LOWER(%s)")
        params.append(district)
    return (" AND ".join(conditions) if conditions else "1 = 1"), params


AUTO_COMPLAINT_SOURCE = "AUTO_SCAN_VIOLATION"


def _complaint_frontend_status(status: str | None) -> str:
    normalized = str(status or "NEW").upper().replace("-", "_")
    return {
        "UNDER_REVIEW": "in-progress",
        "REVIEW": "in-progress",
        "INVESTIGATING": "in-progress",
        "IN_PROGRESS": "in-progress",
        "ACTION_TAKEN": "action-taken",
    }.get(normalized, normalized.lower().replace("_", "-"))


def _normalize_complaint_status(value: str | None) -> str:
    normalized = str(value or "IN_PROGRESS").upper().replace("-", "_")
    return {
        "NEW": "NEW",
        "VIEWED": "VIEWED",
        "IN_PROGRESS": "IN_PROGRESS",
        "UNDER_REVIEW": "IN_PROGRESS",
        "REVIEW": "IN_PROGRESS",
        "INVESTIGATING": "IN_PROGRESS",
        "ACTION_TAKEN": "ACTION_TAKEN",
        "RESOLVED": "RESOLVED",
        "CLOSED": "CLOSED",
    }.get(normalized, "IN_PROGRESS")


def _automatic_violation_complaint_data(
    scan_id: str,
    user: dict[str, Any],
    product_name: str,
    checks: list[dict[str, Any]],
    evidence_images: list[str],
) -> dict[str, Any] | None:
    violations = [item for item in checks if str(item.get("status") or "").upper() == "VIOLATION"]
    if not violations:
        return None
    details = []
    for item in violations:
        evidence = item.get("value") or item.get("evidence") or "Evidence unavailable"
        explanation = item.get("explanation") or "Rule violation detected by the compliance engine."
        details.append(f"- {item.get('label') or item.get('id')}: {explanation}\n  Evidence: {evidence}")
    return {
        "complaint_id": new_id("complaint"),
        "scan_id": scan_id,
        "organization_id": user.get("organization_id"),
        "product_name": product_name or "Untitled product",
        "product_category": None,
        "complaint_category": "Compliance violation",
        "complaint_description": f"Automatically created from compliance scan {scan_id}.\n\nRule violations:\n" + "\n".join(details),
        "complaint_location": user.get("location") or user.get("district") or "Unknown",
        "state": user.get("state"),
        "district": user.get("district"),
        "submitted_by": user.get("name") or "Compliance system",
        "status": "NEW",
        "source": AUTO_COMPLAINT_SOURCE,
        "priority": "HIGH",
        "evidence_images": evidence_images,
        "changed_by": user.get("id"),
    }


def _insert_automatic_violation_complaint(
    cursor: Any,
    scan_id: str,
    user: dict[str, Any],
    product_name: str,
    checks: list[dict[str, Any]],
    evidence_images: list[str],
) -> str | None:
    data = _automatic_violation_complaint_data(scan_id, user, product_name, checks, evidence_images)
    if not data:
        return None
    cursor.execute(
        "SELECT complaint_id FROM complaints WHERE scan_id = %s AND source = %s LIMIT 1",
        (scan_id, AUTO_COMPLAINT_SOURCE),
    )
    existing = cursor.fetchone()
    if existing:
        return existing["complaint_id"]
    cursor.execute(
        """
        INSERT INTO complaints (
            complaint_id, scan_id, organization_id, product_name, product_category,
            complaint_category, complaint_description, complaint_location, state,
            district, submitted_by, status, source, priority, evidence_images
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT DO NOTHING
        """,
        (
            data["complaint_id"], data["scan_id"], data["organization_id"], data["product_name"],
            data["product_category"], data["complaint_category"], data["complaint_description"],
            data["complaint_location"], data["state"], data["district"], data["submitted_by"],
            data["status"], data["source"], data["priority"], json.dumps(data["evidence_images"]),
        ),
    )
    cursor.execute(
        "SELECT complaint_id FROM complaints WHERE scan_id = %s AND source = %s LIMIT 1",
        (scan_id, AUTO_COMPLAINT_SOURCE),
    )
    created = cursor.fetchone()
    complaint_id = created["complaint_id"] if created else data["complaint_id"]
    if created and created["complaint_id"] == data["complaint_id"]:
        cursor.execute(
            "INSERT INTO complaint_status_history (history_id, complaint_id, previous_status, new_status, changed_by, administrative_remark) VALUES (%s, %s, %s, %s, %s, %s)",
            (new_id("history"), complaint_id, None, "NEW", data["changed_by"], "Automatic complaint created from scan violation."),
        )
    return complaint_id


def _complaint_dto(cursor: Any, row: dict[str, Any], *, include_history: bool = True) -> dict[str, Any]:
    evidence_refs = row.get("evidence_images") if isinstance(row.get("evidence_images"), list) else []
    evidence = [(_supabase_storage_signed_url(item) or item) if isinstance(item, str) else item for item in evidence_refs]
    scan = None
    report = None
    scan_id = row.get("scan_id")
    if scan_id and include_history:
        cursor.execute("SELECT scan_id, product_name, overall_status, compliance_score, scanned_at FROM scans WHERE scan_id = %s", (scan_id,))
        scan_row = cursor.fetchone()
        if scan_row:
            scan = {"id": scan_row["scan_id"], "product": scan_row.get("product_name"), "status": scan_row.get("overall_status"), "complianceScore": scan_row.get("compliance_score"), "scannedAt": iso_datetime(scan_row.get("scanned_at"))}
            cursor.execute("SELECT report_id, generated_at, status FROM reports WHERE scan_id = %s ORDER BY generated_at DESC LIMIT 1", (scan_id,))
            report_row = cursor.fetchone()
            if report_row:
                report = {"id": report_row["report_id"], "generatedAt": iso_datetime(report_row.get("generated_at")), "status": report_row.get("status")}
    history = []
    if include_history:
        cursor.execute("SELECT h.history_id, h.previous_status, h.new_status, h.changed_at, h.administrative_remark, u.name AS changed_by_name FROM complaint_status_history h LEFT JOIN users u ON u.id = h.changed_by WHERE h.complaint_id = %s ORDER BY h.changed_at ASC", (row["complaint_id"],))
        history = [{"id": item["history_id"], "previousStatus": item.get("previous_status"), "newStatus": item.get("new_status"), "changedBy": item.get("changed_by_name"), "changedAt": iso_datetime(item.get("changed_at")), "administrativeRemark": item.get("administrative_remark")} for item in cursor.fetchall()]
    frontend_status = _complaint_frontend_status(row.get("status"))
    return {
        "id": row["complaint_id"], "product": row.get("product_name") or "Untitled product", "image": evidence[0] if evidence else "", "evidenceImages": evidence,
        "shop": row.get("submitted_by") or row.get("organization_name") or "Organization", "location": row.get("complaint_location") or row.get("district") or "Unknown",
        "category": row.get("complaint_category") or row.get("product_category") or "Other", "description": row.get("complaint_description") or "",
        "status": frontend_status, "submittedBy": row.get("submitted_by") or "", "date": iso_datetime(row.get("created_at")), "updatedAt": iso_datetime(row.get("updated_at") or row.get("created_at")),
        "relatedScans": 1 if scan_id else 0, "organizationId": row.get("organization_id"), "organizationName": row.get("organization_name"), "scanId": scan_id,
        "reportId": report["id"] if report else row.get("report_id"), "state": row.get("state"), "district": row.get("district"), "adminRemark": row.get("admin_remark"), "history": history,
        "source": row.get("source"), "relatedScan": scan, "relatedReport": report,
    }


def _complaint_list_query(user: dict[str, Any], *, search: str | None = None, state: str | None = None, district: str | None = None, status: str | None = None, category: str | None = None, date: str | None = None) -> tuple[str, list[Any]]:
    scope, params = _complaint_scope(user, requested_state=state, requested_district=district)
    conditions = [scope]
    if search:
        conditions.append("(c.complaint_id ILIKE %s OR c.product_name ILIKE %s OR c.submitted_by ILIKE %s OR c.complaint_description ILIKE %s)")
        params.extend([f"%{search}%"] * 4)
    if status:
        normalized = status.upper().replace("-", "_")
        if normalized in {"REVIEW", "UNDER_REVIEW", "INVESTIGATING"}:
            normalized = "IN_PROGRESS"
        conditions.append("c.status = %s")
        params.append(normalized)
    if category:
        conditions.append("COALESCE(c.complaint_category, c.product_category, 'Other') = %s")
        params.append(category)
    if date:
        conditions.append("c.created_at::date = %s")
        params.append(date)
    return " AND ".join(conditions), params


def _field_record(observation: FieldObservation) -> dict[str, Any]:
    return {
        "status": observation.state.value,
        "value": observation.value,
        "confidence": observation.confidence,
        "evidence": observation.evidence,
    }


def _package_data(package: ExtractedPackage) -> dict[str, Any]:
    return json_value(dataclasses.asdict(package))


def _calculate_compliance_score(results: list[dict[str, Any]]) -> int:
    applicable = [item for item in results if (item.get("status") or "").upper() != "NOT_APPLICABLE"]
    if not applicable:
        return 100
    violations = sum(1 for item in applicable if (item.get("status") or "").upper() == "VIOLATION")
    review = sum(1 for item in applicable if (item.get("status") or "").upper() in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED"})
    score = 100 - (violations * 25) - (review * 10)
    return max(0, min(100, score))


def _scan_dto(scan: dict[str, Any], results: list[dict[str, Any]], cursor: Any = None) -> dict[str, Any]:
    extracted = scan.get("extracted_data") or {}
    fields = extracted.get("fields") or {}
    def field_value(name: str, fallback: str = "—") -> str:
        item = fields.get(name) or {}
        value = item.get("value") if isinstance(item, dict) else None
        return str(value) if value not in (None, "") else fallback
    def field_confidence(name: str) -> float:
        item = fields.get(name) or {}
        value = item.get("confidence") if isinstance(item, dict) else None
        try:
            return float(value) if value is not None else 0
        except (TypeError, ValueError):
            return 0
    def detected(name: str) -> bool:
        item = fields.get(name) or {}
        return isinstance(item, dict) and item.get("status") == ObservationState.PRESENT.value and bool(item.get("value"))

    declarations = [
        {"key": "manufacturer", "label": "Manufacturer / Packer", "detected": detected("manufacturer"), "value": field_value("manufacturer"), "confidence": field_confidence("manufacturer")},
        {"key": "productName", "label": "Product Name", "detected": detected("generic_name"), "value": field_value("generic_name"), "confidence": field_confidence("generic_name")},
        {"key": "netQuantity", "label": "Net Quantity", "detected": detected("net_quantity"), "value": field_value("net_quantity"), "confidence": field_confidence("net_quantity")},
        {"key": "mrp", "label": "MRP", "detected": detected("mrp"), "value": field_value("mrp"), "confidence": field_confidence("mrp")},
        {"key": "manufactureDate", "label": "Date of Manufacture", "detected": detected("manufacture_or_pack_or_import_date"), "value": field_value("manufacture_or_pack_or_import_date"), "confidence": field_confidence("manufacture_or_pack_or_import_date")},
        {"key": "consumerCare", "label": "Consumer Care Details", "detected": detected("consumer_care"), "value": field_value("consumer_care"), "confidence": field_confidence("consumer_care")},
    ]
    violations = [
        {"id": item["id"], "title": item["label"], "explanation": item["explanation"], "requirement": item["reference"], "evidence": item["value"], "severity": "medium"}
        for item in results if item["status"] == "VIOLATION"
    ]
    scanned_at = iso_datetime(scan["scanned_at"])
    
    # Retrieve all images from scan_images table if cursor provided
    normalized_images = []
    image_refs = scan.get("_image_refs")
    if image_refs is not None:
        normalized_images = [
            _supabase_storage_signed_url(reference) or reference
            for reference in image_refs
            if reference
        ]
    elif cursor:
        try:
            cursor.execute("SELECT image_ref FROM scan_images WHERE scan_id = %s ORDER BY sort_index", (scan["scan_id"],))
            image_rows = cursor.fetchall()
            normalized_images = [
                _supabase_storage_signed_url(row["image_ref"]) or row["image_ref"]
                for row in image_rows
                if row.get("image_ref")
            ]
        except Exception:
            pass

    # Fallback to legacy image_ref if no images found
    if not normalized_images and scan.get("image_ref"):
        normalized_images = [_supabase_storage_signed_url(scan["image_ref"]) or scan["image_ref"]]
    
    score = scan.get("compliance_score")
    if score is None:
        score = _calculate_compliance_score(results)
    return {
        "id": scan["scan_id"],
        "scan_id": scan["scan_id"],
        "product": scan.get("product_name") or "Product name unavailable",
        "image": normalized_images[0] if normalized_images else (scan.get("image_ref") or ""),
        "images": normalized_images,
        "date": scanned_at,
        "status": {"COMPLIANT": "compliant", "VIOLATION": "non-compliant"}.get(scan["overall_status"], "needs-review"),
        "violations": len(violations),
        "declarations": declarations,
        "violationList": violations,
        "category": None,
        "location": None,
        "extractedData": extracted,
        "checks": results,
        "complianceScore": int(score),
    }


def _result_rows(cursor: Any, scan_id: str) -> list[dict[str, Any]]:
    cursor.execute("SELECT * FROM compliance_results WHERE scan_id = %s ORDER BY id", (scan_id,))
    rows = cursor.fetchall()
    return [
        {
                "id": row["id"],
            "rule_id": row["check_name"],
            "label": row["check_name"],
            "status": row["status"],
            "value": row.get("extracted_value") or "Evidence unavailable for this assessment",
            "reference": row.get("applicable_requirement") or "Unavailable",
            "explanation": row["explanation"],
            "evidence": row.get("evidence") or "Evidence unavailable for this assessment",
            "confidence": float(row["confidence"]) if row.get("confidence") is not None else None,
            "sourceImage": row.get("source_image"),
        }
        for row in rows
    ]


def _result_rows_for_scans(cursor: Any, scan_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not scan_ids:
        return {}
    cursor.execute("SELECT * FROM compliance_results WHERE scan_id = ANY(%s) ORDER BY scan_id, id", (scan_ids,))
    grouped: dict[str, list[dict[str, Any]]] = {scan_id: [] for scan_id in scan_ids}
    for row in cursor.fetchall():
        grouped.setdefault(row["scan_id"], []).append({
            "id": row["id"],
            "rule_id": row["check_name"],
            "label": row["check_name"],
            "status": row["status"],
            "value": row.get("extracted_value") or "Evidence unavailable for this assessment",
            "reference": row.get("applicable_requirement") or "Unavailable",
            "explanation": row["explanation"],
            "evidence": row.get("evidence") or "Evidence unavailable for this assessment",
            "confidence": float(row["confidence"]) if row.get("confidence") is not None else None,
            "sourceImage": row.get("source_image"),
        })
    return grouped


def _get_scan(scan_id: str, user: dict[str, Any]) -> dict[str, Any] | None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT s.*, u.state AS scan_state, u.district AS scan_district FROM scans s JOIN users u ON u.id = s.user_id WHERE s.scan_id = %s", (scan_id,))
            scan = cursor.fetchone()
            allowed = bool(scan and (scan["user_id"] == user["id"] or (user["role"] == "organization" and scan.get("organization_id") == user.get("organization_id"))))
            if user.get("role") == "admin" and scan:
                allowed = (not user.get("state") or str(scan.get("scan_state") or "").casefold() == str(user["state"]).casefold()) and (not user.get("district") or str(scan.get("scan_district") or "").casefold() == str(user["district"]).casefold())
            if not scan or not allowed:
                return None
            return _scan_dto(scan, _result_rows(cursor, scan_id), cursor)


def _report_summary(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total_checks": len(checks),
        "total": len(checks),
        "compliant": sum(1 for item in checks if item["status"] == "COMPLIANT"),
        "violations": sum(1 for item in checks if item["status"] == "VIOLATION"),
        "review": sum(1 for item in checks if item["status"] in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED", "NOT_APPLICABLE"}),
    }


def _build_pdf_report(
    report_id: str,
    scan: dict[str, Any],
    checks: list[dict[str, Any]],
    generated_at: datetime,
    officer_name: str,
    location: str | None,
    images: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble one report payload from persisted scan data for all PDF callers."""
    status = scan.get("overall_status")
    if not status:
        status = {"compliant": "COMPLIANT", "non-compliant": "VIOLATION"}.get(scan.get("status"), "UNABLE_TO_VERIFY")
    score = scan.get("compliance_score")
    if score is None:
        score = scan.get("complianceScore")
    if score is None:
        # This is only a backwards-compatible fallback for scans created before
        # the persisted score column existed. The PDF itself never calculates a score.
        score = _calculate_compliance_score(checks)
    return {
        "report_id": report_id,
        "scan_id": scan.get("scan_id") or scan.get("id"),
        "product_name": scan.get("product_name") or scan.get("product") or "Product name unavailable",
        "overall_status": status,
        "status": status,
        "scanned_at": scan.get("scanned_at") or scan.get("date"),
        "generated_at": generated_at,
        "officer_name": officer_name,
        "location": location or "Not provided",
        "extracted_data": scan.get("extracted_data") or scan.get("extractedData") or {},
        "checks": checks,
        "summary": _report_summary(checks),
        "compliance_score": int(score),
        "images": images,
    }


def _report_dto(row: dict[str, Any], checks: list[dict[str, Any]], extracted: dict[str, Any]) -> dict[str, Any]:
    summary = _report_summary(checks)
    metadata = row.get("metadata") or {}
    score = row.get("compliance_score")
    if score is None and isinstance(metadata, dict):
        score = metadata.get("compliance_score")
    if score is None:
        score = _calculate_compliance_score(checks)
    return {
        "id": row["report_id"], "report_id": row["report_id"], "scanId": row["scan_id"], "scan_id": row["scan_id"],
        "productName": row.get("product_name") or "Product name unavailable", "generatedAt": iso_datetime(row["generated_at"]),
        "scanDate": iso_datetime(row["scanned_at"]), "officerName": row.get("officer_name") or "Unavailable",
        "applicationName": "NIRIKSHA", "reportTitle": "NIRIKSHA Legal Metrology Compliance Report",
        "overallStatus": {"COMPLIANT": "compliant", "VIOLATION": "non-compliant"}.get(row["status"], "needs-review"),
        "summary": summary, "checks": [{
            "id": str(item["id"]), "name": item["label"], "status": {"COMPLIANT": "compliant", "VIOLATION": "non-compliant"}.get(item["status"], "needs-review"),
            "value": item["value"], "requirement": item["reference"], "explanation": item["explanation"], "evidence": item["evidence"], "confidence": item.get("confidence"),
        } for item in checks], "pdfUrl": f"/api/reports/{row['report_id']}/pdf", "extractedData": extracted,
        "complianceScore": int(score), "location": row.get("inspection_location") or "Not provided",
    }


def _report_list_dto(row: dict[str, Any]) -> dict[str, Any]:
    status = row.get("scan_status") or row.get("status")
    return {
        "id": row["report_id"], "report_id": row["report_id"], "scanId": row["scan_id"], "scan_id": row["scan_id"],
        "productName": row.get("product_name") or "Product name unavailable", "generatedAt": iso_datetime(row["generated_at"]),
        "scanDate": iso_datetime(row["scanned_at"]), "officerName": row.get("officer_name") or "Unavailable",
        "applicationName": "NIRIKSHA", "reportTitle": "NIRIKSHA Legal Metrology Compliance Report",
        "overallStatus": {"COMPLIANT": "compliant", "VIOLATION": "non-compliant"}.get(status, "needs-review"),
        "summary": {
            "violations": int(row.get("violation_count") or 0), "review": int(row.get("review_count") or 0),
            "compliant": int(row.get("compliant_count") or 0), "total": int(row.get("check_count") or 0),
        },
        "checks": [], "pdfUrl": f"/api/reports/{row['report_id']}/pdf", "complianceScore": int(row.get("compliance_score") or 0),
        "location": row.get("inspection_location") or "Not provided",
    }


def _json_from_response(text: str) -> Any:
    if "```" in text:
        fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
        if fenced:
            text = fenced[0].strip()
    return json.loads(text)


def _normalize_status(value: Any) -> ObservationState:
    if not value:
        return ObservationState.NOT_ASSESSED
    status_map = {
        "VISIBLE": ObservationState.PRESENT,
        "PRESENT": ObservationState.PRESENT,
        "CONFIRMED_ABSENT": ObservationState.CONFIRMED_ABSENT,
        "NOT_VISIBLE": ObservationState.NOT_VISIBLE,
        "NOT_VISIBLE_IN_IMAGE": ObservationState.NOT_VISIBLE,
        "UNREADABLE": ObservationState.UNREADABLE,
        "UNREADABLE_TEXT": ObservationState.UNREADABLE,
        "NOT_ASSESSED": ObservationState.NOT_ASSESSED,
    }
    normalized = str(value).strip().upper().replace("-", "_")
    return status_map.get(normalized, ObservationState.NOT_ASSESSED)


def _field_from_record(field_name: str, record: Any) -> FieldObservation:
    if not isinstance(record, dict):
        return FieldObservation(state=ObservationState.NOT_ASSESSED)
    state = _normalize_status(record.get("status") or record.get("visibility") or record.get("state"))
    value = record.get("value")
    confidence = record.get("confidence")
    evidence = record.get("evidence") or record.get("source_text") or ""
    bbox = record.get("bounding_box") or record.get("bbox") or {}
    if bbox and evidence:
        evidence = f"{evidence} :: {bbox}"
    try:
        normalized_confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        normalized_confidence = None
    return FieldObservation(
        state=state,
        value=value if state is not ObservationState.NOT_VISIBLE else None,
        confidence=normalized_confidence,
        evidence=evidence,
    )


def _map_quantity_basis(value: Any) -> QuantityBasis | None:
    if value is None:
        return None
    mapping = {
        "WEIGHT": QuantityBasis.WEIGHT,
        "VOLUME": QuantityBasis.VOLUME,
        "LENGTH": QuantityBasis.LENGTH,
        "AREA": QuantityBasis.AREA,
        "NUMBER": QuantityBasis.NUMBER,
    }
    return mapping.get(str(value).strip().upper(), None)


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y"}:
            return True
        if lowered in {"false", "no", "n"}:
            return False
    return bool(value)


def _best_observation(observations: list[FieldObservation]) -> FieldObservation:
    """Keep the strongest source when the extractor returns legacy aliases.

    A model may return both a canonical field and an older alias.  Do not let a
    later, weaker alias replace a visible declaration with an unverified one.
    """
    if not observations:
        return FieldObservation(state=ObservationState.NOT_ASSESSED)
    rank = {
        ObservationState.PRESENT: 4,
        ObservationState.UNREADABLE: 3,
        ObservationState.NOT_VISIBLE: 2,
        ObservationState.CONFIRMED_ABSENT: 1,
        ObservationState.NOT_ASSESSED: 0,
    }
    return max(
        observations,
        key=lambda item: (rank[item.state], item.confidence or 0.0, bool(item.evidence), len(item.value or "")),
    )


def _extract_package(payload: dict[str, Any]) -> ExtractedPackage:
    fields = payload.get("fields", {})
    context = payload.get("context", {})
    package_context = PackageContext(
        is_imported=_as_bool(context.get("is_imported")),
        may_become_unfit_for_human_consumption=_as_bool(context.get("may_become_unfit_for_human_consumption")),
        date_requirement_governed_by_other_law=_as_bool(context.get("date_requirement_governed_by_other_law")),
        unit_sale_price_required=_as_bool(context.get("unit_sale_price_required")),
        retail_sale_price_equals_unit_sale_price=_as_bool(context.get("retail_sale_price_equals_unit_sale_price")),
        unit_sale_price_governed_by_other_law=_as_bool(context.get("unit_sale_price_governed_by_other_law")),
        quantity_basis=_map_quantity_basis(context.get("quantity_basis")),
        contains_multiple_products=_as_bool(context.get("contains_multiple_products")),
        is_genetically_modified_food=_as_bool(context.get("is_genetically_modified_food")),
        requires_vegetarian_origin_mark=_as_bool(context.get("requires_vegetarian_origin_mark")),
        is_ecommerce_entity_offering_imported_product=_as_bool(context.get("is_ecommerce_entity_offering_imported_product")),
        # Missing coverage data must never be treated as proof that every
        # relevant label surface was inspected.
        inspected_relevant_label_surfaces=_as_bool(context.get("inspected_relevant_label_surfaces")) is True,
    )

    mapping = {
        "generic_name": "generic_name",
        "product_name": "generic_name",
        "manufacturer": "manufacturer",
        "manufacturer_details": "manufacturer",
        "packer": "packer",
        "packer_details": "packer",
        "importer": "importer",
        "importer_details": "importer",
        "country_of_origin": "country_of_origin",
        "country_of_origin_details": "country_of_origin",
        "net_quantity": "net_quantity",
        "mrp": "mrp",
        "unit_sale_price": "unit_sale_price",
        "manufacture_or_pack_or_import_date": "manufacture_or_pack_or_import_date",
        "pack_date": "manufacture_or_pack_or_import_date",
        "date_declaration": "manufacture_or_pack_or_import_date",
        "best_before_or_use_by": "best_before_or_use_by",
        "best_before": "best_before_or_use_by",
        "use_by": "best_before_or_use_by",
        "consumer_care": "consumer_care",
        "consumer_care_details": "consumer_care",
        "component_names_and_quantities": "component_names_and_quantities",
        "gm_mark": "gm_mark",
        "dietary_origin_mark": "dietary_origin_mark",
        "vegetarian_non_vegetarian_mark": "dietary_origin_mark",
        "ecommerce_country_of_origin_filter": "ecommerce_country_of_origin_filter",
    }

    candidates: dict[str, list[FieldObservation]] = {}
    for dto_key, package_key in mapping.items():
        if dto_key in fields:
            candidates.setdefault(package_key, []).append(_field_from_record(dto_key, fields[dto_key]))
    extra_fields = {key: _best_observation(value) for key, value in candidates.items()}

    package = ExtractedPackage(
        generic_name=extra_fields.get("generic_name", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        manufacturer=extra_fields.get("manufacturer", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        packer=extra_fields.get("packer", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        importer=extra_fields.get("importer", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        country_of_origin=extra_fields.get("country_of_origin", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        net_quantity=extra_fields.get("net_quantity", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        mrp=extra_fields.get("mrp", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        unit_sale_price=extra_fields.get("unit_sale_price", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        manufacture_or_pack_or_import_date=extra_fields.get("manufacture_or_pack_or_import_date", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        best_before_or_use_by=extra_fields.get("best_before_or_use_by", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        consumer_care=extra_fields.get("consumer_care", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        component_names_and_quantities=extra_fields.get("component_names_and_quantities", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        gm_mark=extra_fields.get("gm_mark", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        dietary_origin_mark=extra_fields.get("dietary_origin_mark", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        ecommerce_country_of_origin_filter=extra_fields.get("ecommerce_country_of_origin_filter", FieldObservation(state=ObservationState.NOT_ASSESSED)),
        context=package_context,
    )
    return package


def _build_extraction_prompt() -> str:
    return """
    Extract only what is visible in the supplied package label images. Examine
    every supplied image before deciding a field is not visible. Treat each as
    a different possible package surface; do not use text from one field to
    manufacture a value for another.

    Rules:
    - Do not invent missing text.
    - Return exact, verbatim label text for value and evidence. Preserve the
      printed currency, punctuation, units, and dates; do not normalize values.
    - VISIBLE means the declaration or symbol itself is visible. NOT_VISIBLE
      means it was not found in supplied images. Use CONFIRMED_ABSENT only when
      all relevant label surfaces are clearly readable and the declaration is
      genuinely absent; otherwise use NOT_VISIBLE or UNREADABLE.
    - If the text is visible but difficult to read, set status to UNREADABLE and provide the best readable text if available.
    - Extract serving_size separately from net_quantity. Never infer net quantity
      from serving size, "per serve", portion size, nutrition facts, price, or
      unit sale price. Extract net_quantity only from a standalone declaration
      such as "Net Qty 50 g", "Net Weight: 500 g", or an otherwise clearly
      standalone package quantity. If only a serving quantity is visible, mark
      net_quantity NOT_VISIBLE or UNREADABLE with evidence explaining why.
    - Keep MRP/retail price separate from unit_sale_price. For example, extract
      "MRP ₹20.00 (INCL. OF ALL TAXES)" as MRP and "USP ₹1.00 PER g" as unit
      sale price when those exact declarations are visible.
    - generic_name is the common/generic commodity wording (for example,
      "POTATO CHIPS"), not merely a brand or flavour. product_name may identify
      the branded product separately.
    - dietary_origin_mark must record a visibly detected green vegetarian or
      brown non-vegetarian symbol, including its type in value/evidence.
    - manufacturer_details and consumer_care_details must include the complete
      visible declaration, including address, email, phone, and references to
      an address stated above where printed.
    - Return valid JSON only. No markdown fences.
    - Include image_coverage and context sections for downstream legal validation.
    - Confidence should be between 0 and 1.

    Output JSON schema:
    {
      "image_coverage": {
        "overall": "COMPLETE|PARTIAL|UNKNOWN",
        "minimum_required_surfaces_covered": true,
        "notes": "..."
      },
      "context": {
        "is_imported": true,
        "may_become_unfit_for_human_consumption": true,
        "date_requirement_governed_by_other_law": false,
        "unit_sale_price_required": false,
        "retail_sale_price_equals_unit_sale_price": false,
        "unit_sale_price_governed_by_other_law": false,
        "quantity_basis": "WEIGHT|VOLUME|LENGTH|AREA|NUMBER|UNKNOWN",
        "contains_multiple_products": false,
        "is_genetically_modified_food": false,
        "requires_vegetarian_origin_mark": false,
        "is_ecommerce_entity_offering_imported_product": false,
        "inspected_relevant_label_surfaces": true
      },
      "fields": {
        "generic_name": {"status": "VISIBLE|NOT_VISIBLE|UNREADABLE|CONFIRMED_ABSENT|NOT_ASSESSED", "value": "...", "confidence": 0.93, "evidence": "Visible text excerpt", "bounding_box": {"x": 10, "y": 20, "w": 60, "h": 15}},
        "manufacturer_details": {"status": "VISIBLE|NOT_VISIBLE|UNREADABLE|CONFIRMED_ABSENT|NOT_ASSESSED", "value": "...", "confidence": 0.9, "evidence": "...", "bounding_box": {"x": 0, "y": 0, "w": 0, "h": 0}},
        "packer_details": {"status": "NOT_VISIBLE", "value": null, "confidence": 0.0, "evidence": "Not visible on the provided images."},
        "importer_details": {"status": "NOT_VISIBLE", "value": null, "confidence": 0.0, "evidence": "Not visible on the provided images."},
        "country_of_origin": {"status": "NOT_VISIBLE", "value": null, "confidence": 0.0, "evidence": "Not visible on the provided images."},
        "net_quantity": {"status": "VISIBLE", "value": "Net Qty 200 g", "confidence": 0.9, "evidence": "..."},
        "serving_size": {"status": "VISIBLE|NOT_VISIBLE|UNREADABLE|CONFIRMED_ABSENT|NOT_ASSESSED", "value": "Per Serve (20 g)", "confidence": 0.9, "evidence": "..."},
        "mrp": {"status": "NOT_VISIBLE", "value": null, "confidence": 0.0, "evidence": "Not visible on the provided images."},
        "unit_sale_price": {"status": "NOT_VISIBLE", "value": null, "confidence": 0.0, "evidence": "Not visible on the provided images."},
        "date_declaration": {"status": "VISIBLE", "value": "Packed Aug 2026", "confidence": 0.9, "evidence": "..."},
        "best_before": {"status": "NOT_VISIBLE", "value": null, "confidence": 0.0, "evidence": "Not visible on the provided images."},
        "use_by": {"status": "NOT_VISIBLE", "value": null, "confidence": 0.0, "evidence": "Not visible on the provided images."},
        "consumer_care_details": {"status": "VISIBLE", "value": "Consumer care: ...", "confidence": 0.9, "evidence": "..."},
        "dietary_origin_mark": {"status": "VISIBLE|NOT_VISIBLE|UNREADABLE|CONFIRMED_ABSENT|NOT_ASSESSED", "value": "Green vegetarian symbol", "confidence": 0.9, "evidence": "..."},
        "gm_mark": {"status": "VISIBLE|NOT_VISIBLE|UNREADABLE|CONFIRMED_ABSENT|NOT_ASSESSED", "value": null, "confidence": 0.0, "evidence": "..."},
        "component_names_and_quantities": {"status": "VISIBLE|NOT_VISIBLE|UNREADABLE|CONFIRMED_ABSENT|NOT_ASSESSED", "value": null, "confidence": 0.0, "evidence": "..."},
        "other_declarations": {"status": "NOT_VISIBLE", "value": null, "confidence": 0.0, "evidence": "No additional declarations visible."}
      }
    }
    """


def _prepare_images_for_gemini(images: list[tuple[str, str, bytes]]) -> list[tuple[str, str, bytes]]:
    prepared: list[tuple[str, str, bytes]] = []
    for filename, mime_type, data in images:
        try:
            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
                if max(width, height) <= GEMINI_MAX_IMAGE_DIMENSION and len(data) <= GEMINI_MAX_IMAGE_BYTES:
                    prepared.append((filename, mime_type, data))
                    continue
                scale = min(1, GEMINI_MAX_IMAGE_DIMENSION / max(width, height))
                resized = image.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.Resampling.LANCZOS) if scale < 1 else image.copy()
                output = io.BytesIO()
                output_format = "PNG" if mime_type == "image/png" else "JPEG"
                if output_format == "JPEG" and resized.mode not in {"RGB", "L"}:
                    resized = resized.convert("RGB")
                resized.save(output, format=output_format, quality=90, optimize=True)
                prepared.append((filename, "image/png" if output_format == "PNG" else "image/jpeg", output.getvalue()))
        except Exception:
            logger.warning("Could not prepare image %s for Gemini; sending the original bytes.", filename)
            prepared.append((filename, mime_type, data))
    return prepared


def _gemini_error_code(error: Exception) -> int | None:
    for value in (getattr(error, "code", None), getattr(error, "status_code", None)):
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            continue
    return None


def _configured_gemini_credentials() -> list[tuple[str, str]]:
    primary_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not primary_key:
        return []
    primary_model = GEMINI_MODEL.strip()
    fallback_model = GEMINI_FALLBACK_MODEL
    credentials = [(primary_key, primary_model)]
    if fallback_model and fallback_model != primary_model:
        credentials.append((primary_key, fallback_model))
    configured_keys: list[str] = []
    for value in ((os.getenv("GEMINI_API_KEY_FALLBACK") or ""), (os.getenv("GEMINI_API_KEYS") or "")):
        configured_keys.extend(item.strip() for item in value.split(",") if item.strip())
    for key in dict.fromkeys(configured_keys):
        if key != primary_key:
            credentials.append((key, fallback_model or primary_model))
    return list(dict.fromkeys(credentials))


async def _call_gemini(images: list[tuple[str, str, bytes]]) -> dict[str, Any]:
    credentials = _configured_gemini_credentials()
    if not credentials:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is empty. Add your key to the project .env file before running the backend.")

    contents: list[Any] = []
    for filename, mime_type, data in images:
        contents.append(types.Part.from_bytes(data=data, mime_type=mime_type))
        contents.append(f"Inspect the complete package image named {filename}, including all readable label panels.")
    contents.append("Return only compact valid JSON, with no reasoning or markdown. Carefully inspect the images directly for product name, manufacturer/packer/importer, MRP, net quantity and unit of measurement, manufacturing/packing date, best before/expiry, consumer care/contact details, country of origin, and every other visible mandatory declaration. For net quantity, search the entire image for Net Quantity, Net Qty, Net Weight, Net Wt, Quantity, Contents, and values such as 100 g, 250 g, 500 g, 1 kg, 100 ml, 500 ml, or 1 L. If text is unclear or unreadable, return null or unknown with an explanation and never invent a value.\n" + _build_extraction_prompt())

    response = None
    last_error: Exception | None = None
    for credential_index, (api_key, model) in enumerate(credentials):
        client = genai.Client(api_key=api_key)
        quota_exhausted = False
        for attempt in range(1, 4):
            try:
                logger.info("[GEMINI] Attempt %d using configured credential %d", attempt, credential_index + 1)
                request_started = time.perf_counter()
                logger.info("[GEMINI] Request started")
                generate_kwargs: dict[str, Any] = {"model": model, "contents": contents}
                # Current SDKs accept deterministic JSON generation. Avoid probing
                # with a second request when a lightweight test double is in use.
                if "unittest.mock" not in type(client.models.generate_content).__module__:
                    generate_kwargs["config"] = types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    )
                response = client.models.generate_content(**generate_kwargs)
                logger.info("[GEMINI] Response received: %.2fs", time.perf_counter() - request_started)
                logger.info("[GEMINI] Success")
                break
            except Exception as error:
                last_error = error
                error_text = str(error)
                status_code = _gemini_error_code(error)
                is_auth_error = (
                    status_code == 401
                    or "UNAUTHENTICATED" in error_text
                    or "ACCESS_TOKEN_TYPE_UNSUPPORTED" in error_text
                )
                is_quota_error = status_code == 429 or "RESOURCE_EXHAUSTED" in error_text or "quota" in error_text.lower()
                is_transient_error = status_code is not None and status_code >= 500

                if is_auth_error:
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Gemini rejected GEMINI_API_KEY. Create a fresh Gemini API key in Google AI Studio, "
                            "replace GEMINI_API_KEY in the backend .env file, and restart Uvicorn."
                        ),
                    ) from error
                if is_quota_error:
                    if credential_index + 1 < len(credentials):
                        logger.warning("[GEMINI] Quota exhausted for configured model/credential %d; switching to the next configured fallback.", credential_index + 1)
                        quota_exhausted = True
                        break
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            "Gemini request quota is exhausted for the configured models. "
                            "Wait for the quota to reset, enable billing, or set GEMINI_API_KEY_FALLBACK "
                            "or GEMINI_API_KEYS with a key from another Google project."
                        ),
                    ) from error
                if not is_transient_error:
                    raise HTTPException(
                        status_code=502,
                        detail="Gemini image analysis is temporarily unavailable. Check the backend log and try again.",
                    ) from error
                if attempt < 3:
                    delay = 2 if attempt == 1 else 5
                    logger.warning("[GEMINI] %s received, retrying in %d seconds", status_code or "temporary failure", delay)
                    await asyncio.sleep(delay)
                else:
                    logger.error("[GEMINI] All %d attempts failed", attempt)
                    raise HTTPException(status_code=503, detail="AI analysis service is temporarily unavailable. Please try again.") from error
        if response is not None:
            break
        if not quota_exhausted:
            break

    if response is None:
        raise HTTPException(status_code=503, detail="AI analysis service is temporarily unavailable. Please try again.") from last_error
    text = getattr(response, "text", None)
    if not text:
        text = ""
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", []) if content else []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    text += part_text
        if not text:
            raise HTTPException(status_code=502, detail="Gemini returned no valid structured response.")

    payload = _json_from_response(text)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Gemini response was not valid JSON.")
    return payload


def _persist_scan_artifacts(
    scan_id: str,
    user: dict[str, Any],
    loaded: list[tuple[str, str, bytes]],
    package: ExtractedPackage,
    result: Any,
    checks: list[dict[str, Any]],
    compliance_score: int,
) -> None:
    started = time.perf_counter()
    storage_refs: list[str] = []
    image_refs: list[str] = []
    try:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        upload_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=min(4, len(loaded))) as executor:
            local_and_remote = list(executor.map(
                lambda item: (
                    item,
                    _upload_to_supabase_storage(user["id"], scan_id, item[0], item[1], item[2]),
                ),
                loaded,
            ))
        for index, ((filename, _mime_type, data), storage_ref) in enumerate(local_and_remote, 1):
            image_filename = f"{uuid.uuid4().hex}{Path(filename).suffix.lower() or '.jpg'}"
            (STORAGE_DIR / image_filename).write_bytes(data)
            image_refs.append(f"/api/uploads/{image_filename}")
            storage_refs.append(storage_ref)
        logger.info("[SCAN] Background image upload: %.2fs", time.perf_counter() - upload_started)

        db_started = time.perf_counter()
        with connect() as connection:
            with connection.cursor() as cursor:
                for index, ((filename, mime_type, _data), storage_ref) in enumerate(zip(loaded, storage_refs), 1):
                    cursor.execute(
                        "INSERT INTO scan_images (scan_image_id, scan_id, image_ref, filename, mime_type, sort_index) VALUES (%s, %s, %s, %s, %s, %s)",
                        (new_id("scan_image"), scan_id, storage_ref, filename, mime_type, index),
                    )
                cursor.execute("UPDATE scans SET image_ref = %s WHERE scan_id = %s", (storage_refs[0] if storage_refs else "", scan_id))
                _insert_automatic_violation_complaint(
                    cursor, scan_id, user, package.generic_name.value or "Product name unavailable", checks, storage_refs,
                )
            connection.commit()
        logger.info("[SCAN] Background DB: %.2fs", time.perf_counter() - db_started)

        report_id = new_id("report")
        pdf_path = STORAGE_DIR / "reports" / f"{report_id}.pdf"
        generated_at = datetime.now(UTC)
        report_started = time.perf_counter()
        scan = _get_scan(scan_id, user)
        if not scan:
            raise RuntimeError("The saved scan could not be loaded for report generation.")
        report_images = [
            {"label": filename, "bytes": data, "path": None, "reference": storage_ref, "sort_index": index}
            for index, ((filename, _mime_type, data), storage_ref) in enumerate(zip(loaded, storage_refs), 1)
        ]
        pdf_report = _build_pdf_report(report_id, scan, scan.get("checks", []), generated_at, user.get("name", "Unknown"), user.get("location"), report_images)
        create_pdf(pdf_report, pdf_path)
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO reports (report_id, scan_id, generated_by, organization_id, generated_at, pdf_path, status, metadata) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
                    (report_id, scan_id, user["id"], user.get("organization_id"), generated_at, str(pdf_path), result.overall_status.value, json.dumps({"compliance_score": compliance_score, "generator": "reportlab"})),
                )
            connection.commit()
        logger.info("[SCAN] Report: %.2fs", time.perf_counter() - report_started)
    except Exception as error:
        logger.warning("Asynchronous scan persistence failed for %s: %s", scan_id, error)
    finally:
        logger.info("[SCAN] Background persistence: %.2fs", time.perf_counter() - started)


@app.on_event("startup")
async def startup() -> None:
    try:
        init_db()
    except Exception as error:  # The API can still start and expose a useful health/error response.
        print(f"NIRIKSHA database initialization failed: {error}")


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        with connect() as connection:
            connection.execute("SELECT 1")
        return {"status": "ok", "database": "ok"}
    except Exception:
        return {"status": "ok", "database": "unavailable"}


@app.post("/api/db/init")
async def initialize_database() -> dict[str, str]:
    try:
        init_db()
        return {"status": "ok", "message": "PostgreSQL schema initialized."}
    except Exception:
        raise HTTPException(status_code=503, detail="The PostgreSQL schema could not be initialized. Check DATABASE_URL and database availability.")


@app.post("/api/auth/login")
async def login(request: LoginRequest) -> dict[str, Any]:
    requested_role = (request.role or "").strip().lower() or None
    if requested_role and requested_role not in ACTIVE_ROLES:
        raise HTTPException(status_code=403, detail="Only organization, officer, and admin accounts can sign in.")
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                if requested_role == "organization":
                    cursor.execute(
                        "SELECT * FROM users WHERE (LOWER(login_id) = LOWER(%s) OR LOWER(COALESCE(email, '')) = LOWER(%s)) AND role = %s LIMIT 1",
                        (request.login_id.strip(), request.login_id.strip(), requested_role),
                    )
                else:
                    cursor.execute("SELECT u.*, COALESCE(NULLIF(u.state, ''), a.state) AS state, COALESCE(NULLIF(u.district, ''), a.district) AS district FROM users u LEFT JOIN admins a ON a.id = u.id WHERE LOWER(u.login_id) = LOWER(%s)", (request.login_id.strip(),))
                user = cursor.fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="The authentication service is unavailable. Check the PostgreSQL connection.")
    if not user or (requested_role and user["role"] != requested_role) or user["role"] not in ACTIVE_ROLES or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if user["role"] == "organization" and ORGANIZATION_OTP_REQUIRED:
        if not request.otp:
            raise HTTPException(status_code=401, detail="A one-time password is required for organization sign in.")
        if not ORGANIZATION_OTP_VERIFY_URL:
            raise HTTPException(status_code=503, detail="Organization OTP is enabled but no OTP provider is configured on the backend.")
        if not _verify_organization_otp(request.login_id.strip(), request.otp.strip()):
            raise HTTPException(status_code=401, detail="The organization OTP could not be verified.")
    return {
        "token": create_token(user["id"]),
        "user": _user_payload(user),
        "otpRequired": ORGANIZATION_OTP_REQUIRED,
    }


@app.post("/api/auth/register")
async def register(request: RegisterRequest) -> dict[str, Any]:
    allowed_roles = {"organization"}
    if request.role not in allowed_roles or len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Organization registration requires a password of at least 8 characters.")
    if not request.email or not request.email.strip():
        raise HTTPException(status_code=400, detail="An official business email is required.")
    try:
        user = create_user(
            request.email.strip().lower(),
            request.password,
            request.organization_name.strip() if request.organization_name else request.name.strip(),
            request.role,
            request.email.strip().lower(),
            state=request.state,
            district=request.district,
            organization_name=request.organization_name,
            organization_type=request.organization_type,
            official_mobile=request.official_mobile,
            registered_address=request.address,
            pin_code=request.pin_code,
            gstin=request.gstin,
            registration_number=request.registration_number,
            authorized_representative_name=request.authorized_representative_name,
            authorized_representative_designation=request.authorized_representative_designation,
            authorized_representative_contact=request.authorized_representative_contact,
            website=request.website,
            industry=request.industry,
        )
    except Exception as error:
        if "unique" in str(error).lower() or "duplicate" in str(error).lower():
            raise HTTPException(status_code=409, detail="That login ID is already registered.")
        raise HTTPException(status_code=503, detail="The account could not be saved. Check the PostgreSQL connection.")
    return {"token": create_token(user["id"]), "user": _user_payload(user)}


@app.get("/api/admin/dashboard")
async def admin_dashboard(
    state: str | None = Query(default=None), district: str | None = Query(default=None), authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    admin = _admin_or_403(authorization)
    with connect() as connection:
        with connection.cursor() as cursor:
            where, params = _complaint_list_query(admin, state=state, district=district)
            cursor.execute(f"SELECT status, COUNT(*) AS count FROM complaints c WHERE {where} GROUP BY status", params)
            statuses = {row["status"]: int(row["count"]) for row in cursor.fetchall()}
            total = sum(statuses.values())
            return {
                "total_complaints": total,
                "new": statuses.get("NEW", 0),
                "viewed": statuses.get("VIEWED", 0),
                "in_progress": sum(statuses.get(key, 0) for key in ("IN_PROGRESS", "UNDER_REVIEW", "REVIEW", "INVESTIGATING")),
                "under_review": sum(statuses.get(key, 0) for key in ("IN_PROGRESS", "UNDER_REVIEW", "REVIEW", "INVESTIGATING")),
                "action_taken": statuses.get("ACTION_TAKEN", 0),
                "investigating": statuses.get("INVESTIGATING", 0),
                "resolved": statuses.get("RESOLVED", 0),
                "closed": statuses.get("CLOSED", 0),
                "requires_attention": sum(statuses.get(k, 0) for k in ("NEW", "VIEWED", "IN_PROGRESS", "UNDER_REVIEW", "REVIEW", "INVESTIGATING")),
                "admin": {"name": admin["name"], "state": admin.get("state") or "All", "district": admin.get("district") or "All"},
            }


@app.get("/api/admin/filters")
async def admin_filters(authorization: str | None = Header(default=None)) -> dict[str, list[str]]:
    admin = _admin_or_403(authorization)
    scope, params = _complaint_scope(admin)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT DISTINCT state FROM complaints c WHERE {scope} AND state IS NOT NULL AND state <> '' ORDER BY state", params)
            states = [row["state"] for row in cursor.fetchall()]
            cursor.execute(f"SELECT DISTINCT district FROM complaints c WHERE {scope} AND district IS NOT NULL AND district <> '' ORDER BY district", params)
            districts = [row["district"] for row in cursor.fetchall()]
            cursor.execute(f"SELECT DISTINCT COALESCE(complaint_category, product_category, 'Other') AS category FROM complaints c WHERE {scope} ORDER BY category", params)
            categories = [row["category"] for row in cursor.fetchall()]
    return {"states": states, "districts": districts, "categories": categories}


@app.get("/api/admin/violations")
async def admin_violations(state: str | None = Query(default=None), district: str | None = Query(default=None), authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    admin = _admin_or_403(authorization)
    conditions, params = _complaint_scope(admin, requested_state=state, requested_district=district, alias="u")
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COALESCE(u.state, 'Not provided') AS state, COALESCE(u.district, 'Not provided') AS district, cr.check_name AS rule_id, COUNT(*) AS count FROM compliance_results cr JOIN scans s ON s.scan_id = cr.scan_id JOIN users u ON u.id = s.user_id WHERE cr.status = 'VIOLATION' AND {conditions} GROUP BY u.state, u.district, cr.check_name ORDER BY count DESC", params)
            return [dict(row) for row in cursor.fetchall()]


@app.get("/api/admin/complaints")
async def admin_complaints(
    search: str | None = Query(default=None), state: str | None = Query(default=None), district: str | None = Query(default=None),
    status: str | None = Query(default=None), category: str | None = Query(default=None), date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    admin = _admin_or_403(authorization)
    where, params = _complaint_list_query(admin, search=search, state=state, district=district, status=status, category=category, date=date)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT c.*, o.organization_name FROM complaints c LEFT JOIN organizations o ON o.id = c.organization_id WHERE {where} ORDER BY c.created_at DESC LIMIT %s OFFSET %s", [*params, limit, offset])
            return [_complaint_dto(cursor, row, include_history=False) for row in cursor.fetchall()]


@app.get("/api/complaints")
async def list_complaints(
    search: str | None = Query(default=None), state: str | None = Query(default=None), district: str | None = Query(default=None),
    status: str | None = Query(default=None), category: str | None = Query(default=None), date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    user = _user_or_401(authorization)
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                where, params = _complaint_list_query(user, search=search, state=state, district=district, status=status, category=category, date=date)
                cursor.execute(f"SELECT c.*, o.organization_name FROM complaints c LEFT JOIN organizations o ON o.id = c.organization_id WHERE {where} ORDER BY c.created_at DESC LIMIT %s OFFSET %s", [*params, limit, offset])
                return [_complaint_dto(cursor, row, include_history=False) for row in cursor.fetchall()]
    except Exception:
        raise HTTPException(status_code=503, detail="Complaint records are temporarily unavailable.")


@app.post("/api/complaints")
async def create_complaint(request: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _user_or_401(authorization)
    if user["role"] != "organization":
        raise HTTPException(status_code=403, detail="Only organizations can submit complaints.")
    complaint_id = new_id("complaint")
    payload = request or {}
    product_name = str(payload.get("product") or payload.get("product_name") or "Unspecified product")
    complaint_category = str(payload.get("category") or payload.get("complaint_category") or "Other")
    complaint_location = str(payload.get("location") or payload.get("complaint_location") or "Unknown")
    description = str(payload.get("description") or payload.get("complaint_description") or "")
    evidence_images = payload.get("evidence_images") if isinstance(payload.get("evidence_images"), list) else []
    with connect() as connection:
        with connection.cursor() as cursor:
            scan_id = payload.get("scan_id")
            if scan_id:
                cursor.execute("SELECT scan_id FROM scans WHERE scan_id = %s AND (user_id = %s OR organization_id = %s)", (scan_id, user["id"], user.get("organization_id")))
                if not cursor.fetchone():
                    raise HTTPException(status_code=403, detail="The selected scan does not belong to your organization.")
            cursor.execute(
                "INSERT INTO complaints (complaint_id, scan_id, organization_id, product_name, product_category, complaint_category, complaint_description, complaint_location, state, district, submitted_by, status, priority, evidence_images) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
                (complaint_id, scan_id, user.get("organization_id"), product_name, payload.get("product_category"), complaint_category, description, complaint_location, user.get("state"), user.get("district"), user.get("name"), "NEW", payload.get("priority") or "MEDIUM", json.dumps(evidence_images)),
            )
            cursor.execute(
                "INSERT INTO complaint_status_history (history_id, complaint_id, previous_status, new_status, changed_by, administrative_remark) VALUES (%s, %s, %s, %s, %s, %s)",
                (new_id("history"), complaint_id, None, "NEW", user["id"], None),
            )
            cursor.execute("SELECT c.*, o.organization_name FROM complaints c LEFT JOIN organizations o ON o.id = c.organization_id WHERE c.complaint_id = %s", (complaint_id,))
            created = cursor.fetchone()
            result = _complaint_dto(cursor, created) if created else None
        connection.commit()
    return result or {"id": complaint_id, "status": "new"}


@app.patch("/api/complaints/{complaint_id}/status")
async def update_complaint_status(complaint_id: str, request: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    admin = _admin_or_403(authorization)
    new_status = _normalize_complaint_status(request.get("status") or request.get("new_status"))
    with connect() as connection:
        with connection.cursor() as cursor:
            scope, scope_params = _complaint_scope(
                admin,
                requested_state=str(request.get("state") or ""),
                requested_district=str(request.get("district") or ""),
            )
            cursor.execute(f"SELECT complaint_id, status, admin_remark FROM complaints c WHERE c.complaint_id = %s AND {scope}", [complaint_id, *scope_params])
            current = cursor.fetchone()
            if not current:
                raise HTTPException(status_code=404, detail="Complaint not found.")
            previous_status = current["status"]
            remark = request["admin_remark"] if "admin_remark" in request else current.get("admin_remark")
            cursor.execute(
                "UPDATE complaints SET status = %s, admin_remark = %s, updated_at = NOW() WHERE complaint_id = %s",
                (new_status, remark, complaint_id),
            )
            if previous_status != new_status or request.get("admin_remark") is not None:
                cursor.execute("INSERT INTO complaint_status_history (history_id, complaint_id, previous_status, new_status, changed_by, administrative_remark) VALUES (%s, %s, %s, %s, %s, %s)", (new_id("history"), complaint_id, previous_status, new_status, admin["id"], remark))
        connection.commit()
    return {"id": complaint_id, "status": _complaint_frontend_status(new_status), "updatedBy": admin["name"], "remark": remark}


@app.get("/api/complaints/{complaint_id}")
async def get_complaint(complaint_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _user_or_401(authorization)
    scope, scope_params = _complaint_scope(user)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT 1 FROM complaints c WHERE c.complaint_id = %s AND {scope}", [complaint_id, *scope_params])
            if not cursor.fetchone():
                cursor.execute("SELECT 1 FROM complaints WHERE complaint_id = %s", (complaint_id,))
                if cursor.fetchone():
                    raise HTTPException(status_code=403, detail="This complaint is outside your permitted scope.")
                raise HTTPException(status_code=404, detail="Complaint not found.")
            cursor.execute("SELECT c.*, o.organization_name FROM complaints c LEFT JOIN organizations o ON o.id = c.organization_id WHERE c.complaint_id = %s", (complaint_id,))
            return _complaint_dto(cursor, cursor.fetchone())


@app.post("/api/scan")
async def scan_images(background_tasks: BackgroundTasks, images: list[UploadFile] = File(...), authorization: str | None = Header(default=None)) -> dict[str, Any]:
    total_started = time.perf_counter()
    logger.info("[PERF] Request received")
    user = _user_or_401(authorization)
    if len(images) < 2:
        raise HTTPException(status_code=400, detail="At least 2 images are required for a scan.")

    loaded: list[tuple[str, str, bytes]] = []
    for upload in images:
        if not upload.filename:
            raise HTTPException(status_code=400, detail="Each uploaded file must include a name.")
        if not upload.content_type or not upload.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Unsupported file type for {upload.filename}. Please upload images only.")
        if upload.content_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported file type for {upload.filename}. Allowed types are JPG, PNG, or WebP.")
        data = await upload.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"The uploaded file {upload.filename} is empty.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"The uploaded file {upload.filename} exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB size limit.")
        loaded.append((upload.filename, upload.content_type, data))

    logger.info("[PERF] Image upload/read: %.2fs", time.perf_counter() - total_started)
    image_started = time.perf_counter()
    gemini_images = _prepare_images_for_gemini(loaded)
    logger.info("[PERF] Image processing: %.2fs", time.perf_counter() - image_started)
    gemini_started = time.perf_counter()
    payload = await _call_gemini(gemini_images)
    logger.info("[PERF] Gemini request: %.2fs", time.perf_counter() - gemini_started)
    parse_started = time.perf_counter()
    rules_started = time.perf_counter()
    package = _extract_package(payload)
    result = ComplianceEngine().evaluate(package)
    logger.info("[PERF] Gemini response parsing: %.2fs", time.perf_counter() - parse_started)
    logger.info("[PERF] Rules: %.2fs", time.perf_counter() - rules_started)

    checks = []
    for outcome in result.outcomes:
        checks.append(
            {
                "id": outcome.rule_id,
                "label": outcome.title,
                "status": outcome.status.value,
                # A visible value without a separate evidence excerpt is still
                # not a missing declaration. _outcome preserves the value as a
                # fallback so the existing report card remains factually true.
                "value": outcome.evidence or "Evidence unavailable for this assessment",
                "reference": outcome.legal_reference,
                "explanation": outcome.explanation,
                "sourceImage": None,
                "confidence": None,
            }
        )
    scan_id = new_id("scan")
    compliance_score = _calculate_compliance_score(checks)
    db_started = time.perf_counter()
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO scans (scan_id, user_id, organization_id, product_name, overall_status, image_ref, image_metadata, extracted_data, compliance_score) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)",
                    (scan_id, user["id"], user.get("organization_id"), package.generic_name.value or "Product name unavailable", result.overall_status.value, "", json.dumps({"image_count": len(loaded)}), json.dumps({"fields": {name: _field_record(getattr(package, name)) for name in ("generic_name", "manufacturer", "packer", "importer", "country_of_origin", "net_quantity", "mrp", "unit_sale_price", "manufacture_or_pack_or_import_date", "best_before_or_use_by", "consumer_care", "component_names_and_quantities", "gm_mark", "dietary_origin_mark", "ecommerce_country_of_origin_filter")}, "context": json_value(dataclasses.asdict(package.context)), "image_coverage": payload.get("image_coverage", {})}), compliance_score),
                )
                for outcome in result.outcomes:
                    cursor.execute(
                        "INSERT INTO compliance_results (scan_id, check_name, status, extracted_value, applicable_requirement, explanation, evidence) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (scan_id, outcome.rule_id, outcome.status.value, outcome.evidence or None, outcome.legal_reference, outcome.explanation, outcome.evidence or None),
                    )
            connection.commit()
    except Exception:
        raise HTTPException(status_code=503, detail="The scan was analyzed but could not be saved. Check the PostgreSQL connection.")
    logger.info("[PERF] DB: %.2fs", time.perf_counter() - db_started)

    scan = _get_scan(scan_id, user)
    if not scan:
        raise HTTPException(status_code=503, detail="The scan was saved but could not be loaded.")

    background_tasks.add_task(_persist_scan_artifacts, scan_id, user, loaded, package, result, checks, compliance_score)
    logger.info("[PERF] Total user response: %.2fs", time.perf_counter() - total_started)
    
    return {
        "overall_status": result.overall_status.value,
        "checks": checks,
        "coverage": payload.get("image_coverage", {"overall": "UNKNOWN", "minimum_required_surfaces_covered": False, "notes": ""}),
        "summary": {"total_checks": len(checks), "compliant": sum(1 for item in checks if item["status"] == "COMPLIANT"), "violations": sum(1 for item in checks if item["status"] == "VIOLATION"), "review": sum(1 for item in checks if item["status"] in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED", "NOT_APPLICABLE"})},
        "scan": scan,
        "report_id": None,
        "complaint_id": None,
    }


@app.get("/api/uploads/{filename}")
async def uploaded_image(filename: str):
    from fastapi.responses import FileResponse
    path = (STORAGE_DIR / Path(filename).name).resolve()
    if path.parent != STORAGE_DIR or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(path)


@app.get("/api/scans")
async def list_scans(
    search: str | None = Query(default=None), status: str | None = Query(default=None), date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    user = _user_or_401(authorization)
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                if user["role"] == "admin":
                    conditions = ["1 = 1"]
                    params: list[Any] = []
                    if user.get("state"):
                        conditions.append("LOWER(COALESCE(u.state, '')) = LOWER(%s)"); params.append(user["state"])
                    if user.get("district"):
                        conditions.append("LOWER(COALESCE(u.district, '')) = LOWER(%s)"); params.append(user["district"])
                elif user["role"] == "organization":
                    conditions = ["(s.user_id = %s OR s.organization_id = %s)"]
                    params = [user["id"], user.get("organization_id")]
                else:
                    conditions = ["s.user_id = %s"]
                    params = [user["id"]]

                if search:
                    conditions.append("(s.scan_id ILIKE %s OR COALESCE(s.product_name, '') ILIKE %s)")
                    params.extend([f"%{search}%", f"%{search}%"])
                if status:
                    normalized_status = {"needs-review": "UNABLE_TO_VERIFY", "non-compliant": "VIOLATION", "compliant": "COMPLIANT"}.get(status.lower(), status.upper())
                    conditions.append("s.overall_status = %s")
                    params.append(normalized_status)
                if date:
                    conditions.append("s.scanned_at::date = %s")
                    params.append(date)
                cursor.execute(f"SELECT s.* FROM scans s JOIN users u ON u.id = s.user_id WHERE {' AND '.join(conditions)} ORDER BY s.scanned_at DESC LIMIT %s OFFSET %s", [*params, limit, offset])
                rows = cursor.fetchall()
                scan_ids = [row["scan_id"] for row in rows]
                results_by_scan = _result_rows_for_scans(cursor, scan_ids)
                cursor.execute("SELECT scan_id, image_ref FROM scan_images WHERE scan_id = ANY(%s) ORDER BY scan_id, sort_index, created_at", (scan_ids,)) if scan_ids else None
                images_by_scan: dict[str, list[str]] = {scan_id: [] for scan_id in scan_ids}
                if scan_ids:
                    for image_row in cursor.fetchall():
                        images_by_scan.setdefault(image_row["scan_id"], []).append(image_row["image_ref"])
                response = []
                for row in rows:
                    row["_image_refs"] = images_by_scan.get(row["scan_id"], [])
                    response.append(_scan_dto(row, results_by_scan.get(row["scan_id"], [])))
                return response
    except Exception:
        raise HTTPException(status_code=503, detail="Scan history is temporarily unavailable.")


@app.get("/api/scans/{scan_id}")
async def get_scan(scan_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _user_or_401(authorization)
    try:
        scan = _get_scan(scan_id, user)
    except Exception:
        raise HTTPException(status_code=503, detail="The scan could not be loaded.")
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return scan


def _report_record(report_id: str, user: dict[str, Any]) -> dict[str, Any] | None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.*, s.product_name, s.user_id, s.overall_status AS scan_status, s.scanned_at, s.extracted_data, s.compliance_score,
                       u.name AS officer_name, scan_user.location AS inspection_location, scan_user.state AS inspection_state, scan_user.district AS inspection_district
                FROM reports r JOIN scans s ON s.scan_id = r.scan_id JOIN users u ON u.id = r.generated_by
                LEFT JOIN users scan_user ON scan_user.id = s.user_id
                WHERE r.report_id = %s
                """, (report_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            if user["role"] == "officer":
                if row["generated_by"] != user["id"]:
                    return None
            elif user["role"] == "organization":
                if row["user_id"] != user["id"] and row.get("organization_id") != user.get("organization_id"):
                    return None
            elif user.get("state") and str(row.get("inspection_state") or "").casefold() != str(user["state"]).casefold():
                return None
            elif user.get("district") and str(row.get("inspection_district") or "").casefold() != str(user["district"]).casefold():
                return None
            row["status"] = row["scan_status"]
            # Add compliance_score to the row metadata for _report_dto to use
            if not row.get("metadata"):
                row["metadata"] = {}
            elif isinstance(row["metadata"], str):
                try:
                    row["metadata"] = json.loads(row["metadata"])
                except (json.JSONDecodeError, TypeError):
                    row["metadata"] = {}
            if isinstance(row["metadata"], dict):
                row["metadata"]["compliance_score"] = row.get("compliance_score")
            return _report_dto(row, _result_rows(cursor, row["scan_id"]), row.get("extracted_data") or {})


@app.post("/api/reports/{scan_id}")
async def generate_report(scan_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _report_user_or_403(authorization)
    try:
        if not _get_scan(scan_id, user):
            raise HTTPException(status_code=404, detail="Scan not found.")
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT s.*, u.name AS scan_user_name, u.location AS inspection_location FROM scans s JOIN users u ON u.id = s.user_id WHERE s.scan_id = %s", (scan_id,))
                scan = cursor.fetchone()
                if not scan:
                    raise HTTPException(status_code=404, detail="Scan not found.")
                checks = _result_rows(cursor, scan_id)
                report_id = new_id("report")
                generated_at = datetime.now(UTC)
                pdf_path = STORAGE_DIR / "reports" / f"{report_id}.pdf"
                pdf_report = _build_pdf_report(
                    report_id,
                    {**scan, "scan_id": scan_id},
                    checks,
                    generated_at,
                    user["name"],
                    scan.get("inspection_location"),
                    _report_image_sources(scan_id, cursor),
                )
                create_pdf(pdf_report, pdf_path)
                cursor.execute("INSERT INTO reports (report_id, scan_id, generated_by, organization_id, generated_at, pdf_path, status, metadata) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)", (report_id, scan_id, user["id"], scan.get("organization_id"), generated_at, str(pdf_path), scan["overall_status"], json.dumps({"compliance_score": scan.get("compliance_score", 0), "generator": "reportlab"})))
            connection.commit()
        created = _report_record(report_id, user)
        if not created:
            raise HTTPException(status_code=503, detail="The report was generated but could not be loaded.")
        return created
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="The PDF report could not be generated or saved.")


@app.get("/api/reports")
async def list_reports(
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    user = _report_user_or_403(authorization)
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                if user["role"] == "officer":
                    scope = "r.generated_by = %s"
                    scope_params: list[Any] = [user["id"]]
                elif user["role"] == "admin":
                    scope_parts = ["(%s = '' OR LOWER(COALESCE(u.state, '')) = LOWER(%s))", "(%s = '' OR LOWER(COALESCE(u.district, '')) = LOWER(%s))"]
                    scope = " AND ".join(scope_parts)
                    scope_params = [user.get("state") or "", user.get("state") or "", user.get("district") or "", user.get("district") or ""]
                else:
                    scope = "(s.user_id = %s OR r.organization_id = %s)"
                    scope_params = [user["id"], user.get("organization_id")]
                cursor.execute(
                    f"""
                    SELECT r.report_id, r.scan_id, r.generated_at, r.metadata,
                           s.product_name, s.overall_status AS scan_status, s.scanned_at, s.compliance_score,
                           u.name AS officer_name, scan_user.location AS inspection_location,
                           COUNT(cr.id) AS check_count,
                           COUNT(cr.id) FILTER (WHERE cr.status = 'COMPLIANT') AS compliant_count,
                           COUNT(cr.id) FILTER (WHERE cr.status = 'VIOLATION') AS violation_count,
                           COUNT(cr.id) FILTER (WHERE cr.status IN ('UNABLE_TO_VERIFY', 'OFFICER_REVIEW_REQUIRED', 'NOT_APPLICABLE')) AS review_count
                    FROM reports r
                    JOIN scans s ON s.scan_id = r.scan_id
                    JOIN users u ON u.id = r.generated_by
                    LEFT JOIN users scan_user ON scan_user.id = s.user_id
                    LEFT JOIN compliance_results cr ON cr.scan_id = s.scan_id
                    WHERE {scope}
                    GROUP BY r.report_id, r.scan_id, r.generated_at, r.metadata, s.product_name, s.overall_status,
                             s.scanned_at, s.compliance_score, u.name, scan_user.location
                    ORDER BY r.generated_at DESC LIMIT %s OFFSET %s
                    """, [*scope_params, limit, offset],
                )
                return [_report_list_dto(row) for row in cursor.fetchall()]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Reports are temporarily unavailable.")


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _report_user_or_403(authorization)
    try:
        report = _report_record(report_id, user)
    except Exception:
        raise HTTPException(status_code=503, detail="The report could not be loaded.")
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@app.get("/api/reports/{report_id}/pdf")
async def download_report(report_id: str, authorization: str | None = Header(default=None)):
    user = _report_user_or_403(authorization)
    from fastapi.responses import FileResponse
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT r.pdf_path, r.organization_id, s.product_name, s.user_id, s.organization_id AS scan_organization_id, r.generated_by, u.state, u.district FROM reports r JOIN scans s ON s.scan_id = r.scan_id JOIN users u ON u.id = s.user_id WHERE r.report_id = %s",
                    (report_id,),
                )
                row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Report not found.")
        if user["role"] == "officer":
            if row["generated_by"] != user["id"]:
                raise HTTPException(status_code=404, detail="Report not found.")
        elif user["role"] == "organization" and row["user_id"] != user["id"] and row.get("organization_id") != user.get("organization_id"):
            raise HTTPException(status_code=404, detail="Report not found.")
        elif user["role"] == "admin" and ((user.get("state") and str(row.get("state") or "").casefold() != str(user["state"]).casefold()) or (user.get("district") and str(row.get("district") or "").casefold() != str(user["district"]).casefold())):
            raise HTTPException(status_code=404, detail="Report not found.")
        path = Path(row["pdf_path"]).resolve()
        if not path.is_file() or STORAGE_DIR not in path.parents:
            raise HTTPException(status_code=404, detail="The PDF file is no longer available.")
        return FileResponse(path, media_type="application/pdf", filename=f"{report_id}.pdf")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="The PDF could not be downloaded.")


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
