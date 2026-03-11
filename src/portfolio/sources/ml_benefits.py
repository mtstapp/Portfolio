"""Merrill Lynch Benefits 401k CSV parser.

Parses the holdings export from benefits.ml.com and converts it to the
canonical holdings schema for use by the portfolio pipeline.

Supported CSV format (export from ML Benefits "Accounts" view):
    Asset Class, Investment, Ticker, % of Account, Market Value,
    Vested Balance, Equivalent Shares, Shares/Units/Bonds,
    Closing Price, Change in Price, Cost Basis

Special ticker handling:
  - Valid tickers (e.g. VTSNX, VBTIX, BAC) → used as-is
  - "N/A" (institutional-only funds) → synthetic "ML.<NAME>" symbol
  - "CIT*" (Collective Investment Trusts) → synthetic "ML.<NAME>" symbol

Usage:
    portfolio import ml-benefits ~/Downloads/investments.csv
"""

import logging
import re
from datetime import date
from pathlib import Path

import pandas as pd

from portfolio.storage import schema

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Account constants
# ---------------------------------------------------------------------------

ACCOUNT_ID   = "BOA401K"
ACCOUNT_NAME = "BofA 401k"
ACCOUNT_TYPE = "401K"
SOURCE       = "ml_benefits"

# Words to strip when generating synthetic symbols from fund names
_STOP_WORDS = {
    "FUND", "TRUST", "CIT", "IV", "III", "II", "I",
    "THE", "OF", "AND", "A", "K", "CLASS", "INSTL",
    "INSTITUTIONAL", "TOTAL", "INDEX",
}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_dollar(s) -> float:
    """'$136,474.62 ' → 136474.62.  Handles None / empty / N/A → 0.0."""
    if pd.isna(s) or str(s).strip() in ("", "N/A"):
        return 0.0
    cleaned = re.sub(r"[$, ]", "", str(s))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_pct(s) -> float:
    """'18.62%' → 0.1862.  Handles None / empty → 0.0."""
    if pd.isna(s) or str(s).strip() in ("", "N/A"):
        return 0.0
    cleaned = re.sub(r"[%, ]", "", str(s))
    try:
        return float(cleaned) / 100.0
    except ValueError:
        return 0.0


def _parse_float(s) -> float:
    """Parse a plain numeric string.  Handles None / empty → 0.0."""
    if pd.isna(s) or str(s).strip() in ("", "N/A"):
        return 0.0
    try:
        return float(str(s).strip())
    except ValueError:
        return 0.0


def _make_symbol(ticker: str, name: str) -> str:
    """Return a canonical symbol for the holding.

    Valid tickers are returned as-is.  N/A or CIT* tickers get a synthetic
    symbol derived from the fund name: ``ML.<WORD1>-<WORD2>-<WORD3>``.

    Examples:
        "VTSNX", "VTSNX"        → "VTSNX"
        "N/A",   "STABLE VALUE" → "ML.STABLE-VALUE"
        "CIT*",  "STATE ST REAL ASSET K" → "ML.STATE-ST-REAL"
    """
    ticker = str(ticker).strip()
    if ticker and ticker not in ("N/A", "CIT*", ""):
        return ticker
    # Generate from fund name: take up to 3 significant words
    words = re.sub(r"[^A-Z0-9 ]", "", name.upper()).split()
    parts = [w for w in words if w not in _STOP_WORDS][:3]
    return "ML." + "-".join(parts) if parts else "ML.UNKNOWN"


def _map_security_type(asset_class: str) -> str:
    """Map ML Benefits asset class string to canonical security_type.

    EQUITY/STOCK   → MUTUAL_FUND  (all 401k equity slots are institutional funds)
    BOND/FIXED INCOME → BOND
    STABLE VALUE   → CASH
    """
    ac = str(asset_class).strip().upper()
    if "STABLE" in ac:
        return "CASH"
    if "BOND" in ac or "FIXED" in ac:
        return "BOND"
    return "MUTUAL_FUND"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_csv(file_path: str | Path, as_of: date | None = None) -> pd.DataFrame:
    """Read an ML Benefits 401k CSV export and return a cleaned raw DataFrame.

    Args:
        file_path: Path to the CSV file downloaded from benefits.ml.com.
        as_of:     Date to stamp on records. Defaults to today.

    Returns:
        DataFrame with standardised column names and cleaned numeric values.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"ML Benefits CSV not found: {file_path}")

    raw = pd.read_csv(file_path)
    raw.columns = [c.strip() for c in raw.columns]   # strip whitespace from headers
    log.info("Read %d rows from %s", len(raw), file_path.name)

    effective_date = as_of or date.today()

    df = pd.DataFrame()
    df["as_of"]          = effective_date
    df["asset_class_raw"] = raw["Asset Class"].str.strip()
    df["description"]    = raw["Investment"].str.strip()
    df["ticker_raw"]     = raw["Ticker"].str.strip()
    df["symbol"]         = df.apply(
        lambda r: _make_symbol(r["ticker_raw"], r["description"]), axis=1
    )
    df["security_type"]  = df["asset_class_raw"].apply(_map_security_type)
    df["portfolio_pct"]  = raw["% of Account"].apply(_parse_pct)
    df["market_value"]   = raw["Market Value"].apply(_parse_dollar)
    df["cost_basis"]     = raw["Cost Basis"].apply(_parse_dollar)
    df["quantity"]       = raw["Shares/Units/Bonds"].apply(_parse_float)
    df["current_price"]  = raw["Closing Price"].apply(_parse_dollar)

    # average_price = cost_basis per unit (falls back to current price if no units)
    df["average_price"] = df.apply(
        lambda r: (r["cost_basis"] / r["quantity"])
        if r["quantity"] > 0 else r["current_price"],
        axis=1,
    )

    log.info(
        "Parsed %d ML Benefits positions (total: $%s)",
        len(df),
        f"{df['market_value'].sum():,.0f}",
    )
    return df


def to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """Convert a parsed ML Benefits DataFrame to the canonical HOLDINGS_SCHEMA.

    Sets account_id='BOA401K', account_name='BofA 401k', source='ml_benefits'.
    Fundamental/enrichment columns (beta, dividends, etc.) are zero-filled because
    they are not available in the CSV export.
    """
    if df.empty:
        return pd.DataFrame(columns=schema.HOLDINGS_COLS)

    out = pd.DataFrame()
    out["date"]          = pd.to_datetime(df["as_of"]).dt.date
    out["account_id"]    = ACCOUNT_ID
    out["account_name"]  = ACCOUNT_NAME
    out["source"]        = SOURCE
    out["symbol"]        = df["symbol"]
    out["description"]   = df["description"]
    out["security_type"] = df["security_type"]
    out["quantity"]      = df["quantity"]
    out["average_price"] = df["average_price"]
    out["current_price"] = df["current_price"]
    out["market_value"]  = df["market_value"]
    out["cost_basis"]    = df["cost_basis"]
    out["gain_loss"]     = df["market_value"] - df["cost_basis"]
    out["portfolio_pct"] = df["portfolio_pct"]

    # Sector / industry — inferred from security type (no yfinance for 401k funds)
    _sector_map = {"CASH": "Cash", "BOND": "Bond", "MUTUAL_FUND": "Fund"}
    _industry_map = {"CASH": "Cash", "BOND": "Fixed Income", "MUTUAL_FUND": "Mutual Fund"}
    out["sector"]   = df["security_type"].map(_sector_map).fillna("Unknown")
    out["industry"] = df["security_type"].map(_industry_map).fillna("Unknown")

    # Columns not available from CSV — default to empty / zero
    out["asset_class"] = ""
    for col in [
        "risk_score", "beta", "dividend_amount", "dividend_yield",
        "eps", "pe_ratio", "pb_ratio", "market_cap",
        "return_on_assets", "return_on_equity",
        "weighted_beta", "yoc", "div_annual_total",
    ]:
        out[col] = 0.0

    # Ensure all schema columns are present, then return in schema order
    canonical_cols = [f.name for f in schema.HOLDINGS_SCHEMA]
    for col in canonical_cols:
        if col not in out.columns:
            out[col] = None

    return out[canonical_cols]


def canonical_account_row(as_of: date | None = None, total_value: float = 0.0) -> dict:
    """Return a single dict representing the BofA 401k row for the accounts table."""
    return {
        "date":              as_of or date.today(),
        "account_id":        ACCOUNT_ID,
        "account_name":      ACCOUNT_NAME,
        "account_type":      ACCOUNT_TYPE,
        "source":            SOURCE,
        "liquidation_value": total_value,
        "cash_balance":      0.0,
        "total_value":       total_value,
    }
