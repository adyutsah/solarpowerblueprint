import streamlit as st

import layer1_calculations as L1
import layer2_validation as L2
import layer3_pricing as L3
from pdf_generator import build_pdf

st.set_page_config(page_title="PH Solar Blueprint", page_icon=":sunny:", layout="centered")

st.title("Philippine solar blueprint generator")
st.caption(
    "Free, offline sizing tool for homeowners and micro-installers. "
    "No AI calls, no live scraping — every number here comes from fixed "
    "engineering math and a manually maintained price list."
)

with st.expander("Assumptions used in this tool (read this first)", expanded=False):
    st.markdown(
        f"""
- Peak sun hours: static **{L1.STANDARD_PSH} hrs/day** (Philippines average), not location-specific.
- System efficiency derate: **{L1.SYSTEM_EFFICIENCY}** (covers inverter loss, wiring, soiling, temperature).
- Standard panel: **{L1.PANEL_WATTAGE_W}W** per panel.
- Meralco rate: blended estimate, editable below — not the full tiered bracket structure.
- Component prices: manually maintained sample list (see `data/pricing_cache.csv`), **not live marketplace data**.
- This tool is a planning aid. A licensed Professional Electrical Engineer should review
  and sign off on the final as-built design before installation.
        """
    )

st.divider()

# ---------------------------------------------------------------------
# Step 1 — Discovery
# ---------------------------------------------------------------------
st.header("Step 1 — your usage & roof")

col1, col2 = st.columns(2)
with col1:
    input_mode = st.radio("How do you want to enter your usage?",
                           ["Monthly Meralco bill (PHP)", "Known monthly usage (kWh)"])
with col2:
    blended_rate = st.number_input("Blended Meralco rate (PHP/kWh)",
                                    min_value=5.0, max_value=20.0,
                                    value=L1.DEFAULT_BLENDED_RATE_PHP, step=0.10,
                                    help="Check your latest bill for your actual all-in rate per kWh.")

if input_mode == "Monthly Meralco bill (PHP)":
    monthly_bill = st.number_input("Average monthly bill (PHP)", min_value=500, value=6000, step=500)
    monthly_kwh = None
else:
    monthly_bill = None
    monthly_kwh = st.number_input("Average monthly usage (kWh)", min_value=50, value=520, step=10)

col3, col4 = st.columns(2)
with col3:
    roof_type = st.selectbox("Roof type", ["GI sheet", "Concrete", "Tile", "Other"])
with col4:
    available_roof_slots = st.number_input(
        "Max panels your roof can fit", min_value=1, value=12, step=1,
        help="Rough count of standard-size panel slots available, accounting for shading, vents, etc.")

# Run Layer 1 base sizing (no cost yet)
daily_kwh = L1.estimate_daily_kwh(monthly_bill, monthly_kwh, blended_rate)
target_kwp = L1.calculate_target_kwp(daily_kwh)
panels = L1.size_panels(target_kwp, available_roof_slots=available_roof_slots)
inverter = L1.size_inverter(panels["achieved_kwp"])
strings = L1.size_strings(panels["target_panel_count"])
dc_breaker = L1.size_dc_breaker(strings["num_strings"])
dc_cable = L1.size_dc_cable(strings["num_strings"])
ac_breaker = L1.size_ac_breaker(inverter["inverter_kw"])

st.subheader("Baseline blueprint")
b1, b2, b3 = st.columns(3)
b1.metric("Target size", f"{target_kwp:.2f} kWp")
b2.metric("Panels needed", f"{panels['target_panel_count']} x {panels['panel_wattage']}W")
b3.metric("Achieved size", f"{panels['achieved_kwp']} kWp")

if not panels["roof_fits"]:
    st.warning(
        f"Your roof slot count ({available_roof_slots}) can't fit the target panel "
        f"count ({panels['target_panel_count']}). Consider panels rated "
        f"{panels.get('suggested_min_wattage')}W or higher, or reduce your target."
    )

st.divider()

# ---------------------------------------------------------------------
# Step 2 — Customization
# ---------------------------------------------------------------------
st.header("Step 2 — customize your system")

col5, col6 = st.columns(2)
with col5:
    system_type = st.selectbox("System type", ["grid-tie", "hybrid", "off-grid"])
with col6:
    battery_choice = st.selectbox(
        "Battery bank", ["None", "5 kWh", "10 kWh", "15 kWh", "20 kWh"],
        index=0 if system_type == "grid-tie" else 1,
    )

battery_kwh_map = {"None": 0, "5 kWh": 5, "10 kWh": 10, "15 kWh": 15, "20 kWh": 20}
battery_kwh = battery_kwh_map[battery_choice]

col7, col8 = st.columns(2)
with col7:
    plan_batteries_later = st.checkbox(
        "I might add batteries later", value=False,
        disabled=(system_type != "grid-tie"),
    )
with col8:
    net_metering_interest = st.checkbox("I want net metering", value=(system_type != "off-grid"))

cable_run_m = st.slider("Estimated cable run, roof to inverter (meters)", 3, 40, 15)

# Build the config dict Layer 2 checks against
cfg = {
    "system_type": system_type,
    "battery_kwh": battery_kwh,
    "plan_batteries_later": plan_batteries_later,
    "net_metering_interest": net_metering_interest,
    "roof_type": roof_type,
    "daily_kwh": round(daily_kwh, 2),
    "target_kwp": round(target_kwp, 2),
    "target_panel_count": panels["target_panel_count"],
    "available_roof_slots": available_roof_slots,
    "inverter_kw": inverter["inverter_kw"],
    "dc_ac_ratio": inverter["dc_ac_ratio"],
    "ratio_flag": inverter["ratio_flag"],
    "string_voc": strings["string_voc"],
    "within_voc_limit": strings["within_voc_limit"],
}

flags = L2.validate(cfg)

st.subheader("Validation flags")
if not flags:
    st.success("No issues flagged for this configuration.")
else:
    icon_map = {"high": ":red_circle:", "medium": ":large_orange_circle:", "info": ":large_blue_circle:"}
    for f in flags:
        st.markdown(f"{icon_map.get(f['severity'], '•')} **{f['severity'].upper()}** — {f['message']}")

st.divider()

# ---------------------------------------------------------------------
# Step 3 — Bill of materials + financials
# ---------------------------------------------------------------------
st.header("Step 3 — bill of materials & financial estimate")

battery_qty = {}
remaining = battery_kwh
for size in [10, 5]:
    n = remaining // size
    if n > 0:
        battery_qty[f"battery_{size}kwh"] = battery_qty.get(f"battery_{size}kwh", 0) + n
        remaining -= n * size

component_requests = {
    "panel_500w": panels["target_panel_count"],
    f"inverter_{inverter['inverter_kw']}kw": 1,
    "dc_breaker": 1,
    "ac_breaker": 1,
    "spd_dc": 1,
    "spd_ac": 1,
    f"cable_{dc_cable['cable_mm2']}mm": cable_run_m * 2,
    "mounting_rail_set": panels["target_panel_count"],
    "labor_install": round(panels["achieved_kwp"], 1),
    **battery_qty,
}

pricing_table = L3.load_pricing_table()
bom = L3.build_bom(component_requests, pricing_table)

st.dataframe(
    [
        {
            "Component": item["label"],
            "Brand examples": item["brand_examples"],
            "Qty": item["quantity"],
            "Low (PHP)": f"{item['line_total_low']:,.0f}",
            "High (PHP)": f"{item['line_total_high']:,.0f}",
            "Priced as of": item["last_updated"],
        }
        for item in bom["line_items"]
    ],
    use_container_width=True,
    hide_index=True,
)

if bom["missing_components"]:
    st.info(
        "No price on file for: " + ", ".join(bom["missing_components"]) +
        ". Add these to data/pricing_cache.csv."
    )

st.metric("Estimated system cost", f"PHP {bom['total_low_php']:,.0f} – {bom['total_high_php']:,.0f}")

est_cost = (bom["total_low_php"] + bom["total_high_php"]) / 2
financials = L1.calculate_financials(panels["achieved_kwp"], est_cost, blended_rate)

f1, f2, f3 = st.columns(3)
f1.metric("Monthly production", f"{financials['monthly_production_kwh']} kWh")
f2.metric("Monthly savings", f"PHP {financials['monthly_savings_php']:,.0f}")
f3.metric("Payback period", f"{financials['payback_years']} yrs" if financials["payback_years"] else "N/A")

st.caption(
    "Pricing is from a manually maintained sample list, not a live feed — check the "
    "'priced as of' column and get a current quote before purchasing."
)

st.divider()

# ---------------------------------------------------------------------
# Step 4 — Final PDF
# ---------------------------------------------------------------------
st.header("Step 4 — download report")

sizing_result = {
    "daily_kwh": round(daily_kwh, 2),
    "target_kwp": round(target_kwp, 2),
    "panels": panels,
    "inverter": inverter,
    "strings": strings,
    "dc_breaker": dc_breaker,
    "dc_cable": dc_cable,
    "ac_breaker": ac_breaker,
    "financials": financials,
}

if st.button("Generate PDF report", type="primary"):
    pdf_bytes = build_pdf(sizing_result, flags, bom, meta={"roof_type": roof_type, "system_type": system_type})
    st.download_button(
        "Download solar_blueprint.pdf",
        data=pdf_bytes,
        file_name="solar_blueprint.pdf",
        mime="application/pdf",
    )

st.divider()
st.caption(
    "Built as a free planning tool. Not a substitute for a licensed Professional "
    "Electrical Engineer's review of your final as-built design."
)
