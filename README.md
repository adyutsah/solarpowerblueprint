# PH solar blueprint generator

A free, offline solar sizing and quotation tool for Philippine homeowners and
micro-installers. Built as a v1 with zero recurring cost: no AI API calls,
no live web scraping, no paid hosting.

## Architecture

- **Layer 1 — `layer1_calculations.py`**: deterministic sizing math (panels,
  inverter, strings, breakers, cable, financials). Static PSH = 3.5 hrs/day.
- **Layer 2 — `layer2_validation.py`**: rule-based constraint checking
  (undersized batteries, roof space, string voltage limits, etc). No LLM —
  just a table of `condition -> message` rules.
- **Layer 3 — `layer3_pricing.py`** + `data/pricing_cache.csv`: static,
  manually maintained component pricing. Ships with **sample placeholder
  prices** — replace before using for a real client quote.
- **`pdf_generator.py`**: builds the final report (reportlab, pure Python,
  free).
- **`app.py`**: the Streamlit UI that ties it all together.

## Before you use this for a real client

1. Open `data/pricing_cache.csv` and replace every `PLACEHOLDER` row with
   prices you've actually sourced (marketplace listings, distributor sheets,
   or installer quotes). Update the `last_updated` column each time.
2. Update `DEFAULT_BLENDED_RATE_PHP` in `layer1_calculations.py` if Meralco's
   rates have changed since you last checked.
3. Review `VALIDATION_RULES` in `layer2_validation.py` — add rules as you
   encounter new failure modes in the field.
4. Get a licensed Professional Electrical Engineer to review the final
   as-built design. This tool is a planning aid, not a certified design.

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploying

See `DEPLOYMENT.md` for a full step-by-step guide to deploying this for
free on Streamlit Community Cloud.
