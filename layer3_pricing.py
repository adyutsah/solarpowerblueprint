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
