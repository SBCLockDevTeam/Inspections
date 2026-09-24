from __future__ import annotations

from datetime import date, datetime
import io
import json
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


def build_nfpa_draft_filename(store_number: str, address: str, completion_date: date) -> str:
    city, state = _city_state_from_address(address)
    safe_store = _clean_filename_part(store_number, "store")
    safe_city = _clean_filename_part(city, "Unknown")
    safe_state = _clean_filename_part(state, "ST")
    return f"{safe_store}-{safe_city},{safe_state}-NFPA72-Editable-{completion_date.strftime('%m-%d-%y')}.pdf"


NFPA_DRAFT_FIELDS: list[tuple[str, str]] = [
    ("property_name", "Property Name"),
    ("store_number", "Store Number"),
    ("property_address", "Property Address"),
    ("property_representative", "Property Representative"),
    ("store_phone", "Store Phone"),
    ("testing_organization", "Testing Organization"),
    ("testing_org_address", "Testing Organization Address"),
    ("monitoring_organization", "Monitoring Organization"),
    ("monitoring_org_address", "Monitoring Organization Address"),
    ("monitoring_org_phone", "Monitoring Organization Phone"),
    ("means_of_transmission", "Means of Transmission"),
    ("alarm_retransmitted_to", "Entity Alarms Retransmitted To"),
    ("alarm_retransmitted_phone", "Entity Phone"),
    ("paperwork_location", "Record Documents Location"),
    ("panel_manufacturer", "Alarm Panel Manufacturer"),
    ("disconnecting_means", "Disconnecting Means"),
    ("secondary_power_type", "Secondary Power Type"),
    ("secondary_power_location", "Secondary Power Location"),
    ("battery_type", "Battery Type"),
    ("standby_hours", "Standby Mode (hours)"),
    ("alarm_minutes", "Alarm Mode (minutes)"),
    ("notifications_pretest", "Pre-test Notifications"),
    ("notifications_complete", "Testing Complete Notifications"),
    ("certification_organization", "Certification Organization"),
    ("certification_title", "Certification Title"),
    ("defects_notes", "Defects/Malfunctions Notes"),
    ("wmt_control_number", "WMT Control Number"),
]


def _coerce_nfpa_value(value: object) -> str:
    return str(value or "").strip()


def build_default_nfpa_draft(*, store_number: str, address: str, inspector_name: str = "") -> dict[str, str]:
    values = {key: "" for key, _ in NFPA_DRAFT_FIELDS}
    values["property_name"] = "Walmart, Inc."
    values["store_number"] = store_number.strip()
    values["property_address"] = address.strip()
    values["testing_organization"] = "Security Building Controls"
    values["testing_org_address"] = "6373 Camille Dr, Mechanicsville, VA 23111"
    values["monitoring_organization"] = "Walmart Alarm Central"
    values["monitoring_org_address"] = "703 Associate Drive, Bentonville, AR 72716-0770"
    values["monitoring_org_phone"] = "(479) 273-4600"
    values["means_of_transmission"] = "Network and Phone Lines"
    values["alarm_retransmitted_to"] = "Alarm Central"
    values["alarm_retransmitted_phone"] = "(479) 273-4600"
    values["paperwork_location"] = "Alarm Panel and Managers Safety Binder"
    values["panel_manufacturer"] = "Bosch"
    values["disconnecting_means"] = "Dedicated Breaker"
    values["secondary_power_type"] = "Battery"
    values["secondary_power_location"] = "EDC"
    values["battery_type"] = "Lead Acid"
    values["standby_hours"] = "24"
    values["alarm_minutes"] = "5"
    values["certification_organization"] = "Security Building Controls"
    values["certification_title"] = "Technician"
    values["property_representative"] = inspector_name.strip()
    return values


def normalize_nfpa_draft_fields(raw_fields: object, defaults: dict[str, str] | None = None) -> dict[str, str]:
    normalized = dict(defaults or {})
    if not isinstance(raw_fields, dict):
        return normalized
    allowed_keys = {key for key, _ in NFPA_DRAFT_FIELDS}
    for key, value in raw_fields.items():
        text_key = str(key).strip()
        if text_key not in allowed_keys:
            continue
        normalized[text_key] = _coerce_nfpa_value(value)
    for key in allowed_keys:
        normalized.setdefault(key, "")
    return normalized


def serialize_nfpa_draft_fields(fields: dict[str, str]) -> str:
    return json.dumps(fields, ensure_ascii=True)


def parse_nfpa_draft_fields(raw: str, defaults: dict[str, str]) -> dict[str, str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {}
    return normalize_nfpa_draft_fields(parsed, defaults)


def render_nfpa_draft_pdf(*, inspection_id: str, fields: dict[str, str], completion_date: date) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PDF export requires reportlab. Install web dependencies including reportlab.") from exc

    styles = getSampleStyleSheet()
    label_style = ParagraphStyle(
        "nfpa_label",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
    )
    value_style = ParagraphStyle(
        "nfpa_value",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
    )

    rows = [[Paragraph("Field", label_style), Paragraph("Value", label_style)]]
    for key, label in NFPA_DRAFT_FIELDS:
        value = fields.get(key, "") or ""
        rows.append([Paragraph(label, value_style), Paragraph(value.replace("\n", "<br/>"), value_style)])

    table = Table(rows, colWidths=[2.4 * inch, 5.1 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title="NFPA 72 Editable Draft",
    )

    heading = ParagraphStyle(
        "nfpa_heading",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
    )
    subheading = ParagraphStyle(
        "nfpa_subheading",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
    )

    story = [
        Paragraph("NFPA 72 System Record of Inspection and Testing", heading),
        Spacer(1, 0.08 * inch),
        Paragraph(f"Inspection ID: {inspection_id}", subheading),
        Paragraph(f"Draft Export Date: {completion_date.strftime('%m/%d/%Y')}", subheading),
        Spacer(1, 0.2 * inch),
        table,
    ]
    doc.build(story)
    return buffer.getvalue()


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
    # Export should proceed with any available data, including partial rows.
    if not isinstance(rows, list):
        return "Rows payload must be a list."
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