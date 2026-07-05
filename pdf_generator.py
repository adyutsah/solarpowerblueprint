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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, CondPageBreak
)

styles = getSampleStyleSheet()
h1 = styles["Heading1"]
h2 = styles["Heading2"]
body = styles["BodyText"]
small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.grey)
warn = ParagraphStyle("warn", parent=body, textColor=colors.HexColor("#993C1D"))

# Plain strings in reportlab Tables do NOT wrap — they silently overflow
# past the declared column width instead of breaking onto a new line.
# Every cell that could contain more than a couple of words must be
# wrapped in a Paragraph (which does wrap correctly) rather than passed
# as a raw string.
cell_style = ParagraphStyle("cell", parent=body, fontSize=8, leading=10)
cell_style_bold = ParagraphStyle("cell_bold", parent=cell_style, fontName="Helvetica-Bold")


def _cell(text, bold=False):
    return Paragraph(str(text), cell_style_bold if bold else cell_style)


def _header_row(labels):
    return [_cell(label, bold=True) for label in labels]


def _flags_table(flags):
    if not flags:
        return Paragraph("No issues flagged for this configuration.", body)
    rows = [_header_row(["Severity", "Note"])]
    for f in flags:
        rows.append([_cell(f["severity"].upper()), _cell(f["message"])])
    t = Table(rows, colWidths=[25 * mm, 135 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1EFE8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B4B2A9")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _bom_table(bom):
    rows = [_header_row(["Component", "Brand examples", "Qty", "Low (PHP)", "High (PHP)", "Priced as of"])]
    for item in bom["line_items"]:
        rows.append([
            _cell(item["label"]),
            _cell(item["brand_examples"]),
            _cell(item["quantity"]),
            _cell(f"{item['line_total_low']:,.0f}"),
            _cell(f"{item['line_total_high']:,.0f}"),
            _cell(item["last_updated"]),
        ])
    t = Table(rows, colWidths=[42 * mm, 38 * mm, 12 * mm, 24 * mm, 24 * mm, 30 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1EFE8")),
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
            _header_row(["Metric", "Value"]),
            [_cell("Estimated monthly production"), _cell(f"{fin['monthly_production_kwh']} kWh")],
            [_cell("Estimated monthly savings"), _cell(f"PHP {fin['monthly_savings_php']:,.0f}")],
            [_cell("Estimated payback period"), _cell(f"{fin['payback_years']} years" if fin['payback_years'] else "N/A")],
        ]
        t = Table(rows, colWidths=[80 * mm, 80 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E1F5EE")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#5DCAA5")),
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
        _header_row(["Item", "Spec"]),
        [_cell("Target system size"), _cell(f"{sizing['target_kwp']} kWp")],
        [_cell("Panel count"), _cell(f"{sizing['panels']['target_panel_count']} x {sizing['panels']['panel_wattage']}W")],
        [_cell("Achieved system size"), _cell(f"{sizing['panels']['achieved_kwp']} kWp")],
        [_cell("Inverter"), _cell(f"{inv['inverter_kw']} kW (DC:AC ratio {inv['dc_ac_ratio']})")],
        [_cell("String configuration"), _cell(f"{strings['num_strings']} string(s) x {strings['panels_per_string']} panels")],
        [_cell("String voltage (Voc)"), _cell(f"{strings['string_voc']} V")],
        [_cell("DC breaker"), _cell(f"{dcb['breaker_a']} A")],
        [_cell("DC cable size"), _cell(f"{dcc['cable_mm2']} mm\u00b2 PV1-F")],
        [_cell("AC breaker"), _cell(f"{acb['breaker_a']} A")],
    ]
    t = Table(tech_rows, colWidths=[70 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F1FB")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#85B7EB")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Validation flags", styles["Heading3"]))
    story.append(_flags_table(flags))

    # --- Section C: Bill of Materials -----------------------------------
    # CondPageBreak only breaks if less than the given space remains on the
    # current page — this avoids the double-break bug you get from pairing
    # a trailing Spacer with a hard PageBreak (a Spacer that doesn't fit
    # flows onto a fresh page by itself, then the PageBreak bumps everything
    # else to the page after that, leaving a genuinely blank page between).
    story.append(CondPageBreak(50 * mm))
    story.append(Spacer(1, 6 * mm))
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
