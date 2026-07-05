"""
PDF report builder — Section A (financial), B (technical), C (BOM).

Uses reportlab, which is pure Python and free (no external service, no
API key). Returns bytes so Streamlit can offer it as a direct download
without writing to disk.
"""

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

styles = getSampleStyleSheet()
h1 = styles["Heading1"]
h2 = styles["Heading2"]
body = styles["BodyText"]
small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.grey)
warn = ParagraphStyle("warn", parent=body, textColor=colors.HexColor("#993C1D"))


def _flags_table(flags):
    if not flags:
        return Paragraph("No issues flagged for this configuration.", body)
    rows = [["Severity", "Note"]]
    for f in flags:
        rows.append([f["severity"].upper(), f["message"]])
    t = Table(rows, colWidths=[25 * mm, 145 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1EFE8")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B4B2A9")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _bom_table(bom):
    rows = [["Component", "Brand examples", "Qty", "Low (PHP)", "High (PHP)", "Priced as of"]]
    for item in bom["line_items"]:
        rows.append([
            item["label"],
            item["brand_examples"],
            str(item["quantity"]),
            f"{item['line_total_low']:,.0f}",
            f"{item['line_total_high']:,.0f}",
            item["last_updated"],
        ])
    t = Table(rows, colWidths=[45 * mm, 35 * mm, 15 * mm, 25 * mm, 25 * mm, 30 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1EFE8")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B4B2A9")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def build_pdf(sizing: dict, flags: list, bom: dict, meta: dict) -> bytes:
    """meta: dict with optional keys like 'homeowner_name', 'roof_type',
    'system_type', 'location'."""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )
    story = []

    # --- Cover / header -----------------------------------------------
    story.append(Paragraph("Solar system blueprint", h1))
    story.append(Paragraph(f"Generated {date.today().isoformat()}", small))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "This report is a planning aid, not a certified engineering design. "
        "Sizing math uses simplified, documented assumptions (see appendix). "
        "A licensed Professional Electrical Engineer should review and sign "
        "off on the final as-built design before installation, in line with "
        "the Philippine Electrical Code.",
        warn,
    ))
    story.append(Spacer(1, 6 * mm))

    # --- Section A: Financial dashboard --------------------------------
    story.append(Paragraph("Section A — Financial dashboard", h2))
    fin = sizing.get("financials")
    if fin:
        rows = [
            ["Metric", "Value"],
            ["Estimated monthly production", f"{fin['monthly_production_kwh']} kWh"],
            ["Estimated monthly savings", f"PHP {fin['monthly_savings_php']:,.0f}"],
            ["Estimated payback period", f"{fin['payback_years']} years" if fin['payback_years'] else "N/A"],
        ]
        t = Table(rows, colWidths=[80 * mm, 80 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E1F5EE")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#5DCAA5")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No system cost was provided, so payback and "
                                "savings could not be estimated.", body))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Note: financial figures use a static blended Meralco rate and a "
        "static Philippine peak sun hour assumption (3.5 hrs/day), not "
        "location-specific irradiance data or Meralco's full tiered rate "
        "structure. Treat as directional, not exact.",
        small,
    ))
    story.append(Spacer(1, 6 * mm))

    # --- Section B: Technical schematic layout -------------------------
    story.append(Paragraph("Section B — Technical schematic layout", h2))
    strings = sizing["strings"]
    inv = sizing["inverter"]
    dcb = sizing["dc_breaker"]
    dcc = sizing["dc_cable"]
    acb = sizing["ac_breaker"]
    tech_rows = [
        ["Item", "Spec"],
        ["Target system size", f"{sizing['target_kwp']} kWp"],
        ["Panel count", f"{sizing['panels']['target_panel_count']} x {sizing['panels']['panel_wattage']}W"],
        ["Achieved system size", f"{sizing['panels']['achieved_kwp']} kWp"],
        ["Inverter", f"{inv['inverter_kw']} kW (DC:AC ratio {inv['dc_ac_ratio']})"],
        ["String configuration", f"{strings['num_strings']} string(s) x {strings['panels_per_string']} panels"],
        ["String voltage (Voc)", f"{strings['string_voc']} V"],
        ["DC breaker", f"{dcb['breaker_a']} A"],
        ["DC cable size", f"{dcc['cable_mm2']} mm² PV1-F"],
        ["AC breaker", f"{acb['breaker_a']} A"],
    ]
    t = Table(tech_rows, colWidths=[70 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F1FB")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#85B7EB")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Validation flags", styles["Heading3"]))
    story.append(_flags_table(flags))
    story.append(Spacer(1, 6 * mm))

    # --- Section C: Bill of Materials -----------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Section C — Bill of materials", h2))
    if bom["line_items"]:
        story.append(_bom_table(bom))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            f"Estimated total: PHP {bom['total_low_php']:,.0f} – "
            f"{bom['total_high_php']:,.0f}",
            styles["Heading3"],
        ))
    if bom["missing_components"]:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            "Components without a price on file (add these to "
            "data/pricing_cache.csv): " + ", ".join(bom["missing_components"]),
            warn,
        ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Pricing above is drawn from a manually maintained local price "
        "list, not a live marketplace feed. Check the 'priced as of' "
        "column for each line item — prices in the Philippine solar "
        "market move quickly. Get a current quote from your installer "
        "before purchasing.",
        small,
    ))

    doc.build(story)
    return buf.getvalue()
