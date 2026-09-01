from __future__ import annotations

import html
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import BaseDocTemplate, Frame, Image, PageTemplate, Paragraph, Spacer, Table, TableStyle


NAVY = colors.HexColor("#123b66")
BLUE = colors.HexColor("#1d4e89")
LIGHT_BLUE = colors.HexColor("#eef5fc")
PALE_BLUE = colors.HexColor("#f7fbff")
LINE = colors.HexColor("#c7d5e3")
TEXT = colors.HexColor("#172b4d")
MUTED = colors.HexColor("#5b6f89")
GREEN = colors.HexColor("#16803c")
RED = colors.HexColor("#c62828")
AMBER = colors.HexColor("#b36b00")
DEFAULT_STYLE = ParagraphStyle("DefaultValue", fontName="Helvetica", fontSize=8.2, leading=10.2, textColor=TEXT)


def _raw(value: Any, fallback: str = "Not available") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _escape(value: Any, fallback: str = "Not available") -> str:
    return html.escape(_raw(value, fallback)).replace("\r\n", "\n").replace("\n", "<br/>")


def _paragraph(value: Any, style: ParagraphStyle | None = None, fallback: str = "Not available") -> Paragraph:
    return Paragraph(_escape(value, fallback), style or DEFAULT_STYLE)


def _format_datetime(value: Any) -> str:
    if value in (None, ""):
        return "Not available"
    if isinstance(value, (datetime, date)):
        return value.strftime("%d-%m-%Y %H:%M UTC") if isinstance(value, datetime) else value.isoformat()
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%d-%m-%Y %H:%M UTC")
    except ValueError:
        return text


def _field_value(fields: dict[str, Any], name: str) -> str:
    value = fields.get(name)
    if isinstance(value, dict):
        return _raw(value.get("value"))
    return "Not available"


def _confidence(value: Any) -> str:
    if value in (None, ""):
        return "N/A"
    try:
        number = float(value)
        return f"{number * 100:.0f}%" if number <= 1 else f"{number:.0f}%"
    except (TypeError, ValueError):
        return str(value)


def _normalized_status(value: Any) -> str:
    return _raw(value, "NOT_ASSESSED").upper().replace("-", "_")


def _status_label(value: Any) -> str:
    normalized = _normalized_status(value)
    if normalized == "VIOLATION":
        return "VIOLATION / NON-COMPLIANT"
    if normalized in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED"}:
        return "UNABLE TO VERIFY / REQUIRES REVIEW"
    if normalized == "COMPLIANT":
        return "COMPLIANT"
    return normalized.replace("_", " ")


def _status_color(value: Any) -> colors.Color:
    normalized = _normalized_status(value)
    if normalized == "COMPLIANT":
        return GREEN
    if normalized == "VIOLATION":
        return RED
    return AMBER


def _status_paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    color = _status_color(value).hexval()[2:]
    return Paragraph(f'<font color="#{color}"><b>{html.escape(_status_label(value))}</b></font>', style)


def _rule_id(check: dict[str, Any]) -> Any:
    explicit = check.get("rule_id")
    if explicit not in (None, ""):
        return explicit
    identifier = check.get("id")
    if isinstance(identifier, str) and not identifier.isdigit():
        return identifier
    return check.get("label") or identifier


def _image_source(source: Any) -> tuple[str, bytes | None]:
    if isinstance(source, dict):
        label = _raw(source.get("label"), "Evidence image")
        data = source.get("bytes")
        path = source.get("path")
    else:
        label = "Evidence image"
        data = None
        path = source
    if isinstance(data, bytearray):
        data = bytes(data)
    if not isinstance(data, bytes) and path:
        try:
            candidate = Path(str(path))
            if candidate.is_file():
                data = candidate.read_bytes()
        except OSError:
            data = None
    return label, data if isinstance(data, bytes) else None


def _scaled_image(data: bytes, max_width: float, max_height: float) -> Image | None:
    try:
        reader = ImageReader(BytesIO(data))
        width, height = reader.getSize()
        if width <= 0 or height <= 0:
            return None
        scale = min(max_width / width, max_height / height)
        return Image(BytesIO(data), width=width * scale, height=height * scale, hAlign="CENTER")
    except Exception:
        return None


def _section(title: str, style: ParagraphStyle, width: float) -> Table:
    return Table([[Paragraph(f"<b>{html.escape(title)}</b>", style)],], colWidths=[width], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("BOX", (0, 0), (-1, -1), 0.7, NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))


def _bordered_table(rows: list[list[Any]], widths: list[float], header: bool = False) -> Table:
    commands: list[tuple[Any, ...]] = [
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
        ])
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, splitByRow=1, hAlign="LEFT")
    table.setStyle(TableStyle(commands))
    return table


def _draw_page(canvas: Any, document: Any) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(1.2)
    canvas.line(document.leftMargin, height - 9 * mm, width - document.rightMargin, height - 9 * mm)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(document.leftMargin, 10 * mm, width - document.rightMargin, 10 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(document.leftMargin, 6.5 * mm, "NIRIKSHA - Automated compliance assessment")
    canvas.drawRightString(width - document.rightMargin, 6.5 * mm, f"Page {document.page}")
    canvas.restoreState()


def create_pdf(report: dict[str, Any], output_path: Path) -> None:
    """Create an A4 inspection report from the already-persisted scan result."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = A4
    margin = 15 * mm
    content_width = page_width - (2 * margin)

    base = getSampleStyleSheet()
    title = ParagraphStyle("ReportTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=NAVY, alignment=TA_CENTER, spaceAfter=2)
    subtitle = ParagraphStyle("ReportSubtitle", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=BLUE, alignment=TA_CENTER)
    brand = ParagraphStyle("Brand", parent=base["Title"], fontName="Helvetica-Bold", fontSize=17, leading=18, textColor=colors.white, alignment=TA_CENTER)
    section_text = ParagraphStyle("SectionText", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=9.5, leading=11, textColor=colors.white)
    label = ParagraphStyle("Label", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.7, leading=9.2, textColor=NAVY)
    body = ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=8.2, leading=10.2, textColor=TEXT)
    body_center = ParagraphStyle("BodyCenter", parent=body, alignment=TA_CENTER)
    small = ParagraphStyle("Small", parent=body, fontSize=7.2, leading=8.8)
    small_center = ParagraphStyle("SmallCenter", parent=small, alignment=TA_CENTER)
    rule_id_style = ParagraphStyle("RuleId", parent=small, fontSize=6.4, leading=7.8)
    table_header = ParagraphStyle("TableHeader", parent=small, fontName="Helvetica-Bold", textColor=NAVY, alignment=TA_CENTER)
    score = ParagraphStyle("Score", parent=base["Title"], fontName="Helvetica-Bold", fontSize=16, leading=18, textColor=NAVY, alignment=TA_CENTER)
    status = ParagraphStyle("Status", parent=small, fontName="Helvetica-Bold", alignment=TA_CENTER)
    disclaimer = ParagraphStyle("Disclaimer", parent=small, fontSize=7.5, leading=9.4, textColor=MUTED)
    line_style = ParagraphStyle("Line", parent=small, leading=10)

    class ReportDocument(BaseDocTemplate):
        pass

    document = ReportDocument(
        str(output_path), pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=14 * mm, bottomMargin=14 * mm,
        title="NIRIKSHA Legal Metrology Compliance Inspection Report", author="NIRIKSHA",
    )
    frame = Frame(document.leftMargin, document.bottomMargin, content_width, page_height - document.topMargin - document.bottomMargin, id="normal")
    document.addPageTemplates([PageTemplate(id="inspection", frames=[frame], onPage=_draw_page)])
    story: list[Any] = []

    report_id = report.get("report_id", report.get("id"))
    overall_status = report.get("overall_status", report.get("status", "NOT_ASSESSED"))
    score_value = report.get("compliance_score", 0)
    summary = report.get("summary") or {}
    total_checks = summary.get("total_checks", summary.get("total", 0))
    compliant = summary.get("compliant", 0)
    violations = summary.get("violations", 0)
    review = summary.get("review", summary.get("requires_review", 0))
    checks = report.get("checks") or []
    extracted = report.get("extracted_data") or {}
    fields = extracted.get("fields") if isinstance(extracted, dict) else {}
    fields = fields if isinstance(fields, dict) else {}
    images = report.get("images") or []

    brand_block = Table([[Paragraph("N", brand)]], colWidths=[15 * mm], rowHeights=[15 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLUE), ("BOX", (0, 0), (-1, -1), 0.5, BLUE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    heading_block = [Paragraph("NIRIKSHA", ParagraphStyle("BrandWord", parent=title, fontSize=13, alignment=TA_LEFT)), Paragraph("AI-POWERED PRODUCT COMPLIANCE", ParagraphStyle("BrandSub", parent=small, textColor=BLUE, fontName="Helvetica-Bold", alignment=TA_LEFT))]
    title_block = [Paragraph("LEGAL METROLOGY COMPLIANCE INSPECTION REPORT", title), Paragraph("Automated inspection record for officer review", subtitle)]
    header = Table([[brand_block, heading_block, title_block]], colWidths=[19 * mm, 49 * mm, content_width - 68 * mm], style=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.extend([header, Spacer(1, 4)])

    metadata_rows = [
        [_paragraph("Report Reference Number", label), _paragraph(report_id), _paragraph("Generated Date / Time", label), _paragraph(_format_datetime(report.get("generated_at"))), _paragraph("Compliance Score", label), _paragraph(f"{_raw(score_value, '0')} / 100", score)],
        [_paragraph("Inspection Date / Time", label), _paragraph(_format_datetime(report.get("scanned_at"))), _paragraph("Report Status", label), _status_paragraph(overall_status, status), _paragraph("Scan Reference", label), _paragraph(report.get("scan_id", report.get("scanId")))],
    ]
    metadata = _bordered_table(metadata_rows, [27 * mm, 36 * mm, 27 * mm, 38 * mm, 27 * mm, 25 * mm])
    metadata.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.extend([metadata, Spacer(1, 7)])

    story.append(_section("1. INSPECTION DETAILS", section_text, content_width))
    manufacturer = _field_value(fields, "manufacturer")
    packer = _field_value(fields, "packer")
    if packer != "Not available" and packer != manufacturer:
        manufacturer = f"{manufacturer}; Packer: {packer}"
    remarks = report.get("remarks") or (f"{review} item(s) require officer verification." if review else "Automated assessment completed.")
    detail_rows = [
        [_paragraph("Product Name", label), _paragraph(report.get("product_name", report.get("productName"))), _paragraph("Manufacturer / Packer", label), _paragraph(manufacturer)],
        [_paragraph("Net Quantity", label), _paragraph(_field_value(fields, "net_quantity")), _paragraph("MRP", label), _paragraph(_field_value(fields, "mrp"))],
        [_paragraph("Inspection Officer / User", label), _paragraph(report.get("officer_name", "Not available")), _paragraph("Location", label), _paragraph(report.get("location", "Not provided"))],
        [_paragraph("Number of Evidence Images", label), _paragraph(len(images)), _paragraph("Remarks", label), _paragraph(remarks)],
    ]
    story.extend([_bordered_table(detail_rows, [34 * mm, 56 * mm, 34 * mm, 56 * mm]), Spacer(1, 7)])

    story.append(_section(f"2. EVIDENCE IMAGES ({len(images)})", section_text, content_width))
    if images:
        cards: list[Any] = []
        for index, source in enumerate(images, 1):
            label_text, data = _image_source(source)
            if label_text == "Evidence image":
                label_text = f"Image {index} - Evidence View"
            elif not label_text.lower().startswith("image "):
                label_text = f"Image {index} - {label_text}"
            image = _scaled_image(data, 78 * mm, 70 * mm) if data else None
            content = image or _paragraph("Evidence image could not be loaded from the stored reference.", small_center)
            card = Table([[_paragraph(label_text, label)], [content]], colWidths=[82 * mm], style=TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            cards.append(card)
        rows = [cards[i:i + 2] for i in range(0, len(cards), 2)]
        if rows and len(rows[-1]) == 1:
            rows[-1].append("")
        evidence_table = Table(rows, colWidths=[88 * mm, 88 * mm], splitByRow=1, hAlign="LEFT", style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(evidence_table)
    else:
        story.append(_bordered_table([[_paragraph("No evidence images were recorded for this scan.", body)]], [content_width]))
    story.append(Spacer(1, 7))

    story.append(_section("3. EXECUTIVE SUMMARY", section_text, content_width))
    summary_cards = [
        [_paragraph("COMPLIANCE SCORE", label), _paragraph(f"{_raw(score_value, '0')} / 100", score)],
        [_paragraph("OVERALL STATUS", label), _status_paragraph(overall_status, status)],
        [_paragraph("TOTAL CHECKS", label), _paragraph(total_checks, score)],
        [_paragraph("COMPLIANT", label), Paragraph(f'<font color="#{GREEN.hexval()[2:]}"><b>{_escape(compliant)}</b></font>', score)],
        [_paragraph("VIOLATIONS", label), Paragraph(f'<font color="#{RED.hexval()[2:]}"><b>{_escape(violations)}</b></font>', score)],
        [_paragraph("REQUIRES REVIEW", label), Paragraph(f'<font color="#{AMBER.hexval()[2:]}"><b>{_escape(review)}</b></font>', score)],
    ]
    summary_table = Table([summary_cards[i:i + 3] for i in range(0, len(summary_cards), 3)], colWidths=[content_width / 3] * 3, style=TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE), ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    summary_text = "The automated assessment identified " + (f"{violations} violation(s)" if violations else "no violations") + ". " + (f"{review} item(s) require officer verification." if review else "No item is currently marked for officer review.")
    story.extend([summary_table, Spacer(1, 4), _bordered_table([[_paragraph(summary_text, body)]], [content_width]), Spacer(1, 7)])

    story.append(_section("4. COMPLIANCE FINDINGS", section_text, content_width))
    finding_rows = [[_paragraph("#", table_header), _paragraph("Rule ID", table_header), _paragraph("Applicable Requirement", table_header), _paragraph("Observed Value / Evidence", table_header), _paragraph("Status", table_header), _paragraph("Confidence", table_header)]]
    for index, check in enumerate(checks, 1):
        value = _raw(check.get("value"))
        evidence = _raw(check.get("evidence"), "")
        observed = value if not evidence or evidence == value else f"{value}\nEvidence: {evidence}"
        finding_rows.append([
            _paragraph(index, body_center), _paragraph(_rule_id(check), rule_id_style), _paragraph(check.get("reference", check.get("requirement")), small),
            _paragraph(observed, small), _status_paragraph(check.get("status"), status), _paragraph(_confidence(check.get("confidence")), body_center),
        ])
    if len(finding_rows) == 1:
        finding_rows.append([_paragraph("-", body_center), _paragraph("No findings", body), _paragraph("Not available", body), _paragraph("No compliance checks were returned.", body), _paragraph("NOT ASSESSED", body_center), _paragraph("N/A", body_center)])
    story.extend([_bordered_table(finding_rows, [8 * mm, 29 * mm, 34 * mm, 51 * mm, 31 * mm, 18 * mm], header=True), Spacer(1, 7)])

    review_items = [item for item in checks if _normalized_status(item.get("status")) in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED"}]
    story.append(_section("5. ITEMS REQUIRING OFFICER REVIEW", section_text, content_width))
    if review_items:
        review_rows = [[_paragraph("Review Item / Rule ID", table_header), _paragraph("Status", table_header), _paragraph("Observed Value", table_header), _paragraph("Applicable Requirement", table_header), _paragraph("Reason for Review / Note", table_header)]]
        for item in review_items:
            explanation = _raw(item.get("explanation"), "Verification is required for this finding.")
            review_rows.append([_paragraph(_rule_id(item), rule_id_style), _status_paragraph(item.get("status"), status), _paragraph(item.get("value"), small), _paragraph(item.get("reference", item.get("requirement")), small), _paragraph(explanation, small)])
        story.append(_bordered_table(review_rows, [31 * mm, 34 * mm, 38 * mm, 38 * mm, 39 * mm], header=True))
    else:
        story.append(_bordered_table([[_paragraph("No items requiring officer review.", body)]], [content_width]))
    story.append(Spacer(1, 7))

    story.append(_section("6. FINAL ASSESSMENT", section_text, content_width))
    final_rows = [
        [_paragraph("Total Checks", label), _paragraph(total_checks), _paragraph("Compliance Score", label), _paragraph(f"{_raw(score_value, '0')} / 100", score)],
        [_paragraph("Compliant", label), _paragraph(compliant), _paragraph("Violations", label), _paragraph(violations)],
        [_paragraph("Requires Review", label), _paragraph(review), _paragraph("Overall Status", label), _status_paragraph(overall_status, status)],
    ]
    story.extend([_bordered_table(final_rows, [35 * mm, 55 * mm, 35 * mm, 55 * mm]), Spacer(1, 7)])

    story.append(_section("7. OFFICER REVIEW", section_text, content_width))
    officer_rows = [
        [_paragraph("Officer Name", label), _paragraph("____________________________", line_style), _paragraph("Designation", label), _paragraph("____________________", line_style)],
        [_paragraph("Department / Office", label), _paragraph("____________________________", line_style), _paragraph("Date", label), _paragraph("__________________", line_style)],
        [_paragraph("Review Status", label), _paragraph("[ ] Verified    [ ] Requires Further Verification\n[ ] Non-Compliant Confirmed    [ ] No Violation Found", line_style), _paragraph("Officer Signature", label), _paragraph("________________________________", line_style)],
        [_paragraph("Inspection Remarks", label), _paragraph("______________________________\n______________________________", line_style), _paragraph("Recommended Action", label), _paragraph("__________________________\n__________________________", line_style)],
    ]
    story.extend([_bordered_table(officer_rows, [31 * mm, 59 * mm, 34 * mm, 56 * mm]), Spacer(1, 7)])

    story.append(_section("DISCLAIMER", section_text, content_width))
    disclaimer_text = "This report is generated automatically by NIRIKSHA based on the submitted package images, extracted declarations, applicable Legal Metrology requirements, and automated compliance assessment. Findings marked UNABLE_TO_VERIFY require verification by an authorized officer. This automated report does not by itself constitute a final legal or enforcement determination."
    story.append(_bordered_table([[_paragraph(disclaimer_text, disclaimer)]], [content_width]))

    document.build(story)
