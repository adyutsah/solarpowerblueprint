"""
Layer 3 — Static Pricing Lookup

No live scraping, no marketplace API calls. Prices come from a CSV file
you (or the installer using this tool) maintain by hand. This sidesteps
Shopee/Lazada anti-bot blocking entirely and any related ToS grey area,
at the cost of needing a manual refresh cadence.

IMPORTANT: data/pricing_cache.csv ships with placeholder sample figures.
They are NOT real current market prices. Replace them with your own
sourced quotes (marketplace listings, distributor price sheets, or
installer quotes) before using this for anything client-facing. The
"last_updated" column is shown in the final report precisely so nobody
mistakes a stale or sample price for a live one.
"""

import csv
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "pricing_cache.csv")

CSV_COLUMNS = [
    "component_id", "label", "brand_examples",
    "price_low_php", "price_high_php", "source_note", "last_updated",
]


def load_pricing_table(path=CSV_PATH):
    table = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            table[row["component_id"]] = row
    return table


def get_component_price(component_id, table=None):
    if table is None:
        table = load_pricing_table()
    row = table.get(component_id)
    if row is None:
        return None
    return {
        "component_id": component_id,
        "label": row["label"],
        "brand_examples": row["brand_examples"],
        "price_low_php": float(row["price_low_php"]),
        "price_high_php": float(row["price_high_php"]),
        "source_note": row["source_note"],
        "last_updated": row["last_updated"],
    }


def build_bom(component_requests: dict, table=None):
    """component_requests: dict of {component_id: quantity}
    Returns a list of line items plus totals, and flags any component_id
    not found in the pricing table so the report can call it out rather
    than silently omitting cost.
    """
    if table is None:
        table = load_pricing_table()

    line_items = []
    missing = []
    total_low = 0.0
    total_high = 0.0

    for component_id, qty in component_requests.items():
        if qty <= 0:
            continue
        priced = get_component_price(component_id, table)
        if priced is None:
            missing.append(component_id)
            continue
        line_low = priced["price_low_php"] * qty
        line_high = priced["price_high_php"] * qty
        total_low += line_low
        total_high += line_high
        line_items.append({
            **priced,
            "quantity": qty,
            "line_total_low": round(line_low, 2),
            "line_total_high": round(line_high, 2),
        })

    return {
        "line_items": line_items,
        "missing_components": missing,
        "total_low_php": round(total_low, 2),
        "total_high_php": round(total_high, 2),
    }


# ---------------------------------------------------------------------------
# Price list editor helpers (used by the in-app "installer tools" table)
# ---------------------------------------------------------------------------

def load_pricing_dataframe(path=CSV_PATH):
    """Load the pricing CSV as a pandas DataFrame, ordered/typed for editing."""
    import pandas as pd
    df = pd.read_csv(path, dtype=str).fillna("")
    df["price_low_php"] = pd.to_numeric(df["price_low_php"], errors="coerce")
    df["price_high_php"] = pd.to_numeric(df["price_high_php"], errors="coerce")
    return df[CSV_COLUMNS]


def validate_pricing_dataframe(df) -> list:
    """Return a list of human-readable problem strings. Empty list = OK.
    This is intentionally forgiving (warns, doesn't silently drop rows) so
    the person editing sees exactly what to fix before downloading."""
    problems = []

    ids = df["component_id"].astype(str).str.strip()
    if (ids == "").any():
        problems.append("One or more rows has a blank component_id.")
    dupes = ids[ids.duplicated() & (ids != "")].unique().tolist()
    if dupes:
        problems.append(f"Duplicate component_id values found: {', '.join(dupes)}. "
                         f"Each component_id must be unique — the app looks up "
                         f"prices by this exact value.")

    if df["price_low_php"].isna().any():
        problems.append("One or more rows has a missing or non-numeric price_low_php.")
    if df["price_high_php"].isna().any():
        problems.append("One or more rows has a missing or non-numeric price_high_php.")

    bad_range = df[
        df["price_low_php"].notna() & df["price_high_php"].notna()
        & (df["price_low_php"] > df["price_high_php"])
    ]
    if len(bad_range) > 0:
        problems.append(
            "price_low_php is greater than price_high_php for: "
            + ", ".join(bad_range["component_id"].astype(str).tolist())
        )

    return problems


def dataframe_to_csv_bytes(df) -> bytes:
    return df[CSV_COLUMNS].to_csv(index=False).encode("utf-8")
