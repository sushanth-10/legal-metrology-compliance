from __future__ import annotations

import json
import os
import re
import dataclasses
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types

load_dotenv()

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

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


class LoginRequest(BaseModel):
    login_id: str
    password: str
    role: str | None = None


class RegisterRequest(BaseModel):
    login_id: str
    password: str
    name: str
    email: str | None = None
    role: str = "consumer"


def _user_or_401(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication is required.")
    user = user_from_token(authorization[7:].strip())
    if not user:
        raise HTTPException(status_code=401, detail="Your session is invalid or has expired. Please sign in again.")
    return user


def _officer_or_403(authorization: str | None) -> dict[str, Any]:
    user = _user_or_401(authorization)
    if user["role"] != "officer":
        raise HTTPException(status_code=403, detail="Only officers can generate or access official reports.")
    return user


def _field_record(observation: FieldObservation) -> dict[str, Any]:
    return {
        "status": observation.state.value,
        "value": observation.value,
        "confidence": observation.confidence,
        "evidence": observation.evidence,
    }


def _package_data(package: ExtractedPackage) -> dict[str, Any]:
    return json_value(dataclasses.asdict(package))


def _scan_dto(scan: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
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
    return {
        "id": scan["scan_id"],
        "scan_id": scan["scan_id"],
        "product": scan.get("product_name") or "Product name unavailable",
        "image": scan.get("image_ref") or "",
        "date": scanned_at,
        "status": {"COMPLIANT": "compliant", "VIOLATION": "non-compliant"}.get(scan["overall_status"], "needs-review"),
        "violations": len(violations),
        "declarations": declarations,
        "violationList": violations,
        "category": None,
        "location": None,
        "extractedData": extracted,
        "checks": results,
    }


def _result_rows(cursor: Any, scan_id: str) -> list[dict[str, Any]]:
    cursor.execute("SELECT * FROM compliance_results WHERE scan_id = %s ORDER BY id", (scan_id,))
    rows = cursor.fetchall()
    return [
        {
            "id": row["id"],
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


def _get_scan(scan_id: str, user: dict[str, Any]) -> dict[str, Any] | None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM scans WHERE scan_id = %s", (scan_id,))
            scan = cursor.fetchone()
            if not scan or (user["role"] != "officer" and scan["user_id"] != user["id"]):
                return None
            return _scan_dto(scan, _result_rows(cursor, scan_id))


def _report_dto(row: dict[str, Any], checks: list[dict[str, Any]], extracted: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "total": len(checks),
        "compliant": sum(1 for item in checks if item["status"] == "COMPLIANT"),
        "violations": sum(1 for item in checks if item["status"] == "VIOLATION"),
        "review": sum(1 for item in checks if item["status"] in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED", "NOT_APPLICABLE"}),
    }
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
    - Never infer net quantity from serving size, "per serve", portion size,
      nutrition facts, price, or unit sale price. Extract net_quantity only
      from a standalone net quantity declaration.
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
        "net_quantity": {"status": "VISIBLE", "value": "200 g", "confidence": 0.9, "evidence": "..."},
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


async def _call_gemini(images: list[tuple[str, str, bytes]]) -> dict[str, Any]:
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is empty. Add your key to the project .env file before running the backend.")

    client = genai.Client(api_key=api_key)
    contents: list[Any] = []
    for filename, mime_type, data in images:
        contents.append(types.Part.from_bytes(data=data, mime_type=mime_type))
        contents.append(f"Image: {filename}\n")
    contents.append(_build_extraction_prompt())

    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=contents)
    except Exception as error:
        error_text = str(error)
        if (
            getattr(error, "status_code", None) == 401
            or "UNAUTHENTICATED" in error_text
            or "ACCESS_TOKEN_TYPE_UNSUPPORTED" in error_text
        ):
            raise HTTPException(
                status_code=502,
                detail=(
                    "Gemini rejected GEMINI_API_KEY. Create a fresh Gemini API key in Google AI Studio, "
                    "replace GEMINI_API_KEY in the backend .env file, and restart Uvicorn."
                ),
            ) from error
        raise HTTPException(
            status_code=502,
            detail="Gemini image analysis is temporarily unavailable. Check the backend log and try again.",
        ) from error
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
        return {"status": "ok", "message": "PostgreSQL schema initialized and demo users ensured."}
    except Exception:
        raise HTTPException(status_code=503, detail="The PostgreSQL schema could not be initialized. Check DATABASE_URL and database availability.")


@app.post("/api/auth/login")
async def login(request: LoginRequest) -> dict[str, Any]:
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE login_id = %s", (request.login_id.strip(),))
                user = cursor.fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="The authentication service is unavailable. Check the PostgreSQL connection.")
    if not user or (request.role and user["role"] != request.role) or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    return {
        "token": create_token(user["id"]),
        "user": {"id": user["id"], "loginId": user["login_id"], "name": user["name"], "role": user["role"], "email": user.get("email") or "", "location": user.get("location") or "", "officerId": user.get("officer_id")},
    }


@app.post("/api/auth/register")
async def register(request: RegisterRequest) -> dict[str, Any]:
    if request.role != "consumer" or len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Only consumer registration is available and the password must be at least 8 characters.")
    try:
        user = create_user(request.login_id.strip(), request.password, request.name.strip(), request.role, request.email)
    except Exception as error:
        if "unique" in str(error).lower() or "duplicate" in str(error).lower():
            raise HTTPException(status_code=409, detail="That login ID is already registered.")
        raise HTTPException(status_code=503, detail="The account could not be saved. Check the PostgreSQL connection.")
    return {"token": create_token(user["id"]), "user": {"id": user["id"], "loginId": user["login_id"], "name": user["name"], "role": user["role"], "email": user.get("email") or "", "location": user.get("location") or "", "officerId": None}}


@app.post("/api/scan")
async def scan_images(images: list[UploadFile] = File(...), authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _user_or_401(authorization)
    if len(images) < 2:
        raise HTTPException(status_code=400, detail="At least 2 images are required for a scan.")

    loaded: list[tuple[str, str, bytes]] = []
    for upload in images:
        if not upload.filename:
            raise HTTPException(status_code=400, detail="Each uploaded file must include a name.")
        if not upload.content_type or not upload.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Unsupported file type for {upload.filename}. Please upload images only.")
        data = await upload.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"The uploaded file {upload.filename} is empty.")
        loaded.append((upload.filename, upload.content_type, data))

    payload = await _call_gemini(loaded)
    package = _extract_package(payload)
    result = ComplianceEngine().evaluate(package)

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
    image_filename = f"{uuid.uuid4().hex}{Path(loaded[0][0]).suffix.lower() or '.jpg'}"
    image_path = STORAGE_DIR / image_filename
    try:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(loaded[0][2])
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO scans (scan_id, user_id, product_name, overall_status, image_ref, image_metadata, extracted_data)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    """,
                    (scan_id, user["id"], package.generic_name.value or "Product name unavailable", result.overall_status.value,
                     f"/api/uploads/{image_filename}", json.dumps({"filename": loaded[0][0], "mime_type": loaded[0][1], "image_count": len(loaded)}),
                     json.dumps({"fields": {name: _field_record(getattr(package, name)) for name in ("generic_name", "manufacturer", "packer", "importer", "country_of_origin", "net_quantity", "mrp", "unit_sale_price", "manufacture_or_pack_or_import_date", "best_before_or_use_by", "consumer_care", "component_names_and_quantities", "gm_mark", "dietary_origin_mark", "ecommerce_country_of_origin_filter")}, "context": json_value(dataclasses.asdict(package.context)), "image_coverage": payload.get("image_coverage", {})})),
                )
                for outcome in result.outcomes:
                    cursor.execute(
                        """
                        INSERT INTO compliance_results (scan_id, check_name, status, extracted_value, applicable_requirement, explanation, evidence)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (scan_id, outcome.rule_id, outcome.status.value, outcome.evidence or None, outcome.legal_reference, outcome.explanation, outcome.evidence or None),
                    )
            connection.commit()
    except Exception:
        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(status_code=503, detail="The scan was analyzed but could not be saved. Check the PostgreSQL connection and storage permissions.")

    scan = _get_scan(scan_id, user)
    if not scan:
        raise HTTPException(status_code=503, detail="The scan was saved but could not be loaded.")
    return {
        "overall_status": result.overall_status.value,
        "checks": checks,
        "coverage": payload.get("image_coverage", {"overall": "UNKNOWN", "minimum_required_surfaces_covered": False, "notes": ""}),
        "summary": {"total_checks": len(checks), "compliant": sum(1 for item in checks if item["status"] == "COMPLIANT"), "violations": sum(1 for item in checks if item["status"] == "VIOLATION"), "review": sum(1 for item in checks if item["status"] in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED", "NOT_APPLICABLE"})},
        "scan": scan,
    }


@app.get("/api/uploads/{filename}")
async def uploaded_image(filename: str):
    from fastapi.responses import FileResponse
    path = (STORAGE_DIR / Path(filename).name).resolve()
    if path.parent != STORAGE_DIR or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(path)


@app.get("/api/scans")
async def list_scans(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    user = _user_or_401(authorization)
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                if user["role"] == "officer":
                    cursor.execute("SELECT * FROM scans ORDER BY scanned_at DESC")
                else:
                    cursor.execute("SELECT * FROM scans WHERE user_id = %s ORDER BY scanned_at DESC", (user["id"],))
                rows = cursor.fetchall()
                return [_scan_dto(row, _result_rows(cursor, row["scan_id"])) for row in rows]
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
                SELECT r.*, s.product_name, s.overall_status AS scan_status, s.scanned_at, s.extracted_data, u.name AS officer_name
                FROM reports r JOIN scans s ON s.scan_id = r.scan_id JOIN users u ON u.id = r.generated_by
                WHERE r.report_id = %s
                """, (report_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            if user["role"] != "officer" and row["generated_by"] != user["id"]:
                return None
            row["status"] = row["scan_status"]
            return _report_dto(row, _result_rows(cursor, row["scan_id"]), row.get("extracted_data") or {})


@app.post("/api/reports/{scan_id}")
async def generate_report(scan_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _officer_or_403(authorization)
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT s.*, u.name AS officer_name FROM scans s JOIN users u ON u.id = s.user_id WHERE s.scan_id = %s", (scan_id,))
                scan = cursor.fetchone()
                if not scan:
                    raise HTTPException(status_code=404, detail="Scan not found.")
                checks = _result_rows(cursor, scan_id)
                report_id = new_id("report")
                generated_at = datetime.now(UTC)
                row = {"report_id": report_id, "scan_id": scan_id, "product_name": scan.get("product_name"), "overall_status": scan["overall_status"], "scanned_at": scan["scanned_at"], "generated_at": generated_at, "officer_name": user["name"]}
                pdf_path = STORAGE_DIR / "reports" / f"{report_id}.pdf"
                pdf_report = {**row, "status": scan["overall_status"], "extracted_data": scan.get("extracted_data") or {}, "checks": checks, "summary": {"total_checks": len(checks), "compliant": sum(1 for item in checks if item["status"] == "COMPLIANT"), "violations": sum(1 for item in checks if item["status"] == "VIOLATION"), "review": sum(1 for item in checks if item["status"] in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED", "NOT_APPLICABLE"})}}
                create_pdf(pdf_report, pdf_path)
                cursor.execute("INSERT INTO reports (report_id, scan_id, generated_by, generated_at, pdf_path, status, metadata) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)", (report_id, scan_id, user["id"], generated_at, str(pdf_path), scan["overall_status"], json.dumps({"generator": "reportlab"})))
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
async def list_reports(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    user = _officer_or_403(authorization)
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT r.report_id FROM reports r ORDER BY r.generated_at DESC")
                ids = [row["report_id"] for row in cursor.fetchall()]
        return [item for report_id in ids if (item := _report_record(report_id, user))]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Reports are temporarily unavailable.")


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _officer_or_403(authorization)
    try:
        report = _report_record(report_id, user)
    except Exception:
        raise HTTPException(status_code=503, detail="The report could not be loaded.")
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@app.get("/api/reports/{report_id}/pdf")
async def download_report(report_id: str, authorization: str | None = Header(default=None)):
    user = _officer_or_403(authorization)
    from fastapi.responses import FileResponse
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pdf_path, product_name FROM reports r JOIN scans s ON s.scan_id = r.scan_id WHERE r.report_id = %s", (report_id,))
                row = cursor.fetchone()
        if not row:
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
