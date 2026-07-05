"""
Layer 1 — Deterministic Calculations Core

All math here is fixed, auditable, and has no dependency on any external
API or AI model. This is intentional: sizing math should never be
"generated" text, it should be the same answer every time for the same
inputs.

SIMPLIFICATIONS USED IN THIS V1 (documented on purpose, not hidden):
- Peak Sun Hours (PSH) is a static constant for the Philippines instead of
  a location-specific lookup (NASA POWER / PVGIS). Update PSH below if you
  want to refine this later, or swap in an API call.
- Meralco billing is approximated with a single blended rate, not the full
  tiered bracket structure. Good enough for a rough estimate; the user can
  also enter known kWh directly to skip this approximation entirely.
- All component and cable ratings below are simplified, conservative
  lookup tables aligned to common Philippine residential practice — they
  are NOT a substitute for a licensed Professional Electrical Engineer's
  sign-off on an as-built design.
"""

import math

# ---------------------------------------------------------------------------
# Constants (edit these here if your assumptions change; keep them together
# so the whole app's assumptions are visible in one place)
# ---------------------------------------------------------------------------

STANDARD_PSH = 3.5          # Peak Sun Hours, static Philippines average
SYSTEM_EFFICIENCY = 0.8     # Blanket derate: inverter loss, wiring, soiling, temp

PANEL_WATTAGE_W = 500        # Standard panel size used for sizing
PANEL_VOC = 49.5              # Open-circuit voltage per panel (V)
PANEL_ISC = 13.3              # Short-circuit current per panel (A)

# Standard inverter sizes available locally (kW)
INVERTER_SIZES_KW = [3, 5, 6, 8, 10, 12, 15, 20]

# Typical safe max PV string voltage window for common residential hybrid
# inverters in the PH market (conservative — check actual datasheet Voc max
# before finalizing any real design)
MAX_STRING_VOC = 550

# PV1-F solar cable ampacity table (simplified, derated for PH ambient temps)
# (max_continuous_amps, cable_size_mm2)
CABLE_TABLE = [
    (30, 4),
    (45, 6),
    (63, 10),
    (85, 16),
    (100, 25),
]

# Standard breaker ratings available locally (A)
BREAKER_SIZES_A = [16, 20, 25, 32, 40, 50, 63, 80, 100, 125]

DEFAULT_BLENDED_RATE_PHP = 11.50  # PHP/kWh — approximate Meralco blended rate.
                                    # User should override with their actual
                                    # latest bill rate for accuracy.


# ---------------------------------------------------------------------------
# Step 1 — Convert bill or usage into a daily kWh figure
# ---------------------------------------------------------------------------

def estimate_daily_kwh(monthly_bill_php=None, monthly_kwh=None,
                        blended_rate=DEFAULT_BLENDED_RATE_PHP):
    """Return an estimated average daily kWh consumption.

    Provide either monthly_bill_php OR monthly_kwh directly (monthly_kwh
    wins if both are provided, since it's the more accurate figure).
    """
    if monthly_kwh is not None:
        monthly = monthly_kwh
    elif monthly_bill_php is not None:
        monthly = monthly_bill_php / blended_rate
    else:
        raise ValueError("Provide either monthly_bill_php or monthly_kwh")
    return monthly / 30.0


# ---------------------------------------------------------------------------
# Step 2 — Target system size (kWp)
# ---------------------------------------------------------------------------

def calculate_target_kwp(daily_kwh, psh=STANDARD_PSH, efficiency=SYSTEM_EFFICIENCY):
    """Target kWp = Daily kWh / (PSH x efficiency)"""
    return daily_kwh / (psh * efficiency)


# ---------------------------------------------------------------------------
# Step 3 — Panel count, constrained by available roof space
# ---------------------------------------------------------------------------

def size_panels(target_kwp, panel_wattage=PANEL_WATTAGE_W, available_roof_slots=None):
    """Returns dict with recommended panel count and a roof-fit flag.

    available_roof_slots: max number of standard panels the roof can
    physically fit (hard constraint the user supplies in Step 1).
    """
    target_panel_count = math.ceil((target_kwp * 1000) / panel_wattage)

    result = {
        "target_panel_count": target_panel_count,
        "panel_wattage": panel_wattage,
        "achieved_kwp": round((target_panel_count * panel_wattage) / 1000, 2),
        "roof_fits": True,
        "available_roof_slots": available_roof_slots,
    }

    if available_roof_slots is not None and target_panel_count > available_roof_slots:
        result["roof_fits"] = False
        # Suggest a higher wattage panel to hit the same kWp in fewer panels
        needed_wattage = math.ceil((target_kwp * 1000) / available_roof_slots / 5) * 5
        result["suggested_min_wattage"] = needed_wattage

    return result


# ---------------------------------------------------------------------------
# Step 4 — Inverter sizing
# ---------------------------------------------------------------------------

def size_inverter(achieved_kwp, dc_ac_ratio=1.15):
    """Pick the smallest standard inverter size that keeps DC:AC ratio
    within a sane 1.0-1.3 range (typical PH residential practice)."""
    target_ac_kw = achieved_kwp / dc_ac_ratio
    for size in INVERTER_SIZES_KW:
        if size >= target_ac_kw:
            chosen = size
            break
    else:
        chosen = INVERTER_SIZES_KW[-1]

    actual_ratio = round(achieved_kwp / chosen, 2)
    return {
        "inverter_kw": chosen,
        "dc_ac_ratio": actual_ratio,
        "ratio_flag": (
            "high" if actual_ratio > 1.3 else
            "low" if actual_ratio < 1.0 else
            "ok"
        ),
    }


# ---------------------------------------------------------------------------
# Step 5 — String configuration (series/parallel)
# ---------------------------------------------------------------------------

def size_strings(panel_count, panel_voc=PANEL_VOC, max_string_voc=MAX_STRING_VOC):
    max_series = max(1, math.floor(max_string_voc / panel_voc))
    num_strings = math.ceil(panel_count / max_series)
    panels_per_string = math.ceil(panel_count / num_strings)
    string_voc = round(panels_per_string * panel_voc, 1)

    return {
        "max_series_allowed": max_series,
        "num_strings": num_strings,
        "panels_per_string": panels_per_string,
        "string_voc": string_voc,
        "within_voc_limit": string_voc <= max_string_voc,
    }


# ---------------------------------------------------------------------------
# Step 6 — Balance of System: breakers + cable sizing
# ---------------------------------------------------------------------------

def size_dc_breaker(num_strings, panel_isc=PANEL_ISC):
    total_isc = num_strings * panel_isc
    required = total_isc * 1.25  # NEC/PEC-style 125% continuous-current margin
    for size in BREAKER_SIZES_A:
        if size >= required:
            return {"breaker_a": size, "required_a": round(required, 1)}
    return {"breaker_a": BREAKER_SIZES_A[-1], "required_a": round(required, 1)}


def size_dc_cable(num_strings, panel_isc=PANEL_ISC):
    """Sizes the combined run from the DC combiner to the inverter, which
    carries the sum of all strings' current — NOT panels_per_string,
    since current does not add up across panels wired in series (only
    voltage does). Individual per-string home-run cables only need to
    carry a single string's current (panel_isc x 1.25) and can usually
    be a smaller gauge than this combined figure."""
    current = num_strings * panel_isc * 1.25
    for max_amps, size_mm2 in CABLE_TABLE:
        if max_amps >= current:
            return {"cable_mm2": size_mm2, "required_a": round(current, 1)}
    return {"cable_mm2": CABLE_TABLE[-1][1], "required_a": round(current, 1)}


def size_ac_breaker(inverter_kw, voltage=230):
    current = (inverter_kw * 1000 / voltage) * 1.25
    for size in BREAKER_SIZES_A:
        if size >= current:
            return {"breaker_a": size, "required_a": round(current, 1)}
    return {"breaker_a": BREAKER_SIZES_A[-1], "required_a": round(current, 1)}


# ---------------------------------------------------------------------------
# Step 7 — Financial estimate
# ---------------------------------------------------------------------------

def calculate_financials(achieved_kwp, system_cost_php, blended_rate=DEFAULT_BLENDED_RATE_PHP,
                          psh=STANDARD_PSH, efficiency=SYSTEM_EFFICIENCY):
    monthly_production_kwh = achieved_kwp * psh * efficiency * 30
    monthly_savings_php = monthly_production_kwh * blended_rate
    payback_years = (
        round(system_cost_php / (monthly_savings_php * 12), 1)
        if monthly_savings_php > 0 else None
    )
    return {
        "monthly_production_kwh": round(monthly_production_kwh, 1),
        "monthly_savings_php": round(monthly_savings_php, 2),
        "payback_years": payback_years,
    }


# ---------------------------------------------------------------------------
# Orchestration helper — runs the full Layer 1 pipeline in one call
# ---------------------------------------------------------------------------

def run_full_sizing(monthly_bill_php=None, monthly_kwh=None,
                     blended_rate=DEFAULT_BLENDED_RATE_PHP,
                     available_roof_slots=None,
                     panel_wattage=PANEL_WATTAGE_W,
                     system_cost_php=None):
    daily_kwh = estimate_daily_kwh(monthly_bill_php, monthly_kwh, blended_rate)
    target_kwp = calculate_target_kwp(daily_kwh)
    panels = size_panels(target_kwp, panel_wattage, available_roof_slots)
    inverter = size_inverter(panels["achieved_kwp"])
    strings = size_strings(panels["target_panel_count"])
    dc_breaker = size_dc_breaker(strings["num_strings"])
    dc_cable = size_dc_cable(strings["num_strings"])
    ac_breaker = size_ac_breaker(inverter["inverter_kw"])

    financials = None
    if system_cost_php is not None:
        financials = calculate_financials(panels["achieved_kwp"], system_cost_php, blended_rate)

    return {
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
