from __future__ import annotations

import json
import os
import re
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

from compliance_engine import (
    ComplianceEngine,
    ExtractedPackage,
    FieldObservation,
    ObservationState,
    PackageContext,
    QuantityBasis,
)

load_dotenv()

app = FastAPI(title="NIRIKSHA Package Compliance API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


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
    return FieldObservation(
        state=state,
        value=value if state is not ObservationState.NOT_VISIBLE else None,
        confidence=float(confidence) if confidence is not None else None,
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
        inspected_relevant_label_surfaces=bool(context.get("inspected_relevant_label_surfaces", True)),
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
    }

    extra_fields: dict[str, FieldObservation] = {}
    for dto_key, package_key in mapping.items():
        if dto_key in fields:
            extra_fields[package_key] = _field_from_record(dto_key, fields[dto_key])

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
        context=package_context,
    )
    return package


def _build_extraction_prompt() -> str:
    return """
    Extract only what is visible in the supplied package label images.

    Rules:
    - Do not invent missing text.
    - Do not mark a field as missing/violation simply because it is not visible in the image. Instead set status to NOT_VISIBLE.
    - If the text is visible but difficult to read, set status to UNREADABLE and provide the best readable text if available.
    - If a declaration is clearly absent on inspected surfaces, set status to CONFIRMED_ABSENT.
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
        "other_declarations": {"status": "NOT_VISIBLE", "value": null, "confidence": 0.0, "evidence": "No additional declarations visible."}
      }
    }
    """


async def _call_gemini(images: list[tuple[str, str, bytes]]) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is empty. Add your key to the project .env file before running the backend.")

    client = genai.Client(api_key=api_key)
    contents: list[Any] = []
    for filename, mime_type, data in images:
        contents.append(types.Part.from_bytes(data=data, mime_type=mime_type))
        contents.append(f"Image: {filename}\n")
    contents.append(_build_extraction_prompt())

    response = client.models.generate_content(model=GEMINI_MODEL, contents=contents)
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/scan")
async def scan_images(images: list[UploadFile] = File(...)) -> dict[str, Any]:
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
                "value": outcome.evidence or "No declaration observed",
                "reference": outcome.legal_reference,
                "explanation": outcome.explanation,
                "sourceImage": None,
            }
        )

    response = {
        "overall_status": result.overall_status.value,
        "checks": checks,
        "coverage": payload.get("image_coverage", {"overall": "UNKNOWN", "minimum_required_surfaces_covered": False, "notes": ""}),
        "summary": {
            "total_checks": len(checks),
            "compliant": sum(1 for item in checks if item["status"] == "COMPLIANT"),
            "violations": sum(1 for item in checks if item["status"] == "VIOLATION"),
            "review": sum(1 for item in checks if item["status"] in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED", "NOT_APPLICABLE"}),
        },
    }
    return response


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
