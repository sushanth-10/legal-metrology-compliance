from __future__ import annotations

import os
import html
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak, KeepTogether


def _text(value: Any) -> str:
    return html.escape(str(value)) if value not in (None, "") else "Not available"


def create_pdf(report: dict[str, Any], output_path: Path) -> None:
    """Generate a professional government-style legal metrology compliance report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    
    # Define custom styles
    title_style = ParagraphStyle("Title", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#0f172a"), fontSize=16, spaceAfter=2, fontName="Helvetica-Bold")
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Heading1"], alignment=TA_CENTER, textColor=colors.HexColor("#164e63"), fontSize=12, spaceAfter=4, fontName="Helvetica-Bold")
    report_header_style = ParagraphStyle("ReportHeader", parent=styles["Heading2"], textColor=colors.HexColor("#0f172a"), fontSize=11, spaceBefore=8, spaceAfter=6, fontName="Helvetica-Bold")
    section_header_style = ParagraphStyle("SectionHeader", parent=styles["Heading3"], textColor=colors.white, fontSize=10, spaceBefore=6, spaceAfter=4, fontName="Helvetica-Bold", backColor=colors.HexColor("#164e63"), borderPadding=4)
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9, leading=11, alignment=TA_LEFT)
    small_style = ParagraphStyle("Small", parent=body_style, fontSize=8, leading=10)
    table_header_style = ParagraphStyle("TableHeader", parent=small_style, textColor=colors.white, fontName="Helvetica-Bold")
    table_cell_style = ParagraphStyle("TableCell", parent=small_style, alignment=TA_LEFT)
    
    doc = SimpleDocTemplate(str(output_path), pagesize=A4, rightMargin=12*mm, leftMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    story: list[Any] = []
    
    # A. REPORT HEADER
    story.append(Paragraph("NIRIKSHA", title_style))
    story.append(Paragraph("LEGAL METROLOGY COMPLIANCE INSPECTION REPORT", subtitle_style))
    story.append(Spacer(1, 8))
    
    # Report metadata
    report_id = report.get("report_id", "N/A")
    generated_at = report.get("generated_at", "N/A")
    compliance_score = report.get("compliance_score", 0)
    overall_status = report.get("overall_status", "UNKNOWN")
    
    header_rows = [
        [Paragraph("Report Reference:", small_style), Paragraph(_text(report_id), small_style), Paragraph("Generated Date/Time:", small_style), Paragraph(_text(generated_at), small_style)],
        [Paragraph("Report Status:", small_style), Paragraph(_text(overall_status.upper()), small_style), Paragraph("Compliance Score:", small_style), Paragraph(f"{compliance_score} / 100", small_style)],
    ]
    story.append(Table(header_rows, colWidths=[30*mm, 50*mm, 35*mm, 50*mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0fdfa")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f0fdfa")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])))
    story.append(Spacer(1, 8))
    
    # B. INSPECTION DETAILS
    story.append(Paragraph("INSPECTION DETAILS", report_header_style))
    extracted = report.get("extracted_data", {})
    fields = extracted.get("fields", {})
    
    def get_field_value(field_name: str) -> str:
        field = fields.get(field_name, {})
        if isinstance(field, dict):
            return _text(field.get("value"))
        return "Not available"
    
    inspection_rows = [
        [Paragraph("Product Name:", small_style), Paragraph(report.get("product_name", "Not available"), small_style)],
        [Paragraph("Manufacturer / Packer:", small_style), Paragraph(get_field_value("manufacturer"), small_style)],
        [Paragraph("Net Quantity:", small_style), Paragraph(get_field_value("net_quantity"), small_style)],
        [Paragraph("MRP:", small_style), Paragraph(get_field_value("mrp"), small_style)],
        [Paragraph("Inspection Date/Time:", small_style), Paragraph(_text(report.get("scanned_at", "Not available")), small_style)],
        [Paragraph("Officer:", small_style), Paragraph(_text(report.get("officer_name", "Not available")), small_style)],
        [Paragraph("Evidence Images:", small_style), Paragraph(str(len(report.get("images", []))), small_style)],
    ]
    story.append(Table(inspection_rows, colWidths=[45*mm, 120*mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0fdfa")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])))
    story.append(Spacer(1, 10))
    
    # C. EXECUTIVE SUMMARY
    story.append(Paragraph("EXECUTIVE SUMMARY", report_header_style))
    summary = report.get("summary", {})
    total_checks = summary.get("total_checks", 0)
    compliant = summary.get("compliant", 0)
    violations = summary.get("violations", 0)
    review = summary.get("review", 0)
    
    summary_text = f"""
    Compliance Score: {compliance_score} / 100<br/>
    Overall Status: {_text(overall_status.upper())}<br/>
    <br/>
    Total Checks: {total_checks}<br/>
    Compliant: {compliant}<br/>
    Violations: {violations}<br/>
    Requires Review: {review}
    """
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 10))
    
    # D. COMPLIANCE FINDINGS
    checks = report.get("checks", [])
    if checks:
        story.append(Paragraph("COMPLIANCE FINDINGS", report_header_style))
        
        for index, check in enumerate(checks, 1):
            check_name = check.get("label", check.get("name", f"Check {index}"))
            status = check.get("status", "NOT_ASSESSED").upper()
            value = check.get("value", "Not available")
            requirement = check.get("requirement", check.get("reference", "Not available"))
            explanation = check.get("explanation", "Not available")
            confidence = check.get("confidence")
            
            # Build confidence string
            confidence_str = "Not available"
            if confidence is not None:
                try:
                    confidence_val = float(confidence)
                    confidence_str = f"{confidence_val*100:.0f}%" if confidence_val <= 1 else f"{confidence_val:.0f}%"
                except (TypeError, ValueError):
                    confidence_str = str(confidence)
            
            check_section = f"""
            <b>{index}. {_text(check_name)}</b><br/>
            Status: {status}<br/>
            Value: {_text(value)}<br/>
            Applicable Requirement: {_text(requirement)}<br/>
            Assessment: {_text(explanation)}<br/>
            Confidence: {confidence_str}
            """
            story.append(Paragraph(check_section, small_style))
            story.append(Spacer(1, 4))
        
        story.append(Spacer(1, 6))
    
    # E. VIOLATIONS
    violations_list = [c for c in checks if c.get("status", "").upper() == "VIOLATION"]
    if violations_list:
        story.append(Paragraph("VIOLATIONS", report_header_style))
        
        for index, violation in enumerate(violations_list, 1):
            violation_section = f"""
            <b>Violation {index}: {_text(violation.get("label", violation.get("name", "Unknown")))}</b><br/>
            Status: VIOLATION<br/>
            Extracted Value: {_text(violation.get("value", "Not available"))}<br/>
            Applicable Requirement: {_text(violation.get("requirement", violation.get("reference", "Not available")))}<br/>
            Explanation: {_text(violation.get("explanation", "Not available"))}
            """
            story.append(Paragraph(violation_section, small_style))
            story.append(Spacer(1, 4))
        
        story.append(Spacer(1, 6))
    
    # F. ITEMS REQUIRING OFFICER REVIEW
    review_items = [c for c in checks if c.get("status", "").upper() in {"UNABLE_TO_VERIFY", "OFFICER_REVIEW_REQUIRED"}]
    if review_items:
        story.append(Paragraph("ITEMS REQUIRING OFFICER REVIEW", report_header_style))
        
        for index, item in enumerate(review_items, 1):
            item_section = f"""
            <b>Review Item {index}: {_text(item.get("label", item.get("name", "Unknown")))}</b><br/>
            Status: {_text(item.get("status", "").upper())}<br/>
            Observed Value: {_text(item.get("value", "Not available"))}<br/>
            Applicable Requirement: {_text(item.get("requirement", item.get("reference", "Not available")))}<br/>
            Reason for Review: {_text(item.get("explanation", "Requires verification"))}<br/>
            <i>Note: This item requires officer verification before any regulatory action.</i>
            """
            story.append(Paragraph(item_section, small_style))
            story.append(Spacer(1, 4))
        
        story.append(Spacer(1, 6))
    
    # G. EVIDENCE SUMMARY
    images = report.get("images", [])
    if images:
        story.append(Paragraph("EVIDENCE SUMMARY", report_header_style))
        story.append(Paragraph(f"Evidence Images Examined: {len(images)}", body_style))
        story.append(Spacer(1, 3))
        
        for idx, image_ref in enumerate(images, 1):
            story.append(Paragraph(f"Evidence Image {idx}: {_text(image_ref)}", small_style))
        
        story.append(Spacer(1, 6))
    
    # H. FINAL ASSESSMENT
    story.append(Paragraph("FINAL ASSESSMENT", report_header_style))
    
    assessment_text = f"""
    Total Checks: {total_checks}<br/>
    Compliant: {compliant}<br/>
    Violations: {violations}<br/>
    Requires Review: {review}<br/>
    Compliance Score: {compliance_score} / 100<br/>
    Overall Status: {_text(overall_status.upper())}<br/>
    <br/>
    """
    
    if violations > 0:
        assessment_text += f"This inspection identified {violations} non-compliance issue(s). Officer review and corrective action may be required.<br/>"
    if review > 0:
        assessment_text += f"{review} item(s) require officer verification before enforcement action.<br/>"
    if compliance_score >= 85:
        assessment_text += "The product generally meets applicable Legal Metrology requirements."
    elif compliance_score >= 70:
        assessment_text += "The product requires review to confirm full compliance."
    else:
        assessment_text += "Significant compliance concerns identified. Officer review required."
    
    story.append(Paragraph(assessment_text, body_style))
    story.append(Spacer(1, 10))
    
    # I. OFFICER REVIEW
    story.append(Paragraph("OFFICER REVIEW", report_header_style))
    
    review_text = """
    Officer Name: ___________________________________<br/>
    Designation: ___________________________________<br/>
    <br/>
    Review Status (check one):<br/>
    ☐ Verified<br/>
    ☐ Requires Further Verification<br/>
    ☐ Non-Compliant Confirmed<br/>
    ☐ No Violation Found<br/>
    <br/>
    Inspection Remarks:<br/>
    _________________________________________________________________________<br/>
    _________________________________________________________________________<br/>
    <br/>
    Recommended Action:<br/>
    _________________________________________________________________________<br/>
    _________________________________________________________________________<br/>
    <br/>
    Officer Signature: ________________________     Date: _______________
    """
    story.append(Paragraph(review_text, small_style))
    story.append(Spacer(1, 10))
    
    # J. SYSTEM INFORMATION
    story.append(Paragraph("SYSTEM INFORMATION", report_header_style))
    
    system_info = """
    Generated By: NIRIKSHA — AI-Powered Product Compliance System<br/>
    Assessment Pipeline: Package Images → OCR / Image Analysis → Structured Extraction → Compliance Engine → Compliance Report<br/>
    <br/>
    <i>Disclaimer: This report is an electronically generated assessment based on the submitted package evidence. 
    Automated findings requiring verification should be reviewed by the designated officer before regulatory action. 
    The compliance score represents an assessment indicator to assist the officer and is not a legally binding certification.</i>
    """
    story.append(Paragraph(system_info, small_style))
    
    # Build PDF
    doc.build(story)
