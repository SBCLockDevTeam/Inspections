from __future__ import annotations

from datetime import date, datetime
import io
import re


def _clean_filename_part(value: str, fallback: str) -> str:
    text = value.strip()
    if not text:
        return fallback
    normalized = re.sub(r"[^A-Za-z0-9 ,\-]", "", text)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ,-")
    return normalized or fallback


def _city_state_from_address(address: str) -> tuple[str, str]:
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if len(parts) >= 3:
        return parts[-2], parts[-1]
    if len(parts) == 2:
        return parts[0], parts[1]
    return "Unknown", "ST"


def build_report_filename(store_number: str, address: str, category: str, completion_date: date) -> str:
    city, state = _city_state_from_address(address)
    safe_store = _clean_filename_part(store_number, "store")
    safe_city = _clean_filename_part(city, "Unknown")
    safe_state = _clean_filename_part(state, "ST")
    safe_category = _clean_filename_part(category, "Category")
    return f"{safe_store}-{safe_city},{safe_state}-Initiating Devices-{safe_category}-{completion_date.strftime('%m-%d-%y')}.pdf"


def normalize_export_rows(raw_rows: object) -> list[dict[str, str]]:
    if not isinstance(raw_rows, list):
        return []
    rows: list[dict[str, str]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "text": str(row.get("text") or "").strip(),
                "address": str(row.get("address") or "").strip(),
                "location": str(row.get("location") or "").strip(),
                "event_date": str(row.get("event_date") or "").strip(),
            }
        )
    return rows


def validate_export_rows(rows: list[dict[str, str]]) -> str | None:
    if not rows:
        return "No accepted points were provided for PDF export."
    for index, row in enumerate(rows, start=1):
        if not row["text"]:
            return f"Row {index} is missing Device Type."
        if not row["address"]:
            return f"Row {index} is missing Address."
        if not row["location"]:
            return f"Row {index} is missing Location."
        if not row["event_date"]:
            return f"Row {index} is missing Test Result."
        if "(pending)" in row["event_date"].lower():
            return f"Row {index} still has a pending Test Result. Accept results before exporting."
    return None


def render_report_pdf(
    *,
    inspection_id: str,
    store_number: str,
    store_type: str,
    address: str,
    inspector_name: str,
    category: str,
    start_date: date,
    completion_date: date,
    rows: list[dict[str, str]],
) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:  # pragma: no cover - only exercised when dependency is missing.
        raise RuntimeError("PDF export requires reportlab. Install web dependencies including reportlab.") from exc

    styles = getSampleStyleSheet()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title="Initiating Devices",
    )

    def date_text(value: date) -> str:
        return value.strftime("%m/%d/%Y")

    centered_header = ParagraphStyle(
        "centered_header",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
    )

    label_style = ParagraphStyle(
        "label_style",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
    )

    section_style = ParagraphStyle(
        "section_style",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
    )

    fill_color = colors.HexColor("#eef2f8")

    header_lines = Table(
        [
            [Paragraph("INITIATING DEVICE", centered_header)],
            [Paragraph("SUPPLEMENTARY RECORD OF INSPECTION AND TESTING", centered_header)],
        ],
        colWidths=[7.5 * inch],
    )
    header_lines.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    inspection_dates = Table(
        [
            [
                Paragraph("Inspection/Test Start Date/Time:", label_style),
                date_text(start_date),
                Paragraph("Inspection/Test Completion Date/Time:", label_style),
                date_text(completion_date),
            ],
            [
                "",
                "",
                Paragraph("Number of Supplemental Pages Attached:", label_style),
                "1",
            ],
        ],
        colWidths=[2.0 * inch, 1.3 * inch, 2.7 * inch, 1.5 * inch],
    )
    inspection_dates.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (1, 0), (1, 0), 0.6, colors.black),
                ("LINEBELOW", (3, 0), (3, 0), 0.6, colors.black),
                ("LINEBELOW", (3, 1), (3, 1), 0.6, colors.black),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("ALIGN", (3, 0), (3, 1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    property_info = Table(
        [
            [Paragraph("1.  PROPERTY INFORMATION", section_style), ""],
            [Paragraph("Name of property:", label_style), store_number],
            [Paragraph("Address:", label_style), address],
        ],
        colWidths=[1.2 * inch, 6.3 * inch],
    )
    property_info.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (1, 0)),
                ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (1, 0), 12),
                ("FONTNAME", (0, 1), (0, 2), "Helvetica"),
                ("FONTSIZE", (0, 1), (0, 2), 9),
                ("FONTNAME", (1, 1), (1, 2), "Helvetica"),
                ("FONTSIZE", (1, 1), (1, 2), 10),
                ("BACKGROUND", (1, 1), (1, 2), fill_color),
                ("LINEBELOW", (1, 1), (1, 1), 0.6, colors.black),
                ("LINEBELOW", (1, 2), (1, 2), 0.6, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    story = [
        header_lines,
        Spacer(1, 0.55 * inch),
        inspection_dates,
        Spacer(1, 0.2 * inch),
        property_info,
        Spacer(1, 0.25 * inch),
    ]

    table_data = [["Device Type", "Address", "Location", "Test Result"]]
    for row in rows:
        table_data.append([row["text"], row["address"], row["location"], row["event_date"]])

    table = Table(table_data, colWidths=[2.9 * inch, 0.8 * inch, 2.1 * inch, 1.2 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (1, -1), "CENTER"),
                ("ALIGN", (3, 1), (3, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return buffer.getvalue()