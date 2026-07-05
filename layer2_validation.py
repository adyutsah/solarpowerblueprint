"""
Layer 2 — Constraint & Safety Validation (rule-based, zero cost)

This replaces the original "LLM validation gateway" concept with a plain
rules table. No API calls, no model, no per-request cost.

Why this works for v1: almost all of the value in the original design was
never really about *understanding language* — it was about catching known
bad combinations (undersized battery for a hybrid inverter, roof space
that can't fit the target panel count, etc). Those are deterministic
checks. A rules table catches the same problems for free and instantly.

If you later want a free-text "describe your situation" box, the right
place for an LLM is *only* to parse that text into the structured `cfg`
dict below — never to decide pass/fail itself. This function should
remain the single source of truth for verdicts.

HOW TO ADD A RULE:
Add a dict to VALIDATION_RULES with:
  - id: short unique string
  - condition: a function(cfg) -> True/False
  - severity: "high" | "medium" | "info"
  - message: a template string, filled with cfg.format(**cfg) style values
             (any key referenced in {curly braces} must exist in cfg)
"""

VALIDATION_RULES = [
    {
        "id": "battery_undersized_hybrid",
        "condition": lambda cfg: cfg.get("system_type") == "hybrid"
            and cfg.get("battery_kwh", 0) > 0
            and cfg["battery_kwh"] < (cfg.get("inverter_kw", 0) * 0.5),
        "severity": "high",
        "message": "Your battery bank ({battery_kwh} kWh) looks undersized for a "
                   "{inverter_kw} kW hybrid inverter. As a rule of thumb, aim for "
                   "at least 0.5 kWh of battery per 1 kW of inverter capacity to "
                   "avoid rapid depletion under load.",
    },
    {
        "id": "battery_undersized_offgrid",
        "condition": lambda cfg: cfg.get("system_type") == "off-grid"
            and cfg.get("battery_kwh", 0) < (cfg.get("daily_kwh", 0) * 1.5),
        "severity": "high",
        "message": "Off-grid systems typically need 1.5-2 days of autonomy. "
                   "Your battery bank ({battery_kwh} kWh) is below the "
                   "recommended minimum for your daily usage of "
                   "{daily_kwh} kWh/day.",
    },
    {
        "id": "future_battery_prep",
        "condition": lambda cfg: cfg.get("system_type") == "grid-tie"
            and cfg.get("plan_batteries_later") is True,
        "severity": "info",
        "message": "Since you're planning to add batteries later, we recommend "
                   "sizing your breaker and cable run now for a future hybrid "
                   "upgrade, so you avoid a full rewire down the line. Ask your "
                   "installer to quote 'battery-ready' wiring.",
    },
    {
        "id": "roof_space_insufficient",
        "condition": lambda cfg: cfg.get("available_roof_slots") is not None
            and cfg.get("target_panel_count", 0) > cfg["available_roof_slots"],
        "severity": "high",
        "message": "Your target of {target_panel_count} panels doesn't fit your "
                   "available roof space ({available_roof_slots} panel slots). "
                   "Consider higher-wattage panels to reach your target kWp in "
                   "fewer panels, or reduce your target system size.",
    },
    {
        "id": "string_voc_exceeded",
        "condition": lambda cfg: cfg.get("within_voc_limit") is False,
        "severity": "high",
        "message": "The calculated string voltage ({string_voc}V) exceeds the "
                   "assumed safe inverter input window. Reduce panels per "
                   "string or confirm your specific inverter's actual max "
                   "input voltage before proceeding.",
    },
    {
        "id": "dc_ac_ratio_high",
        "condition": lambda cfg: cfg.get("ratio_flag") == "high",
        "severity": "medium",
        "message": "Your DC:AC ratio ({dc_ac_ratio}) is on the high side. Some "
                   "production may be clipped on the sunniest days. This is "
                   "usually an acceptable trade-off, but worth knowing.",
    },
    {
        "id": "dc_ac_ratio_low",
        "condition": lambda cfg: cfg.get("ratio_flag") == "low",
        "severity": "info",
        "message": "Your DC:AC ratio ({dc_ac_ratio}) is on the low side. Your "
                   "inverter has extra headroom, which is useful if you plan "
                   "to add more panels later.",
    },
    {
        "id": "gi_roof_mounting_note",
        "condition": lambda cfg: cfg.get("roof_type") == "GI sheet",
        "severity": "info",
        "message": "GI sheet roofs need proper flashing and rust-resistant "
                   "mounting hardware. Confirm your installer is using "
                   "roof-hook or L-foot mounts rated for corrugated metal, "
                   "not just adhesive-based mounts.",
    },
    {
        "id": "off_grid_grid_tie_confusion",
        "condition": lambda cfg: cfg.get("system_type") == "off-grid"
            and cfg.get("net_metering_interest") is True,
        "severity": "medium",
        "message": "Net metering requires a grid connection. An off-grid "
                   "system, by definition, won't be eligible. If you want "
                   "both backup power and net metering credit, consider a "
                   "hybrid system instead.",
    },
    {
        "id": "small_system_grid_tie_only",
        "condition": lambda cfg: cfg.get("target_kwp", 0) < 1.5
            and cfg.get("system_type") == "hybrid",
        "severity": "info",
        "message": "For a small system (under 1.5 kWp), a hybrid inverter's "
                   "extra cost may not be justified unless backup power "
                   "during outages is a priority for you.",
    },
]


def validate(cfg: dict) -> list:
    """Run all rules against a config dict and return triggered flags."""
    triggered = []
    for rule in VALIDATION_RULES:
        try:
            if rule["condition"](cfg):
                triggered.append({
                    "id": rule["id"],
                    "severity": rule["severity"],
                    "message": rule["message"].format(**cfg),
                })
        except (KeyError, TypeError):
            # Missing a key this rule needs — skip it rather than crash the app
            continue
    # Sort so high severity shows first
    order = {"high": 0, "medium": 1, "info": 2}
    triggered.sort(key=lambda f: order.get(f["severity"], 3))
    return triggered
