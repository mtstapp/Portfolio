"""Google Sheet allocation taxonomy: read, write, auto-classify, dropdowns.

Manages the "Allocations" worksheet in the "Portfolio" Google Sheet workbook.
Each holding is tagged across 10 dimensions (plus Sector/Industry/Risk/
look-through/manual price).  Dimension 11 (Account Tax Treatment) is derived
from ``account_type`` in the canonical holdings — it is NOT stored in the Sheet.

When a **new** symbol is added to the Sheet, the module attempts to classify it
using the Perplexity API (one-time LLM call per symbol).  If the API key is not
configured or the call fails, a rule-based fallback is used instead.

Public API used by ``daily_refresh.py``::

    from portfolio.sources import allocations

    overrides_df = allocations.sync_and_classify(
        holdings_df=canonical_holdings,
        gs_creds_path="/path/to/service-account.json",
    )
"""

import json
import logging
import re
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────────────────
# Taxonomy constants — every allowed value per dimension
# ───────────────────────────────────────────────────────────────────────

ASSET_CLASSES = [
    "US Equity",
    "Intl Developed Equity",
    "Emerging Market Equity",
    "Investment-Grade Bond",
    "High-Yield Bond",
    "Intl/EM Bond",
    "TIPS/Inflation-Linked",
    "Cash & Equivalents",
    "Real Estate (REITs)",
    "Commodities",
    "Infrastructure",
    "Private Credit/BDC",
    "MLP/Energy Income",
    "Preferred Stock",
    "Multi-Asset/Allocation",
    "Other Alternative",
]

OBJECTIVES = ["Growth", "Income", "Preservation", "Growth & Income"]

REGIONS = ["US", "Developed ex-US", "Emerging Markets", "Frontier", "Global"]

EQUITY_STYLES = [
    "Large Value", "Large Blend", "Large Growth",
    "Mid Value", "Mid Blend", "Mid Growth",
    "Small Value", "Small Blend", "Small Growth",
]

FI_STYLES = [
    "High/Limited", "High/Moderate", "High/Extensive",
    "Medium/Limited", "Medium/Moderate", "Medium/Extensive",
    "Low/Limited", "Low/Moderate", "Low/Extensive",
]

FI_SECTORS = [
    "Government/Sovereign",
    "Agency/GSE",
    "IG Corporate",
    "HY Corporate",
    "Securitized",
    "Municipal",
    "Bank Loans/Floating",
    "TIPS/Inflation",
    "Intl/EM Sovereign",
    "Preferred/Hybrid",
]

FACTORS = [
    "Value", "Growth", "Quality", "Momentum",
    "Low Volatility", "High Yield/Dividend",
    "Size (Small Cap)", "Broad/Market-Weight", "N/A",
]

INCOME_TYPES = [
    "Qualified Dividends",
    "Non-Qualified Dividends",
    "Interest/Coupon",
    "Tax-Exempt Interest",
    "Return of Capital",
    "Capital Gains Distributions",
    "Option Premium/Synthetic",
    "No Current Income",
]

VEHICLE_TYPES = [
    "Individual Stock",
    "Individual Bond",
    "ETF",
    "Open-End Mutual Fund",
    "Closed-End Fund",
    "Money Market Fund",
    "CD/Savings",
    "LP/Partnership",
    "Annuity",
    "Other",
]

TAX_TREATMENTS = ["Taxable", "Tax-Deferred", "Tax-Exempt", "HSA"]

# ───────────────────────────────────────────────────────────────────────
# Sheet column layout  (A … V)
# ───────────────────────────────────────────────────────────────────────

# Ordered list of column headers exactly as they appear in the Sheet.
SHEET_COLUMNS = [
    "Symbol",               # A
    "Description",          # B
    "Asset Class",          # C
    "Objective",            # D
    "Region",               # E
    "Equity Style",         # F
    "FI Style",             # G
    "FI Sector",            # H
    "Factor",               # I
    "Income Type",          # J
    "Vehicle Type",         # K
    "Sector",               # L
    "Industry",             # M
    "Risk Score",           # N
    "pct_domestic_stock",   # O
    "pct_intl_stock",       # P
    "pct_em_stock",         # Q
    "pct_domestic_bond",    # R
    "pct_intl_bond",        # S
    "pct_cash",             # T
    "pct_alternative",      # U
    "Manual Price",         # V
]

# Map from Sheet header → internal Parquet column name
HEADER_TO_COL = {
    "Symbol":          "symbol",
    "Description":     "description",
    "Asset Class":     "asset_class",
    "Objective":       "objective",
    "Region":          "region",
    "Equity Style":    "equity_style",
    "FI Style":        "fi_style",
    "FI Sector":       "fi_sector",
    "Factor":          "factor",
    "Income Type":     "income_type",
    "Vehicle Type":    "vehicle_type",
    "Sector":          "sector",
    "Industry":        "industry",
    "Risk Score":      "risk_score",
    "pct_domestic_stock":  "pct_domestic_stock",
    "pct_intl_stock":      "pct_intl_stock",
    "pct_em_stock":        "pct_em_stock",
    "pct_domestic_bond":   "pct_domestic_bond",
    "pct_intl_bond":       "pct_intl_bond",
    "pct_cash":            "pct_cash",
    "pct_alternative":     "pct_alternative",
    "Manual Price":    "manual_price",
}

COL_TO_HEADER = {v: k for k, v in HEADER_TO_COL.items()}

# Columns that carry dropdown-validatable taxonomy dimensions
DIMENSION_COLS = [
    "asset_class", "objective", "region", "equity_style",
    "fi_style", "fi_sector", "factor", "income_type", "vehicle_type",
]

# Dropdown value lists keyed by internal column name
DROPDOWN_VALUES: dict[str, list[str]] = {
    "asset_class":   ASSET_CLASSES,
    "objective":     OBJECTIVES,
    "region":        REGIONS,
    "equity_style":  EQUITY_STYLES,
    "fi_style":      FI_STYLES,
    "fi_sector":     FI_SECTORS,
    "factor":        FACTORS,
    "income_type":   INCOME_TYPES,
    "vehicle_type":  VEHICLE_TYPES,
}

# Look-through columns
LOOK_THROUGH_COLS = [
    "pct_domestic_stock", "pct_intl_stock", "pct_em_stock",
    "pct_domestic_bond", "pct_intl_bond", "pct_cash", "pct_alternative",
]

# ───────────────────────────────────────────────────────────────────────
# Account tax-treatment derivation (Dimension 11 — NOT in Sheet)
# ───────────────────────────────────────────────────────────────────────

_TAX_TREATMENT_MAP: dict[str, str] = {
    "BROKERAGE": "Taxable",
    "JOINT": "Taxable",
    "TRUST": "Taxable",
    "IRA": "Tax-Deferred",
    "SEP_IRA": "Tax-Deferred",
    "SEP": "Tax-Deferred",
    "401K": "Tax-Deferred",
    "403B": "Tax-Deferred",
    "TRADITIONAL_IRA": "Tax-Deferred",
    "ROTH_IRA": "Tax-Exempt",
    "ROTH": "Tax-Exempt",
    "ROTH_401K": "Tax-Exempt",
    "HSA": "HSA",
}


def derive_tax_treatment(account_type: str) -> str:
    """Map an account_type string to its tax treatment label."""
    return _TAX_TREATMENT_MAP.get(account_type.upper(), "Taxable")


# ───────────────────────────────────────────────────────────────────────
# Rule-based auto-classification  (fallback when LLM unavailable)
# ───────────────────────────────────────────────────────────────────────

def _kw(text: str | None, *patterns: str) -> bool:
    """Case-insensitive keyword match against *text*."""
    if not text:
        return False
    lower = text.lower()
    return any(p.lower() in lower for p in patterns)


def auto_classify_rules(row: dict[str, Any]) -> dict[str, str]:
    """Derive taxonomy values from holdings data using heuristic rules.

    *row* should have at least: symbol, description, security_type, sector,
    industry, dividend_yield, market_cap, pe_ratio, and optionally
    yf_category (yfinance ``info["category"]``).

    Returns a dict of ``{column: value}`` for the taxonomy dimensions.
    """
    sec_type = (row.get("security_type") or "").upper()
    cat = row.get("yf_category") or row.get("sector") or ""
    div_yield = float(row.get("dividend_yield") or 0)
    mkt_cap = float(row.get("market_cap") or 0)
    pe = float(row.get("pe_ratio") or 0)
    sector = row.get("sector") or ""
    symbol = row.get("symbol") or ""

    result: dict[str, str] = {}

    # ── Asset Class ─────────────────────────────────────────────
    if sec_type == "CASH":
        result["asset_class"] = "Cash & Equivalents"
    elif sec_type == "BOND":
        result["asset_class"] = "Investment-Grade Bond"
    elif sec_type == "EQUITY":
        if _kw(sector, "Real Estate"):
            result["asset_class"] = "Real Estate (REITs)"
        else:
            result["asset_class"] = "US Equity"
    elif sec_type in ("ETF", "MUTUAL_FUND"):
        if _kw(cat, "Target", "Allocation", "Balanced", "Lifecycle"):
            result["asset_class"] = "Multi-Asset/Allocation"
        elif _kw(cat, "Real Estate", "REIT"):
            result["asset_class"] = "Real Estate (REITs)"
        elif _kw(cat, "Commodit"):
            result["asset_class"] = "Commodities"
        elif _kw(cat, "TIPS", "Inflation"):
            result["asset_class"] = "TIPS/Inflation-Linked"
        elif _kw(cat, "High Yield", "High-Yield"):
            result["asset_class"] = "High-Yield Bond"
        elif _kw(cat, "Bond", "Fixed", "Treasury", "Aggregate", "Income"):
            if _kw(cat, "International", "Foreign", "Emerging", "EM"):
                result["asset_class"] = "Intl/EM Bond"
            else:
                result["asset_class"] = "Investment-Grade Bond"
        elif _kw(cat, "Emerging", "EM"):
            result["asset_class"] = "Emerging Market Equity"
        elif _kw(cat, "International", "Foreign", "Developed", "World ex-US"):
            result["asset_class"] = "Intl Developed Equity"
        elif _kw(cat, "Preferred"):
            result["asset_class"] = "Preferred Stock"
        elif _kw(cat, "MLP", "Midstream", "Pipeline"):
            result["asset_class"] = "MLP/Energy Income"
        elif _kw(cat, "Infrastructure"):
            result["asset_class"] = "Infrastructure"
        else:
            result["asset_class"] = "US Equity"
    else:
        result["asset_class"] = "US Equity"

    # ── Objective ───────────────────────────────────────────────
    ac = result.get("asset_class", "")
    if ac in ("Cash & Equivalents",):
        result["objective"] = "Preservation"
    elif ac in ("Investment-Grade Bond", "TIPS/Inflation-Linked"):
        result["objective"] = "Preservation"
    elif ac in ("High-Yield Bond", "Private Credit/BDC", "MLP/Energy Income",
                "Preferred Stock"):
        result["objective"] = "Income"
    elif div_yield >= 0.04:
        result["objective"] = "Income"
    elif 0.02 <= div_yield < 0.04:
        result["objective"] = "Growth & Income"
    elif ac == "Multi-Asset/Allocation":
        result["objective"] = "Growth & Income"
    else:
        result["objective"] = "Growth"

    # ── Region ──────────────────────────────────────────────────
    if _kw(cat, "Global", "World", "ACWI"):
        result["region"] = "Global"
    elif _kw(cat, "Emerging", "EM"):
        result["region"] = "Emerging Markets"
    elif _kw(cat, "International", "Foreign", "Developed ex", "ex-US"):
        result["region"] = "Developed ex-US"
    else:
        result["region"] = "US"

    # ── Equity Style ────────────────────────────────────────────
    if sec_type == "EQUITY":
        # Size
        if mkt_cap >= 10_000_000_000:
            cap = "Large"
        elif mkt_cap >= 2_000_000_000:
            cap = "Mid"
        elif mkt_cap > 0:
            cap = "Small"
        else:
            cap = "Large"
        # Value/Growth
        if pe > 0 and pe < 15:
            style = "Value"
        elif pe > 25:
            style = "Growth"
        else:
            style = "Blend"
        result["equity_style"] = f"{cap} {style}"
    elif sec_type in ("ETF", "MUTUAL_FUND"):
        # Try to parse from yfinance category
        style_found = ""
        for s in EQUITY_STYLES:
            if _kw(cat, s):
                style_found = s
                break
        if not style_found:
            # Partial matches
            if _kw(cat, "Large") and _kw(cat, "Growth"):
                style_found = "Large Growth"
            elif _kw(cat, "Large") and _kw(cat, "Value"):
                style_found = "Large Value"
            elif _kw(cat, "Large") and _kw(cat, "Blend"):
                style_found = "Large Blend"
            elif _kw(cat, "Mid") and _kw(cat, "Growth"):
                style_found = "Mid Growth"
            elif _kw(cat, "Small"):
                style_found = "Small Blend"
        # Only set for equity-like funds
        if style_found and not _kw(cat, "Bond", "Fixed", "Treasury", "Income",
                                    "TIPS", "Money"):
            result["equity_style"] = style_found
        else:
            result["equity_style"] = ""
    else:
        result["equity_style"] = ""

    # ── FI Style / FI Sector ────────────────────────────────────
    # Best-effort; mostly left blank for manual override
    result["fi_style"] = ""
    result["fi_sector"] = ""
    if sec_type == "BOND" or _kw(ac, "Bond", "TIPS"):
        if _kw(cat, "Treasury", "Government", "Sovereign"):
            result["fi_sector"] = "Government/Sovereign"
        elif _kw(cat, "Corporate") and _kw(ac, "High-Yield"):
            result["fi_sector"] = "HY Corporate"
        elif _kw(cat, "Corporate"):
            result["fi_sector"] = "IG Corporate"
        elif _kw(cat, "Municipal", "Muni"):
            result["fi_sector"] = "Municipal"
        elif _kw(cat, "TIPS", "Inflation"):
            result["fi_sector"] = "TIPS/Inflation"
        elif _kw(cat, "Securitized", "MBS", "Mortgage"):
            result["fi_sector"] = "Securitized"

    # ── Factor ──────────────────────────────────────────────────
    if sec_type in ("BOND", "CASH") or _kw(ac, "Bond", "Cash", "TIPS"):
        result["factor"] = "N/A"
    elif _kw(cat, "Dividend", "High Yield", "Income") and not _kw(ac, "Bond"):
        result["factor"] = "High Yield/Dividend"
    elif _kw(cat, "Value"):
        result["factor"] = "Value"
    elif _kw(cat, "Growth"):
        result["factor"] = "Growth"
    elif _kw(cat, "Quality"):
        result["factor"] = "Quality"
    elif _kw(cat, "Momentum"):
        result["factor"] = "Momentum"
    elif _kw(cat, "Low Vol", "Min Vol"):
        result["factor"] = "Low Volatility"
    elif _kw(cat, "Small Cap", "Small-Cap"):
        result["factor"] = "Size (Small Cap)"
    elif _kw(cat, "Total Market", "S&P 500", "Broad", "Index"):
        result["factor"] = "Broad/Market-Weight"
    elif sec_type == "EQUITY":
        result["factor"] = "Broad/Market-Weight"
    else:
        result["factor"] = "Broad/Market-Weight"

    # ── Income Type ─────────────────────────────────────────────
    if sec_type in ("BOND", "CASH") or _kw(ac, "Cash", "Investment-Grade",
                                            "TIPS", "Intl/EM Bond"):
        if _kw(cat, "Municipal", "Muni", "Tax-Exempt"):
            result["income_type"] = "Tax-Exempt Interest"
        else:
            result["income_type"] = "Interest/Coupon"
    elif _kw(ac, "High-Yield Bond"):
        result["income_type"] = "Interest/Coupon"
    elif _kw(sector, "Real Estate") or _kw(ac, "Real Estate", "REIT"):
        result["income_type"] = "Non-Qualified Dividends"
    elif _kw(ac, "Private Credit", "BDC"):
        result["income_type"] = "Non-Qualified Dividends"
    elif _kw(ac, "MLP"):
        result["income_type"] = "Return of Capital"
    elif _kw(cat, "Covered Call", "Option", "Buy-Write"):
        result["income_type"] = "Option Premium/Synthetic"
    elif div_yield > 0:
        result["income_type"] = "Qualified Dividends"
    else:
        result["income_type"] = "No Current Income"

    # ── Vehicle Type ────────────────────────────────────────────
    vt_map = {
        "EQUITY": "Individual Stock",
        "ETF": "ETF",
        "MUTUAL_FUND": "Open-End Mutual Fund",
        "BOND": "Individual Bond",
        "CASH": "Money Market Fund",
    }
    result["vehicle_type"] = vt_map.get(sec_type, "Other")

    return result


# ───────────────────────────────────────────────────────────────────────
# LLM-assisted classification via Perplexity API
# ───────────────────────────────────────────────────────────────────────

_PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


def _build_llm_prompt(symbol: str, description: str,
                       security_type: str, extra_context: str = "") -> str:
    """Build the classification prompt for the Perplexity API."""
    return f"""Classify the investment "{symbol}" ({description}, type: {security_type}) across these taxonomy dimensions.
{extra_context}
Return ONLY a valid JSON object with these exact keys and values chosen from the allowed lists below. Do not include any explanation, markdown formatting, or text outside the JSON.

Keys and allowed values:
- "asset_class": one of {json.dumps(ASSET_CLASSES)}
- "objective": one of {json.dumps(OBJECTIVES)}
- "region": one of {json.dumps(REGIONS)}
- "equity_style": one of {json.dumps(EQUITY_STYLES)} or "" if not equity
- "fi_style": one of {json.dumps(FI_STYLES)} or "" if not fixed-income
- "fi_sector": one of {json.dumps(FI_SECTORS)} or "" if not fixed-income
- "factor": one of {json.dumps(FACTORS)}
- "income_type": one of {json.dumps(INCOME_TYPES)}
- "vehicle_type": one of {json.dumps(VEHICLE_TYPES)}

Respond with ONLY the JSON object, no other text."""


def auto_classify_llm(
    symbol: str,
    description: str,
    security_type: str,
    api_key: str,
    extra_context: str = "",
) -> dict[str, str] | None:
    """Call the Perplexity API to classify a single symbol.

    Returns a dict of dimension values, or None on failure.
    """
    try:
        import httpx
    except ImportError:
        log.warning("httpx not installed — cannot call Perplexity API")
        return None

    prompt = _build_llm_prompt(symbol, description, security_type, extra_context)

    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "You are a financial data classifier. Respond with only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 500,
    }

    try:
        resp = httpx.post(
            _PERPLEXITY_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        result = json.loads(content)

        # Validate that returned values are in the allowed lists
        validated: dict[str, str] = {}
        for dim, allowed in DROPDOWN_VALUES.items():
            val = result.get(dim, "")
            if val in allowed:
                validated[dim] = val
            elif val == "" or val is None:
                validated[dim] = ""
            else:
                log.warning("LLM returned invalid %s='%s' for %s; using rule fallback",
                            dim, val, symbol)
                validated[dim] = ""

        log.info("LLM classified %s: %s", symbol, validated.get("asset_class", "?"))
        return validated

    except Exception as exc:
        # Re-raise 401 so the caller can disable LLM for remaining symbols
        # with a single log message rather than 401 noise for every symbol.
        try:
            from httpx import HTTPStatusError
            if isinstance(exc, HTTPStatusError) and exc.response.status_code == 401:
                raise
        except ImportError:
            pass
        log.warning("Perplexity API classification failed for %s", symbol, exc_info=True)
        return None


# ───────────────────────────────────────────────────────────────────────
# Combined classifier (LLM → rules fallback)
# ───────────────────────────────────────────────────────────────────────

def auto_classify(
    row: dict[str, Any],
    api_key: str | None = None,
) -> dict[str, str]:
    """Classify a holding across all taxonomy dimensions.

    Tries LLM first (if *api_key* is provided), falls back to rule-based.
    Returns ``{dimension_col: value}`` dict.
    """
    symbol = row.get("symbol", "")
    description = row.get("description", "")
    sec_type = row.get("security_type", "")

    # Build extra context from available data
    extra_parts = []
    if row.get("sector"):
        extra_parts.append(f"Sector: {row['sector']}")
    if row.get("industry"):
        extra_parts.append(f"Industry: {row['industry']}")
    if row.get("yf_category"):
        extra_parts.append(f"Category: {row['yf_category']}")
    if row.get("dividend_yield"):
        extra_parts.append(f"Dividend yield: {row['dividend_yield']:.2%}")
    if row.get("market_cap"):
        extra_parts.append(f"Market cap: ${row['market_cap']:,.0f}")
    extra_context = "\n".join(extra_parts)

    # Try LLM classification first
    if api_key:
        llm_result = auto_classify_llm(
            symbol, description, sec_type, api_key, extra_context
        )
        if llm_result:
            # Fill any blank dimensions from rules
            rule_result = auto_classify_rules(row)
            for dim in DIMENSION_COLS:
                if not llm_result.get(dim):
                    llm_result[dim] = rule_result.get(dim, "")
            return llm_result

    # Fallback: pure rule-based
    return auto_classify_rules(row)


# ───────────────────────────────────────────────────────────────────────
# Google Sheets I/O
# ───────────────────────────────────────────────────────────────────────

def _get_worksheet(gs_creds_path: str):
    """Open the Allocations worksheet, return (gc, worksheet)."""
    import pygsheets

    gc = pygsheets.authorize(service_file=gs_creds_path)
    wb = gc.open("Portfolio")

    try:
        ws = wb.worksheet_by_title("Allocations")
    except pygsheets.WorksheetNotFound:
        ws = wb.add_worksheet("Allocations", rows=200, cols=len(SHEET_COLUMNS))
        # Write header row
        ws.update_row(1, SHEET_COLUMNS)
        log.info("Created 'Allocations' worksheet with %d columns", len(SHEET_COLUMNS))

    return gc, ws


def read_sheet(gs_creds_path: str) -> pd.DataFrame:
    """Read the Allocations sheet into a DataFrame with internal column names."""
    _, ws = _get_worksheet(gs_creds_path)
    df = ws.get_as_df(has_header=True, include_tailing_empty=False,
                       include_tailing_empty_rows=False)

    if df.empty:
        return pd.DataFrame(columns=list(HEADER_TO_COL.values()))

    # Rename to internal column names
    rename_map = {h: c for h, c in HEADER_TO_COL.items() if h in df.columns}
    df = df.rename(columns=rename_map)

    # Convert numeric columns
    for col in LOOK_THROUGH_COLS + ["risk_score", "manual_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def write_sheet(gs_creds_path: str, df: pd.DataFrame) -> None:
    """Write the overrides DataFrame back to the Allocations sheet."""
    _, ws = _get_worksheet(gs_creds_path)

    # Convert to Sheet column names
    out = df.copy()
    rename_map = {c: h for c, h in COL_TO_HEADER.items() if c in out.columns}
    out = out.rename(columns=rename_map)

    # Ensure all expected columns exist in the right order
    for col in SHEET_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out = out[SHEET_COLUMNS]

    # Replace NaN with empty string for Sheet
    out = out.fillna("")

    # Clear the sheet and rewrite
    ws.clear()
    ws.update_row(1, SHEET_COLUMNS)
    if not out.empty:
        ws.set_dataframe(out, (1, 1), fit=False, copy_head=True)

    log.info("Wrote %d rows to Allocations sheet", len(out))


def setup_dropdowns(gs_creds_path: str) -> None:
    """Install data-validation dropdowns on the Allocations worksheet.

    Sets column-level validation for each taxonomy dimension so the user
    sees a dropdown selector in Google Sheets.  Uses the Sheets API
    batchUpdate directly — pygsheets DataRange does not expose a
    set_data_validation() method.
    """
    _, ws = _get_worksheet(gs_creds_path)

    # Column index mapping (1-based)
    header_to_idx = {h: i + 1 for i, h in enumerate(SHEET_COLUMNS)}

    requests = []
    for dim_col, values in DROPDOWN_VALUES.items():
        header = COL_TO_HEADER.get(dim_col, "")
        col_idx = header_to_idx.get(header)
        if not col_idx:
            continue

        # Sheets API uses 0-based, end-exclusive indices
        requests.append({
            "setDataValidation": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": 1,          # row 2 (skip header)
                    "endRowIndex": 200,
                    "startColumnIndex": col_idx - 1,
                    "endColumnIndex": col_idx,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": v} for v in values],
                    },
                    "showCustomUi": True,
                    "strict": False,
                    "inputMessage": f"Select a {header} value",
                },
            }
        })

    if requests:
        try:
            ws.spreadsheet.custom_request(requests, fields='*')
        except Exception:
            log.warning("Failed to install dropdown validation", exc_info=True)

    log.info("Dropdown validation installed on Allocations sheet")


# ───────────────────────────────────────────────────────────────────────
# Sync + classify orchestrator
# ───────────────────────────────────────────────────────────────────────

def sync_and_classify(
    holdings_df: pd.DataFrame,
    gs_creds_path: str,
    perplexity_api_key: str | None = None,
    setup_dropdowns_flag: bool = True,
) -> pd.DataFrame:
    """Main entry point: sync symbols, auto-classify new ones, write back.

    1. Read the current Sheet
    2. Add new symbols (from holdings) with auto-classification
    3. Remove sold symbols
    4. Update descriptions for existing symbols
    5. Write updated data back to Sheet
    6. Optionally install dropdown validation
    7. Return the overrides DataFrame (internal column names)

    Args:
        holdings_df: Canonical holdings (must have symbol, description, etc.)
        gs_creds_path: Path to Google service account JSON.
        perplexity_api_key: Optional Perplexity API key for LLM classification.
        setup_dropdowns_flag: Whether to install dropdown validation.
    """
    # 1. Read current sheet
    overrides_df = read_sheet(gs_creds_path)

    current_symbols = set(holdings_df["symbol"].unique())
    existing_symbols = set(overrides_df["symbol"].unique()) if not overrides_df.empty else set()

    # 2. Classify and add new symbols
    new_symbols = current_symbols - existing_symbols
    if new_symbols:
        log.info("Classifying %d new symbols: %s", len(new_symbols),
                 ", ".join(sorted(new_symbols)[:10]))

        # Build a lookup from holdings for enrichment data
        # De-duplicate: pick the first row per symbol (may appear in multiple accounts)
        holdings_lookup = holdings_df.drop_duplicates("symbol").set_index("symbol")

        new_rows = []
        effective_api_key = perplexity_api_key  # may be set to None on first 401
        for sym in sorted(new_symbols):
            row_data: dict[str, Any] = {"symbol": sym}

            if sym in holdings_lookup.index:
                h = holdings_lookup.loc[sym]
                row_data["description"] = h.get("description", "")
                row_data["security_type"] = h.get("security_type", "")
                row_data["sector"] = h.get("sector", "")
                row_data["industry"] = h.get("industry", "")
                row_data["dividend_yield"] = h.get("dividend_yield", 0)
                row_data["market_cap"] = h.get("market_cap", 0)
                row_data["pe_ratio"] = h.get("pe_ratio", 0)
            else:
                row_data["description"] = ""

            # Auto-classify — fall back to rules immediately on auth failure
            try:
                classification = auto_classify(row_data, api_key=effective_api_key)
            except Exception as exc:
                try:
                    from httpx import HTTPStatusError
                    if isinstance(exc, HTTPStatusError) and exc.response.status_code == 401:
                        log.warning(
                            "Perplexity API key is invalid or expired (401 Unauthorized). "
                            "Switching to rule-based classification for all remaining symbols. "
                            "Run 'portfolio setup' to update the key."
                        )
                        effective_api_key = None
                        classification = auto_classify_rules(row_data)
                    else:
                        raise
                except ImportError:
                    raise exc

            # Build the new row
            new_row: dict[str, Any] = {
                "symbol": sym,
                "description": row_data.get("description", ""),
                "sector": row_data.get("sector", "") or "",
                "industry": row_data.get("industry", "") or "",
            }
            new_row.update(classification)
            new_rows.append(new_row)

        new_df = pd.DataFrame(new_rows)
        if overrides_df.empty:
            overrides_df = new_df
        else:
            overrides_df = pd.concat([overrides_df, new_df], ignore_index=True)

    # 3. Remove sold symbols
    sold_symbols = existing_symbols - current_symbols
    if sold_symbols:
        overrides_df = overrides_df[~overrides_df["symbol"].isin(sold_symbols)]
        log.info("Removed %d sold symbols from allocations", len(sold_symbols))

    # 4. Update descriptions for existing symbols
    if not overrides_df.empty:
        desc_map = (
            holdings_df.drop_duplicates("symbol")
            .set_index("symbol")["description"]
            .to_dict()
        )
        mask = overrides_df["symbol"].isin(desc_map)
        overrides_df.loc[mask, "description"] = overrides_df.loc[mask, "symbol"].map(desc_map)

        # Also update sector/industry from holdings if currently blank
        sector_map = (
            holdings_df.drop_duplicates("symbol")
            .set_index("symbol")
        )
        for col in ["sector", "industry"]:
            if col in sector_map.columns and col in overrides_df.columns:
                empty_mask = mask & (
                    overrides_df[col].isna() | (overrides_df[col] == "")
                )
                if empty_mask.any():
                    overrides_df.loc[empty_mask, col] = (
                        overrides_df.loc[empty_mask, "symbol"]
                        .map(sector_map[col].to_dict())
                    )

    # Sort by symbol for consistency
    overrides_df = overrides_df.sort_values("symbol").reset_index(drop=True)

    # 5. Write back to Sheet
    try:
        write_sheet(gs_creds_path, overrides_df)
    except Exception:
        log.exception("Failed to write allocations to Google Sheet")

    # 6. Optionally install dropdowns
    if setup_dropdowns_flag:
        try:
            setup_dropdowns(gs_creds_path)
        except Exception:
            log.exception("Failed to set up dropdown validation")

    return overrides_df
