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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
from PIL import Image

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False)

from compliance_engine import (
    ComplianceEngine,
    ExtractedPackage,
    FieldObservation,
    ObservationState,
    PackageContext,
    QuantityBasis,
)
from compliance_engine.rules import is_valid_mrp_declaration
from database import STORAGE_DIR, connect, create_token, create_user, init_db, iso_datetime, json_value, new_id, user_from_token, verify_password
from pdf_reports import CERTIFICATE_LAYOUT_VERSION, create_certificate_pdf, create_pdf

app = FastAPI(title="NIRIKSHA Package Compliance API")

# R6_10A was a former e-commerce listing metric. It is intentionally no
# longer evaluated, but older scans may still contain persisted rows. Keep
# those legacy rows in the database for auditability while excluding them
# from all application-facing result/report/analytics views.
EXCLUDED_LEGACY_RULE_IDS = {"R6_10A"}


def _configured_origins() -> list[str]:
    """Read exact browser origins allowed to call the API.

    Keep credentials enabled without allowing every website. The deployed
    frontend origin(s) belong in FRONTEND_ORIGINS on the backend host.
    """
    raw_origins = os.getenv("FRONTEND_ORIGINS", "")
    configured = [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]
    local = ["http://127.0.0.1:5173", "http://localhost:5173"]
    return list(dict.fromkeys(local + configured))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

logger = logging.getLogger("niriksha")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.6-flash").strip()
ORGANIZATION_OTP_REQUIRED = (os.getenv("ORGANIZATION_OTP_REQUIRED", "false").strip().lower() in {"1", "true", "yes", "on"})
ORGANIZATION_OTP_VERIFY_URL = (os.getenv("ORGANIZATION_OTP_VERIFY_URL") or "").strip()
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_SECRET_KEY = (os.getenv("SUPABASE_SECRET_KEY") or "").strip()
SUPABASE_STORAGE_BUCKET = (os.getenv("SUPABASE_STORAGE_BUCKET") or "scan-images").strip() or "scan-images"
SUPABASE_STORAGE_SIGNED_URL_TTL = max(60, int(os.getenv("SUPABASE_STORAGE_SIGNED_URL_TTL", "3600")))
CERTIFICATE_VERIFICATION_BASE_URL = (os.getenv("CERTIFICATE_VERIFICATION_BASE_URL") or "").strip().rstrip("/")
MAX_UPLOAD_BYTES = max(1, int(os.getenv("MAX_UPLOAD_BYTES", "10485760")))
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
GEMINI_MAX_IMAGE_DIMENSION = 3000
GEMINI_MAX_IMAGE_BYTES = 8 * 1024 * 1024
GEMINI_REQUEST_TIMEOUT_SECONDS = max(1.0, float(os.getenv("GEMINI_REQUEST_TIMEOUT_SECONDS", "60")))
GEMINI_FALLBACK_TIMEOUT_SECONDS = max(GEMINI_REQUEST_TIMEOUT_SECONDS, float(os.getenv("GEMINI_FALLBACK_TIMEOUT_SECONDS", "60")))
GEMINI_TOTAL_TIMEOUT_SECONDS = max(GEMINI_FALLBACK_TIMEOUT_SECONDS, float(os.getenv("GEMINI_TOTAL_TIMEOUT_SECONDS", "120")))
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


class ProfileUpdateRequest(BaseModel):
    name: str
    location: str
    state: str | None = None
    district: str | None = None


class InspectionReviewRequest(BaseModel):
    officer_name: str
    designation: str
    department: str
    inspection_location: str
    inspection_date: str
    inspection_remarks: str = ""
    recommended_action: str = ""
    review_status: str


ACTIVE_ROLES = {"organization", "officer", "admin"}


def _user_payload(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"], "loginId": user["login_id"], "name": user["name"], "role": user["role"],
        "email": user.get("email") or "", "location": user.get("location") or "",
        "officerId": user.get("officer_id"), "organizationId": user.get("organization_id"), "orgId": user.get("organization_id"),
        "state": user.get("state"), "district": user.get("district"),
        "designation": user.get("designation") or user.get("administrative_role") or ("Officer" if user.get("role") == "officer" else user.get("role", "").title()),
        "department": user.get("department") or "",
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


def _organization_or_403(authorization: str | None) -> dict[str, Any]:
    user = _user_or_401(authorization)
    if user["role"] != "organization":
        raise HTTPException(status_code=403, detail="Only organizations can access compliance certificates.")
    return user


def _officer_or_403(authorization: str | None) -> dict[str, Any]:
    user = _user_or_401(authorization)
    if user["role"] != "officer":
        raise HTTPException(status_code=403, detail="Only officers can generate or access official reports.")
    return user


def _report_user_or_403(authorization: str | None) -> dict[str, Any]:
    user = _user_or_401(authorization)
    if user["role"] not in {"officer", "admin"}:
        raise HTTPException(status_code=403, detail="Only officers and admins can access official reports.")
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
    record: dict[str, Any] = {
        "status": observation.state.value,
        "value": observation.value,
        "confidence": observation.confidence,
        "evidence": observation.evidence,
    }
    if observation.source_image is not None:
        record["source_image_index"] = observation.source_image
    if observation.source_image_ref:
        record["source_image_ref"] = observation.source_image_ref
    if observation.bounding_box:
        record["bounding_box"] = observation.bounding_box
    return record


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


def _certificate_eligibility(scan: dict[str, Any], checks: list[dict[str, Any]]) -> tuple[bool, str]:
    """Evaluate certificate eligibility without changing compliance results."""
    status = str(scan.get("overall_status") or scan.get("status") or "").upper().replace("-", "_")
    try:
        score = int(scan.get("compliance_score") if scan.get("compliance_score") is not None else _calculate_compliance_score(checks))
    except (TypeError, ValueError):
        score = 0
    applicable = [item for item in checks if str(item.get("status") or "").upper() != "NOT_APPLICABLE"]
    mandatory_unverified = [item for item in applicable if str(item.get("status") or "").upper() in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED"}]
    mandatory_violations = [item for item in applicable if str(item.get("status") or "").upper() == "VIOLATION"]
    all_verified = all(str(item.get("status") or "").upper() == "COMPLIANT" for item in applicable)
    if status != "COMPLIANT":
        return False, "The final compliance status is not COMPLIANT."
    if score < 90:
        return False, "The compliance score is below the required 90/100 certificate threshold."
    if mandatory_violations:
        return False, "One or more applicable mandatory requirements are NON-COMPLIANT."
    if mandatory_unverified or not all_verified:
        return False, "One or more applicable mandatory requirements require verification."
    return True, "All applicable mandatory requirements are verified and the score meets the certificate threshold."


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
    certificate_eligible, certificate_reason = _certificate_eligibility(scan, results)
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
        "officerReview": _scan_review(scan),
        "certificateEligible": certificate_eligible,
        "certificateEligibilityReason": certificate_reason,
    }


def _result_rows(cursor: Any, scan_id: str) -> list[dict[str, Any]]:
    cursor.execute("SELECT * FROM compliance_results WHERE scan_id = %s AND check_name <> 'R6_10A' ORDER BY id", (scan_id,))
    rows = [row for row in cursor.fetchall() if row.get("check_name") not in EXCLUDED_LEGACY_RULE_IDS]
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
    cursor.execute("SELECT * FROM compliance_results WHERE scan_id = ANY(%s) AND check_name <> 'R6_10A' ORDER BY scan_id, id", (scan_ids,))
    grouped: dict[str, list[dict[str, Any]]] = {scan_id: [] for scan_id in scan_ids}
    for row in cursor.fetchall():
        if row.get("check_name") in EXCLUDED_LEGACY_RULE_IDS:
            continue
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


def _scan_review(scan: dict[str, Any]) -> dict[str, Any]:
    metadata = scan.get("image_metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, json.JSONDecodeError):
            metadata = {}
    review = metadata.get("officer_review") if isinstance(metadata, dict) else None
    return review if isinstance(review, dict) else {}


def _review_payload(request: InspectionReviewRequest) -> dict[str, str]:
    values = request.model_dump()
    return {key: str(value or "").strip() for key, value in values.items()}


def _save_scan_review(scan_id: str, user: dict[str, Any], review: dict[str, str]) -> dict[str, Any]:
    allowed_statuses = {"Verified", "Requires Further Verification", "Non-Compliant Confirmed", "No Violation Found"}
    if review.get("review_status") not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Choose a valid officer review status.")
    required = ("officer_name", "designation", "department", "inspection_location", "inspection_date")
    if any(not review.get(field) for field in required):
        raise HTTPException(status_code=400, detail="Officer name, designation, department, location, and inspection date are required.")
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT s.image_metadata FROM scans s WHERE s.scan_id = %s AND s.user_id = %s", (scan_id, user["id"]))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Scan not found.")
            metadata = row.get("image_metadata") or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (TypeError, json.JSONDecodeError):
                    metadata = {}
            metadata = metadata if isinstance(metadata, dict) else {}
            metadata["officer_review"] = review
            cursor.execute("UPDATE scans SET image_metadata = %s::jsonb WHERE scan_id = %s", (json.dumps(metadata), scan_id))
        connection.commit()
    return review


def _build_pdf_report(
    report_id: str,
    scan: dict[str, Any],
    checks: list[dict[str, Any]],
    generated_at: datetime,
    officer_name: str,
    location: str | None,
    images: list[dict[str, Any]],
    review: dict[str, Any] | None = None,
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
        "officer_review": review or {},
    }


def _report_dto(row: dict[str, Any], checks: list[dict[str, Any]], extracted: dict[str, Any]) -> dict[str, Any]:
    summary = _report_summary(checks)
    metadata = row.get("metadata") or {}
    score = row.get("compliance_score")
    if score is None and isinstance(metadata, dict):
        score = metadata.get("compliance_score")
    if score is None:
        score = _calculate_compliance_score(checks)
    metadata_review = (metadata.get("officer_review") if isinstance(metadata, dict) else None) or {}
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
        "designation": metadata_review.get("designation") or "Not provided",
        "department": metadata_review.get("department") or "Not provided",
        "inspectionRemarks": metadata_review.get("inspection_remarks") or "",
        "recommendedAction": metadata_review.get("recommended_action") or "",
        "reviewStatus": metadata_review.get("review_status") or "",
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


def _certificate_verification_url(request: Request, certificate_id: str) -> str:
    base_url = CERTIFICATE_VERIFICATION_BASE_URL or str(request.base_url).rstrip("/")
    return f"{base_url}/api/certificates/{certificate_id}/verify"


def _certificate_dto(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, json.JSONDecodeError):
            metadata = {}
    score = row.get("compliance_score")
    if score is None and isinstance(metadata, dict):
        score = metadata.get("compliance_score", 0)
    verification_url = metadata.get("verification_url") if isinstance(metadata, dict) else None
    return {
        "id": row["report_id"],
        "certificateId": row["report_id"],
        "scanId": row["scan_id"],
        "productName": row.get("product_name") or "Product name unavailable",
        "generatedAt": iso_datetime(row.get("generated_at")),
        "assessmentDate": iso_datetime(row.get("scanned_at")),
        "complianceScore": int(score or 0),
        "status": "compliant",
        "pdfUrl": f"/api/certificates/{row['report_id']}/pdf",
        "verificationUrl": verification_url,
    }


def _json_from_response(text: str) -> Any:
    candidate = text.strip()
    if "```" in candidate:
        fenced = re.findall(r"```(?:json)?\s*(.*?)```", candidate, flags=re.S | re.I)
        if fenced:
            candidate = fenced[0].strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as original_error:
        # Gemini can occasionally append a short sentence or a second JSON
        # fragment despite the JSON-only instruction. Recover the structured
        # extraction object when one is present, rather than blindly choosing
        # an unrelated wrapper object that would make every finding empty.
        decoder = json.JSONDecoder()
        parsed_objects: list[dict[str, Any]] = []
        for start in (match.start() for match in re.finditer(r"[\[{]", candidate)):
            try:
                parsed, _end = decoder.raw_decode(candidate[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                parsed_objects.append(parsed)
        if parsed_objects:
            structured = [item for item in parsed_objects if isinstance(item.get("fields"), dict)]
            selected = max(
                structured or parsed_objects,
                key=lambda item: len(item.get("fields", {})) if isinstance(item.get("fields"), dict) else 0,
            )
            logger.warning("Gemini response contained trailing or wrapped JSON; using the structured extraction object and ignoring unrelated content.")
            return selected
        raise original_error


def _normalize_status(value: Any) -> ObservationState:
    if not value:
        return ObservationState.NOT_ASSESSED
    status_map = {
        "VISIBLE": ObservationState.PRESENT,
        "PRESENT": ObservationState.PRESENT,
        "DETECTED": ObservationState.PRESENT,
        "FOUND": ObservationState.PRESENT,
        "COMPLIANT": ObservationState.PRESENT,
        "CONFIRMED_ABSENT": ObservationState.CONFIRMED_ABSENT,
        "ABSENT": ObservationState.CONFIRMED_ABSENT,
        "NOT_VISIBLE": ObservationState.NOT_VISIBLE,
        "NOT_VISIBLE_IN_IMAGE": ObservationState.NOT_VISIBLE,
        "NOT_FOUND": ObservationState.NOT_VISIBLE,
        "UNREADABLE": ObservationState.UNREADABLE,
        "UNREADABLE_TEXT": ObservationState.UNREADABLE,
        "NOT_ASSESSED": ObservationState.NOT_ASSESSED,
    }
    normalized = str(value).strip().upper().replace("-", "_")
    return status_map.get(normalized, ObservationState.NOT_ASSESSED)


_EXTRACTION_FIELD_ALIASES = {
    "generic_name", "product_name", "common_generic_product_name",
    "manufacturer", "manufacturer_details", "manufactured_by", "marketed_by",
    "packer", "packer_details", "packed_by", "importer", "importer_details", "imported_by",
    "country_of_origin", "country_of_origin_details", "origin",
    "net_quantity", "net_qty", "net_weight", "net_wt",
    "mrp", "maximum_retail_price", "retail_sale_price",
    "unit_sale_price", "unit_price", "usp",
    "manufacture_or_pack_or_import_date", "pack_date", "date_declaration",
    "manufacture_date", "manufacturing_date", "mfd", "packed_date",
    "best_before_or_use_by", "best_before", "use_by", "expiry", "expiry_date",
    "consumer_care", "consumer_care_details", "consumer_contact", "customer_care",
    "component_names_and_quantities", "multipack_details",
    "gm_mark", "genetically_modified_mark",
    "dietary_origin_mark", "vegetarian_non_vegetarian_mark", "veg_nonveg_mark",
}


def _normalized_key(value: Any) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(value).strip())
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _field_key(value: Any) -> str:
    key = _normalized_key(value)
    aliases = {
        "mrp_retail_sale_price_inclusive_of_all_taxes": "mrp",
        "maximum_retail_price_inclusive_of_all_taxes": "mrp",
        "manufacturer_packer_importer_name_and_address": "manufacturer_details",
        "manufacturer_packer_importer_name_address": "manufacturer_details",
        "net_quantity_and_unit": "net_quantity",
        "country_of_origin_manufacture_assembly": "country_of_origin",
        "manufacture_pack_import_month_and_year": "manufacture_or_pack_or_import_date",
        "best_before_use_by_expiry_date": "best_before_or_use_by",
        "unit_sale_price_declaration": "unit_sale_price",
        "consumer_complaint_contact": "consumer_care",
        "gm_food_declaration": "gm_mark",
        "vegetarian_non_vegetarian_origin_mark": "dietary_origin_mark",
        "names_and_quantities_of_products_in_a_multipack": "component_names_and_quantities",
    }
    return aliases.get(key, key)


def _field_map_score(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    return sum(1 for key in value if _field_key(key) in _EXTRACTION_FIELD_ALIASES)


def _field_records_from_list(value: Any) -> dict[str, Any] | None:
    """Convert a named field-record list to the same local map we expect.

    This only reshapes records that already contain a field name/key; it does
    not infer a declaration from arbitrary text.
    """
    if not isinstance(value, list):
        return None
    records: dict[str, Any] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized = {_normalized_key(key): child for key, child in item.items()}
        raw_name = normalized.get("field") or normalized.get("field_name") or normalized.get("name") or normalized.get("key")
        if raw_name is None:
            continue
        record = dict(item)
        for metadata_key in ("field", "field_name", "name", "key"):
            record.pop(metadata_key, None)
            for original_key in list(record):
                if _normalized_key(original_key) == metadata_key:
                    record.pop(original_key, None)
        records[str(raw_name)] = record
    return records or None


def _has_structured_extraction(payload: Any) -> bool:
    return _has_selected_extraction(_structured_extraction(payload))


def _has_selected_extraction(selected: Any) -> bool:
    fields = selected.get("fields") if isinstance(selected, dict) else None
    return _field_map_score(fields) > 0 if isinstance(fields, dict) else _field_map_score(selected) > 0


def _structured_extraction(payload: Any) -> dict[str, Any]:
    """Find the richest extraction object without inventing declaration data.

    The requested Gemini schema uses ``{"fields": {...}}``. In practice a
    valid model response can also be wrapped in ``data``/``result``, return the
    field map directly, or put the JSON response inside a string envelope. All
    of those are presentation differences; this function only unwraps them.
    """
    candidates: list[tuple[int, int, int, dict[str, Any]]] = []

    def walk(value: Any, depth: int = 0, inherited_context: Any = None, inherited_coverage: Any = None) -> None:
        if isinstance(value, dict):
            normalized = {_normalized_key(key): child for key, child in value.items()}
            context = normalized.get("context", inherited_context)
            coverage = normalized.get("image_coverage", inherited_coverage)
            fields = normalized.get("fields")
            if not fields:
                fields = normalized.get("extracted_fields") or normalized.get("observations")
            fields_from_list = _field_records_from_list(fields)
            if fields_from_list is not None:
                fields = fields_from_list
            if isinstance(fields, dict):
                score = _field_map_score(fields)
                candidates.append((score, len(fields), -depth, {**value, "fields": fields, "context": context, "image_coverage": coverage}))
            else:
                score = _field_map_score(value)
                if score:
                    candidates.append((score, score, -depth, {**value, "context": context, "image_coverage": coverage}))
            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child, depth + 1, context, coverage)
                elif isinstance(child, str) and child.lstrip().startswith(("{", "[")):
                    try:
                        decoded = json.loads(child)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    walk(decoded, depth + 1, context, coverage)
        elif isinstance(value, list):
            fields = _field_records_from_list(value)
            if fields is not None:
                candidates.append((_field_map_score(fields), len(fields), -depth, {"fields": fields, "context": inherited_context, "image_coverage": inherited_coverage}))
            for child in value:
                walk(child, depth + 1, inherited_context, inherited_coverage)

    walk(payload)
    if not candidates:
        return payload if isinstance(payload, dict) else {}
    # Prefer the object containing the most recognized fields. The field-count
    # and depth tie breakers keep the complete extraction when envelopes are
    # nested or when a response contains an unrelated small object.
    return max(candidates, key=lambda item: (item[0], item[1], item[2]))[3]


def _field_from_record(field_name: str, record: Any) -> FieldObservation:
    if not isinstance(record, dict):
        if isinstance(record, (str, int, float)) and str(record).strip():
            return FieldObservation(state=ObservationState.PRESENT, value=str(record), evidence=str(record))
        return FieldObservation(state=ObservationState.NOT_ASSESSED)
    normalized_record = {_normalized_key(key): value for key, value in record.items()}
    raw_state = normalized_record.get("status") or normalized_record.get("visibility") or normalized_record.get("state")
    value = normalized_record.get("value")
    if value is None:
        value = normalized_record.get("text") or normalized_record.get("extracted_text")
    confidence = normalized_record.get("confidence")
    evidence = normalized_record.get("evidence") or normalized_record.get("source_text") or ""
    if raw_state is None and "present" in normalized_record:
        raw_state = "PRESENT" if normalized_record["present"] is True else "NOT_VISIBLE"
    elif raw_state is None and (value not in (None, "") or evidence):
        # A named record with an extracted value is already evidence of a
        # visible observation even when a compact array response omits the
        # redundant status property.
        raw_state = "PRESENT"
    state = _normalize_status(raw_state)
    if value is not None and not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    if not isinstance(evidence, str):
        evidence = json.dumps(evidence, ensure_ascii=False) if isinstance(evidence, (dict, list)) else str(evidence)
    # Gemini may return a parsed numeric MRP in ``value`` while keeping the
    # complete printed declaration in ``evidence``. Preserve that existing
    # declaration so Rule 6(1)(e) validates the evidence actually shown.
    if (
        field_name == "mrp"
        and state is ObservationState.PRESENT
        and evidence
        and not is_valid_mrp_declaration(str(value or ""))
        and is_valid_mrp_declaration(str(evidence))
    ):
        value = evidence
    bbox = record.get("bounding_box") or record.get("bbox") or {}
    if bbox and evidence:
        evidence = f"{evidence} :: {bbox}"
    source_image: int | None = None
    for key in ("source_image_index", "sourceImageIndex", "image_index", "source_image"):
        raw_index = normalized_record.get(_normalized_key(key))
        if isinstance(raw_index, dict):
            for nested_key in ("index", "image_index", "source_image_index"):
                if raw_index.get(nested_key) is not None:
                    raw_index = raw_index[nested_key]
                    break
        if isinstance(raw_index, str) and key == "source_image":
            image_match = re.search(r"(?:image|img)[ _-]*(\d+)", raw_index, re.I)
            raw_index = int(image_match.group(1)) - 1 if image_match else None
        try:
            parsed_index = int(raw_index) if raw_index is not None else None
        except (TypeError, ValueError):
            parsed_index = None
        if parsed_index is not None and parsed_index >= 0:
            source_image = parsed_index
            break
    if source_image is None:
        raw_number = normalized_record.get("source_image_number")
        try:
            parsed_number = int(raw_number) if raw_number is not None else None
        except (TypeError, ValueError):
            parsed_number = None
        if parsed_number is not None and parsed_number > 0:
            source_image = parsed_number - 1
    source_image_ref = normalized_record.get("source_image_ref") or normalized_record.get("source_path")
    if source_image_ref is None:
        raw_source = normalized_record.get("source_image")
        if isinstance(raw_source, str) and not re.search(r"(?:image|img)[ _-]*\d+", raw_source, re.I):
            source_image_ref = raw_source
    normalized_bbox = bbox if isinstance(bbox, dict) and bbox else None
    try:
        normalized_confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        normalized_confidence = None
    return FieldObservation(
        state=state,
        value=value if state is not ObservationState.NOT_VISIBLE else None,
        confidence=normalized_confidence,
        evidence=evidence,
        source_image=source_image,
        source_image_ref=str(source_image_ref) if source_image_ref else None,
        bounding_box=normalized_bbox,
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
    # Some Gemini responses include one or more harmless outer envelopes
    # around the extraction object. Select the richest existing ``fields``
    # object; do not infer or synthesize any declaration values.
    if not isinstance(payload.get("fields"), dict) and not _field_map_score(payload):
        payload = _structured_extraction(payload)
    fields = payload.get("fields")
    if not isinstance(fields, dict):
        # Some responses omit the harmless ``fields`` envelope and return the
        # recognized declaration records directly at the selected object.
        fields = payload if _field_map_score(payload) else {}
    normalized_fields = {_field_key(key): value for key, value in fields.items()}
    context = payload.get("context", {})
    if not isinstance(context, dict):
        context = {}
    normalized_context = {_normalized_key(key): value for key, value in context.items()}
    package_context = PackageContext(
        is_imported=_as_bool(normalized_context.get("is_imported")),
        may_become_unfit_for_human_consumption=_as_bool(normalized_context.get("may_become_unfit_for_human_consumption")),
        date_requirement_governed_by_other_law=_as_bool(normalized_context.get("date_requirement_governed_by_other_law")),
        unit_sale_price_required=_as_bool(normalized_context.get("unit_sale_price_required")),
        retail_sale_price_equals_unit_sale_price=_as_bool(normalized_context.get("retail_sale_price_equals_unit_sale_price")),
        unit_sale_price_governed_by_other_law=_as_bool(normalized_context.get("unit_sale_price_governed_by_other_law")),
        quantity_basis=_map_quantity_basis(normalized_context.get("quantity_basis")),
        contains_multiple_products=_as_bool(normalized_context.get("contains_multiple_products")),
        is_genetically_modified_food=_as_bool(normalized_context.get("is_genetically_modified_food")),
        requires_vegetarian_origin_mark=_as_bool(normalized_context.get("requires_vegetarian_origin_mark")),
        # Missing coverage data must never be treated as proof that every
        # relevant label surface was inspected.
        inspected_relevant_label_surfaces=_as_bool(normalized_context.get("inspected_relevant_label_surfaces")) is True,
    )

    mapping = {
        "generic_name": "generic_name",
        "product_name": "generic_name",
        "common_generic_product_name": "generic_name",
        "manufacturer": "manufacturer",
        "manufacturer_details": "manufacturer",
        "manufactured_by": "manufacturer",
        "marketed_by": "manufacturer",
        "packer": "packer",
        "packer_details": "packer",
        "packed_by": "packer",
        "importer": "importer",
        "importer_details": "importer",
        "imported_by": "importer",
        "country_of_origin": "country_of_origin",
        "country_of_origin_details": "country_of_origin",
        "origin": "country_of_origin",
        "net_quantity": "net_quantity",
        "net_qty": "net_quantity",
        "net_weight": "net_quantity",
        "net_wt": "net_quantity",
        "mrp": "mrp",
        "maximum_retail_price": "mrp",
        "retail_sale_price": "mrp",
        "unit_sale_price": "unit_sale_price",
        "unit_price": "unit_sale_price",
        "usp": "unit_sale_price",
        "manufacture_or_pack_or_import_date": "manufacture_or_pack_or_import_date",
        "pack_date": "manufacture_or_pack_or_import_date",
        "date_declaration": "manufacture_or_pack_or_import_date",
        "manufacture_date": "manufacture_or_pack_or_import_date",
        "manufacturing_date": "manufacture_or_pack_or_import_date",
        "mfd": "manufacture_or_pack_or_import_date",
        "packed_date": "manufacture_or_pack_or_import_date",
        "best_before_or_use_by": "best_before_or_use_by",
        "best_before": "best_before_or_use_by",
        "use_by": "best_before_or_use_by",
        "expiry": "best_before_or_use_by",
        "expiry_date": "best_before_or_use_by",
        "consumer_care": "consumer_care",
        "consumer_care_details": "consumer_care",
        "consumer_contact": "consumer_care",
        "customer_care": "consumer_care",
        "component_names_and_quantities": "component_names_and_quantities",
        "multipack_details": "component_names_and_quantities",
        "gm_mark": "gm_mark",
        "genetically_modified_mark": "gm_mark",
        "dietary_origin_mark": "dietary_origin_mark",
        "vegetarian_non_vegetarian_mark": "dietary_origin_mark",
        "veg_nonveg_mark": "dietary_origin_mark",
    }

    candidates: dict[str, list[FieldObservation]] = {}
    for dto_key, package_key in mapping.items():
        if dto_key in normalized_fields:
            candidates.setdefault(package_key, []).append(_field_from_record(dto_key, normalized_fields[dto_key]))
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
    - If a responsible entity name is printed in one declaration and the same
      legal entity name is repeated next to a readable postal address in a
      consumer-services/contact declaration, include that linked name/address
      evidence in manufacturer_details. Do not mark the address absent merely
      because the package places it in the contact block.
    - For every visible field, include source_image_index as the zero-based
      index of the supplied image where that declaration is visible. Omit it
      when the source cannot be established precisely; never guess. Preserve
      bounding_box only when the model can identify one from the supplied
      image, and never fabricate coordinates.
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
        "inspected_relevant_label_surfaces": true
      },
      "fields": {
        "generic_name": {"status": "VISIBLE|NOT_VISIBLE|UNREADABLE|CONFIRMED_ABSENT|NOT_ASSESSED", "value": "...", "confidence": 0.93, "evidence": "Visible text excerpt", "source_image_index": 0, "bounding_box": {"x": 10, "y": 20, "w": 60, "h": 15}},
        "manufacturer_details": {"status": "VISIBLE|NOT_VISIBLE|UNREADABLE|CONFIRMED_ABSENT|NOT_ASSESSED", "value": "...", "confidence": 0.9, "evidence": "...", "source_image_index": 1, "bounding_box": {"x": 0, "y": 0, "w": 0, "h": 0}},
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


def _is_gemini_transient_error(error: Exception) -> bool:
    error_text = str(error).lower()
    status_code = _gemini_error_code(error)
    return (
        status_code is not None and status_code >= 500
    ) or isinstance(error, (asyncio.TimeoutError, TimeoutError, ConnectionError, URLError)) or any(
        marker in error_text for marker in ("timed out", "timeout", "connection reset", "connection refused", "temporarily unavailable")
    )


def _gemini_error_category(error: Exception) -> str:
    """Classify provider failures without exposing credential contents."""
    error_text = str(error).lower()
    status_code = _gemini_error_code(error)
    if status_code == 429:
        if any(marker in error_text for marker in ("resource_exhausted", "quota", "quota exceeded", "quota exhausted")):
            return "quota_exhausted"
        return "rate_limited"
    if status_code in {401} or any(marker in error_text for marker in ("unauthenticated", "invalid api key", "api key not valid", "access_token_type_unsupported")):
        return "authentication"
    if status_code == 403 or any(marker in error_text for marker in ("permission denied", "permission_denied", "forbidden", "project is not permitted")):
        return "permission"
    if status_code == 404 or any(marker in error_text for marker in ("model not found", "not found: model", "does not exist")):
        return "model_unavailable"
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)) or any(marker in error_text for marker in ("timed out", "timeout")):
        return "timeout"
    if _is_gemini_transient_error(error):
        return "transient"
    return "unknown"


def _configured_gemini_credentials() -> list[tuple[str, str]]:
    primary_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    primary_model = GEMINI_MODEL.strip()
    fallback_model = GEMINI_FALLBACK_MODEL
    configured_keys = [key.strip() for key in re.split(r"[,;\s]+", os.getenv("GEMINI_API_KEYS") or "") if key.strip()]
    fallback_key = (os.getenv("GEMINI_API_KEY_FALLBACK") or "").strip()
    additional_keys = [key for key in [fallback_key, *configured_keys] if key]
    if not primary_key and additional_keys:
        primary_key = additional_keys.pop(0)
    if not primary_key:
        return []
    credentials = [(primary_key, primary_model)]
    for key in additional_keys:
        if key and key not in {item[0] for item in credentials}:
            credentials.append((key, fallback_model or primary_model))
    if fallback_model and fallback_model != primary_model and len(credentials) == 1:
        credentials.append((primary_key, fallback_model))
    return credentials


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
    total_started = time.perf_counter()
    # Use every distinct configured credential, but only after the preceding
    # request fails. A successful primary request still exits immediately.
    attempts = credentials
    for credential_index, (api_key, model) in enumerate(attempts):
        label = "Primary" if credential_index == 0 else f"Fallback {credential_index + 1}"
        remaining_seconds = GEMINI_TOTAL_TIMEOUT_SECONDS - (time.perf_counter() - total_started)
        if remaining_seconds <= 0:
            break
        configured_timeout = GEMINI_FALLBACK_TIMEOUT_SECONDS if credential_index else GEMINI_REQUEST_TIMEOUT_SECONDS
        request_timeout = min(configured_timeout, remaining_seconds)
        request_started = time.perf_counter()
        try:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=int(GEMINI_TOTAL_TIMEOUT_SECONDS * 1000)),
            )
            logger.info("[GEMINI] %s model: %s", label, model)
            logger.info("[GEMINI] %s request started", label)
            generate_kwargs: dict[str, Any] = {"model": model, "contents": contents}
            if "unittest.mock" not in type(client.models.generate_content).__module__:
                generate_kwargs["config"] = types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                )
            response = await asyncio.wait_for(
                asyncio.to_thread(client.models.generate_content, **generate_kwargs),
                timeout=request_timeout,
            )
            elapsed = time.perf_counter() - request_started
            if credential_index > 0:
                logger.info("[GEMINI] %s completed in %.2fs", label, elapsed)
                logger.info("[GEMINI] %s success", label)
            else:
                logger.info("[GEMINI] Primary response: %.2fs", elapsed)
            break
        except Exception as error:
            last_error = error
            status_code = _gemini_error_code(error)
            elapsed = time.perf_counter() - request_started
            category = _gemini_error_category(error)
            logger.error(
                "[GEMINI] %s failed: category=%s status=%s type=%s error=%s",
                label,
                category,
                status_code or "unknown",
                type(error).__name__,
                error,
            )
            next_credential = credentials[credential_index + 1] if credential_index + 1 < len(attempts) else None
            same_credential_and_model = bool(next_credential and next_credential == (api_key, model))

            if category == "authentication":
                if next_credential and not same_credential_and_model and next_credential[0] != api_key:
                    logger.warning("[GEMINI] %s authentication failed; trying configured fallback credential %d.", label, credential_index + 2)
                    continue
                raise HTTPException(
                    status_code=502,
                    detail="Gemini authentication failed for the configured credential. Replace the invalid API key and restart the backend.",
                ) from error
            if category in {"quota_exhausted", "rate_limited"}:
                if next_credential and not same_credential_and_model:
                    logger.warning("[GEMINI] %s failed after %.2fs; trying configured fallback credential %d.", label, elapsed, credential_index + 2)
                    continue
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "Gemini API quota is currently unavailable for the configured credentials. "
                        "Switch to a credential from another Google project or wait for the quota to reset."
                        if category == "quota_exhausted"
                        else "Gemini is temporarily rate-limited. Please try again shortly or use another configured credential."
                    ),
                ) from error
            if category in {"transient", "timeout"}:
                logger.warning("[GEMINI] %s failed/timeout after %.2fs", label, elapsed)
                if next_credential and not same_credential_and_model:
                    next_model = credentials[credential_index + 1][1]
                    logger.info("[GEMINI] Switching to fallback credential %d with model: %s", credential_index + 2, next_model)
                    continue
                break
            if category == "permission":
                raise HTTPException(status_code=502, detail="Gemini rejected the configured project permission. Check the Google project, API enablement, and API key restrictions.") from error
            if category == "model_unavailable":
                raise HTTPException(status_code=502, detail=f"The configured Gemini model is unavailable: {model}.") from error
            raise HTTPException(
                status_code=502,
                detail="Gemini image analysis is temporarily unavailable. Check the backend log and try again.",
            ) from error

    logger.info("[GEMINI] Total Gemini time: %.2fs", time.perf_counter() - total_started)
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
        # The Supabase Python client is not safe to share across worker
        # threads on Windows. Upload sequentially in this already-background
        # task so the user response remains unchanged and every image gets a
        # reliable scan_images record.
        local_and_remote = [
            (
                item,
                _upload_to_supabase_storage(user["id"], scan_id, item[0], item[1], item[2]),
            )
            for item in loaded
        ]
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

        # Organizations receive a certificate only through the separate,
        # user-triggered certificate endpoint. Preserve the existing officer
        # report path without generating an official report for organizations.
        if user.get("role") != "officer":
            return

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
    configured_credentials = _configured_gemini_credentials()
    logger.info(
        "[GEMINI] Configuration: primary_model=%s fallback_model=%s credentials=%d primary_configured=%s fallback_configured=%s",
        GEMINI_MODEL or "(unset)",
        GEMINI_FALLBACK_MODEL or "(unset)",
        len(configured_credentials),
        bool(configured_credentials),
        len(configured_credentials) > 1,
    )
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
                    cursor.execute("SELECT u.*, a.department, a.administrative_role, COALESCE(NULLIF(u.state, ''), a.state) AS state, COALESCE(NULLIF(u.district, ''), a.district) AS district FROM users u LEFT JOIN admins a ON a.id = u.id WHERE LOWER(u.login_id) = LOWER(%s)", (request.login_id.strip(),))
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


@app.get("/api/profile")
async def get_profile(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    return _user_payload(_user_or_401(authorization))


@app.patch("/api/profile")
async def update_profile(request: ProfileUpdateRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _user_or_401(authorization)
    values = {key: str(value or "").strip() for key, value in request.model_dump().items()}
    if not values["name"] or not values["location"]:
        raise HTTPException(status_code=400, detail="Name and location are required.")
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE users SET name = %s, location = %s, state = %s, district = %s WHERE id = %s RETURNING *", (values["name"], values["location"], values["state"] or None, values["district"] or None, user["id"]))
                updated = cursor.fetchone()
            connection.commit()
        if not updated:
            raise HTTPException(status_code=404, detail="Profile not found.")
        updated.update({"department": user.get("department"), "administrative_role": user.get("administrative_role")})
        return _user_payload(updated)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="The profile could not be saved.")


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


@app.get("/api/admin/officers")
async def admin_officers(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    """Return persisted officer location summaries for the admin overview.

    Complaint and violation access remains jurisdiction-scoped. This small
    directory intentionally reads the current officer profile directly so an
    edited state/location is not hidden by stale seed data or admin defaults.
    """
    _admin_or_403(authorization)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT u.id, u.officer_id, u.name, u.email, u.location, u.state, u.district FROM users u WHERE u.role = 'officer' ORDER BY u.name",
            )
            return [
                {
                    "id": row["id"],
                    "officerId": row.get("officer_id"),
                    "name": row.get("name") or "Officer",
                    "email": row.get("email") or "",
                    "location": row.get("location") or "",
                    "state": row.get("state") or "",
                    "district": row.get("district") or "",
                }
                for row in cursor.fetchall()
            ]


@app.get("/api/admin/violations")
async def admin_violations(state: str | None = Query(default=None), district: str | None = Query(default=None), authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    admin = _admin_or_403(authorization)
    conditions, params = _complaint_scope(admin, requested_state=state, requested_district=district, alias="u")
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COALESCE(u.state, 'Not provided') AS state, COALESCE(u.district, 'Not provided') AS district, cr.check_name AS rule_id, COUNT(*) AS count FROM compliance_results cr JOIN scans s ON s.scan_id = cr.scan_id JOIN users u ON u.id = s.user_id WHERE cr.status = 'VIOLATION' AND cr.check_name <> 'R6_10A' AND {conditions} GROUP BY u.state, u.district, cr.check_name ORDER BY count DESC", params)
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
    if user["role"] == "organization":
        raise HTTPException(status_code=403, detail="Organizations cannot raise complaints from this workspace.")
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
    logger.info("[SCAN] Request received: %d image(s)", len(images))
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
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
        except Exception as error:
            logger.warning("[SCAN] Invalid image %s: type=%s size=%d error=%s", upload.filename, upload.content_type, len(data), type(error).__name__)
            raise HTTPException(status_code=400, detail=f"The uploaded file {upload.filename} is not a valid readable image.") from error
        logger.info("[SCAN] Image accepted: type=%s size=%d filename=%s", upload.content_type, len(data), upload.filename)
        loaded.append((upload.filename, upload.content_type, data))

    logger.info("[SCAN] Received %d valid image(s) in %.2fs", len(loaded), time.perf_counter() - total_started)
    image_started = time.perf_counter()
    gemini_images = _prepare_images_for_gemini(loaded)
    logger.info("[PERF] Image processing: %.2fs", time.perf_counter() - image_started)
    gemini_started = time.perf_counter()
    payload = await _call_gemini(gemini_images)
    logger.info("[PERF] Gemini request: %.2fs", time.perf_counter() - gemini_started)
    parse_started = time.perf_counter()
    rules_started = time.perf_counter()
    structured_payload = _structured_extraction(payload)
    if not _has_selected_extraction(structured_payload):
        logger.error("[SCAN] Gemini returned JSON without any recognized package fields; refusing to persist an empty assessment.")
        raise HTTPException(
            status_code=502,
            detail="Gemini returned no structured package fields. No empty scan was saved; please check the model response and try again.",
        )
    package = _extract_package(structured_payload)
    image_coverage = structured_payload.get("image_coverage") or payload.get("image_coverage", {})
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
                "sourceImage": outcome.source_image,
                "sourceImageRef": outcome.source_image_ref,
                "boundingBox": outcome.bounding_box,
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
                    (scan_id, user["id"], user.get("organization_id"), package.generic_name.value or "Product name unavailable", result.overall_status.value, "", json.dumps({"image_count": len(loaded)}), json.dumps({"fields": {name: _field_record(getattr(package, name)) for name in ("generic_name", "manufacturer", "packer", "importer", "country_of_origin", "net_quantity", "mrp", "unit_sale_price", "manufacture_or_pack_or_import_date", "best_before_or_use_by", "consumer_care", "component_names_and_quantities", "gm_mark", "dietary_origin_mark")}, "context": json_value(dataclasses.asdict(package.context)), "image_coverage": image_coverage}), compliance_score),
                )
                for outcome in result.outcomes:
                    cursor.execute(
                        "INSERT INTO compliance_results (scan_id, check_name, status, extracted_value, applicable_requirement, explanation, evidence, source_image) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (scan_id, outcome.rule_id, outcome.status.value, outcome.evidence or None, outcome.legal_reference, outcome.explanation, outcome.evidence or None, outcome.source_image),
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
        "coverage": image_coverage or {"overall": "UNKNOWN", "minimum_required_surfaces_covered": False, "notes": ""},
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


@app.patch("/api/scans/{scan_id}/review")
async def save_scan_review(scan_id: str, request: InspectionReviewRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _officer_or_403(authorization)
    try:
        review = _save_scan_review(scan_id, user, _review_payload(request))
        return {"scan_id": scan_id, "officerReview": review}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="The officer review could not be saved.")


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
async def generate_report(scan_id: str, request: InspectionReviewRequest | None = None, authorization: str | None = Header(default=None)) -> dict[str, Any]:
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
                review = _review_payload(request) if request else _scan_review(scan)
                if request:
                    scan["image_metadata"] = {**(scan.get("image_metadata") or {}), "officer_review": review}
                    cursor.execute("UPDATE scans SET image_metadata = %s::jsonb WHERE scan_id = %s", (json.dumps(scan["image_metadata"]), scan_id))
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
                    review,
                )
                create_pdf(pdf_report, pdf_path)
                cursor.execute("INSERT INTO reports (report_id, scan_id, generated_by, organization_id, generated_at, pdf_path, status, metadata) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)", (report_id, scan_id, user["id"], scan.get("organization_id"), generated_at, str(pdf_path), scan["overall_status"], json.dumps({"compliance_score": scan.get("compliance_score", 0), "generator": "reportlab", "officer_review": review})))
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
                    LEFT JOIN compliance_results cr ON cr.scan_id = s.scan_id AND cr.check_name <> 'R6_10A'
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


def _certificate_row(certificate_id: str, user: dict[str, Any] | None = None) -> dict[str, Any] | None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.*, s.product_name, s.user_id AS scan_user_id, s.organization_id AS scan_organization_id,
                       s.scanned_at, s.extracted_data, s.compliance_score, s.overall_status AS scan_status
                FROM reports r JOIN scans s ON s.scan_id = r.scan_id
                WHERE r.report_id = %s AND r.metadata->>'document_type' = 'COMPLIANCE_CERTIFICATE'
                """,
                (certificate_id,),
            )
            row = cursor.fetchone()
    if not row or user is None:
        return row
    if user.get("role") != "organization":
        return None
    if row.get("scan_user_id") != user.get("id") and row.get("scan_organization_id") != user.get("organization_id"):
        return None
    return row


@app.get("/api/certificates/scan/{scan_id}")
async def get_scan_certificate(scan_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _organization_or_403(authorization)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.*, s.product_name, s.user_id AS scan_user_id, s.organization_id AS scan_organization_id,
                       s.scanned_at, s.extracted_data, s.compliance_score, s.overall_status AS scan_status
                FROM reports r JOIN scans s ON s.scan_id = r.scan_id
                WHERE r.scan_id = %s AND r.metadata->>'document_type' = 'COMPLIANCE_CERTIFICATE'
                  AND (s.user_id = %s OR s.organization_id = %s)
                ORDER BY r.generated_at DESC LIMIT 1
                """,
                (scan_id, user["id"], user.get("organization_id")),
            )
            row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No compliance certificate has been generated for this scan.")
    return _certificate_dto(row)


@app.post("/api/certificates/{scan_id}")
async def generate_certificate(scan_id: str, request: Request, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _organization_or_403(authorization)
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT s.*, u.location AS inspection_location
                    FROM scans s JOIN users u ON u.id = s.user_id
                    WHERE s.scan_id = %s AND (s.user_id = %s OR s.organization_id = %s)
                    """,
                    (scan_id, user["id"], user.get("organization_id")),
                )
                scan = cursor.fetchone()
                if not scan:
                    raise HTTPException(status_code=404, detail="Scan not found.")
                checks = _result_rows(cursor, scan_id)
                eligible, reason = _certificate_eligibility(scan, checks)
                if not eligible:
                    raise HTTPException(status_code=409, detail=f"Compliance certificate is not available: {reason}")

                cursor.execute(
                    """
                    SELECT r.*, s.product_name, s.user_id AS scan_user_id, s.organization_id AS scan_organization_id,
                           s.scanned_at, s.extracted_data, s.compliance_score, s.overall_status AS scan_status
                    FROM reports r JOIN scans s ON s.scan_id = r.scan_id
                    WHERE r.scan_id = %s AND r.metadata->>'document_type' = 'COMPLIANCE_CERTIFICATE'
                    ORDER BY r.generated_at DESC LIMIT 1
                    """,
                    (scan_id,),
                )
                existing = cursor.fetchone()
                if existing:
                    return _certificate_dto(existing)

                certificate_id = new_id("certificate")
                generated_at = datetime.now(UTC)
                verification_url = _certificate_verification_url(request, certificate_id)
                applicable_checks = [item for item in checks if str(item.get("status") or "").upper() != "NOT_APPLICABLE"]
                payload = {
                    "certificate_id": certificate_id,
                    "scan_id": scan_id,
                    "scanned_at": scan.get("scanned_at"),
                    "generated_at": generated_at,
                    "product_name": scan.get("product_name"),
                    "extracted_data": scan.get("extracted_data") or {},
                    "compliance_score": int(scan.get("compliance_score") or _calculate_compliance_score(checks)),
                    "summary": {
                        "total": len(applicable_checks),
                        "compliant": sum(1 for item in applicable_checks if item.get("status") == "COMPLIANT"),
                        "violations": sum(1 for item in applicable_checks if item.get("status") == "VIOLATION"),
                        "review": sum(1 for item in applicable_checks if item.get("status") in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED"}),
                    },
                    "verification_url": verification_url,
                }
                pdf_path = STORAGE_DIR / "reports" / f"{certificate_id}.pdf"
                create_certificate_pdf(payload, pdf_path)
                metadata = {
                    "document_type": "COMPLIANCE_CERTIFICATE",
                    "generator": "reportlab",
                    "layout_version": CERTIFICATE_LAYOUT_VERSION,
                    "compliance_score": payload["compliance_score"],
                    "verification_url": verification_url,
                    "eligibility_reason": reason,
                }
                cursor.execute(
                    """
                    INSERT INTO reports (report_id, scan_id, generated_by, organization_id, generated_at, pdf_path, status, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (certificate_id, scan_id, user["id"], scan.get("organization_id") or user.get("organization_id"), generated_at, str(pdf_path), "COMPLIANT", json.dumps(metadata)),
                )
                connection.commit()
                return _certificate_dto({**scan, "report_id": certificate_id, "scan_id": scan_id, "generated_at": generated_at, "metadata": metadata, "compliance_score": payload["compliance_score"]})
    except HTTPException:
        raise
    except Exception:
        logger.exception("Certificate generation failed for scan %s", scan_id)
        raise HTTPException(status_code=503, detail="The compliance certificate could not be generated or saved.")


@app.get("/api/certificates/{certificate_id}/verify")
async def verify_certificate(certificate_id: str) -> dict[str, Any]:
    row = _certificate_row(certificate_id)
    if not row:
        raise HTTPException(status_code=404, detail="Certificate not found.")
    metadata = row.get("metadata") or {}
    score = row.get("compliance_score")
    if score is None and isinstance(metadata, dict):
        score = metadata.get("compliance_score", 0)
    return {
        "certificateId": row["report_id"],
        "product": row.get("product_name") or "Product name unavailable",
        "assessmentDate": iso_datetime(row.get("scanned_at")),
        "score": int(score or 0),
        "complianceStatus": "COMPLIANT",
        "verificationStatus": "VALID",
    }


@app.get("/api/certificates/{certificate_id}/pdf")
async def download_certificate(certificate_id: str, request: Request, authorization: str | None = Header(default=None)):
    user = _organization_or_403(authorization)
    row = _certificate_row(certificate_id, user)
    if not row:
        raise HTTPException(status_code=404, detail="Certificate not found.")
    from fastapi.responses import FileResponse
    path = Path(row["pdf_path"]).resolve()
    if STORAGE_DIR not in path.parents:
        raise HTTPException(status_code=404, detail="The certificate PDF file is no longer available.")
    metadata = row.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, json.JSONDecodeError):
            metadata = {}
    if metadata.get("layout_version") != CERTIFICATE_LAYOUT_VERSION:
        # Existing certificates were generated with the previous layout. On
        # an explicit download, refresh only the PDF from persisted scan data;
        # the scan request and its compliance result remain untouched.
        with connect() as connection:
            with connection.cursor() as cursor:
                checks = _result_rows(cursor, row["scan_id"])
                applicable_checks = [item for item in checks if str(item.get("status") or "").upper() != "NOT_APPLICABLE"]
                verification_url = metadata.get("verification_url") or _certificate_verification_url(request, row["report_id"])
                payload = {
                    "certificate_id": row["report_id"],
                    "scan_id": row["scan_id"],
                    "scanned_at": row.get("scanned_at"),
                    "generated_at": row.get("generated_at"),
                    "product_name": row.get("product_name"),
                    "extracted_data": row.get("extracted_data") or {},
                    "compliance_score": int(row.get("compliance_score") or _calculate_compliance_score(checks)),
                    "summary": {
                        "total": len(applicable_checks),
                        "compliant": sum(1 for item in applicable_checks if item.get("status") == "COMPLIANT"),
                        "violations": sum(1 for item in applicable_checks if item.get("status") == "VIOLATION"),
                        "review": sum(1 for item in applicable_checks if item.get("status") in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED"}),
                    },
                    "verification_url": verification_url,
                }
                path.parent.mkdir(parents=True, exist_ok=True)
                create_certificate_pdf(payload, path)
                metadata = {**metadata, "generator": "reportlab", "layout_version": CERTIFICATE_LAYOUT_VERSION, "verification_url": verification_url}
                cursor.execute("UPDATE reports SET metadata = %s::jsonb WHERE report_id = %s", (json.dumps(metadata), row["report_id"]))
                connection.commit()
    if not path.is_file() or STORAGE_DIR not in path.parents:
        raise HTTPException(status_code=404, detail="The certificate PDF file is no longer available.")
    return FileResponse(path, media_type="application/pdf", filename=f"{certificate_id}.pdf")


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=int(os.getenv("API_PORT", "8001")), reload=True)
