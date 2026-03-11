"""Transform raw source data into the canonical schema.

Each transform function takes a raw DataFrame (from a data source) and
returns a DataFrame conforming to the canonical schema in storage.schema.
"""

import logging
from datetime import date

import pandas as pd

from portfolio.storage import schema

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schwab positions → canonical holdings
# ---------------------------------------------------------------------------

def schwab_positions_to_canonical(
    raw_df: pd.DataFrame,
    as_of: date | None = None,
) -> pd.DataFrame:
    """Normalize raw Schwab position data to the canonical holdings schema."""
    if raw_df.empty:
        return pd.DataFrame(columns=schema.HOLDINGS_COLS)

    df = raw_df.copy()
    df["date"] = as_of or date.today()
    df["source"] = "schwab"

    # Ensure all required columns exist with defaults
    defaults = {
        "account_id": "",
        "account_name": "",
        "symbol": "",
        "description": "",
        "security_type": "UNKNOWN",
        "quantity": 0.0,
        "average_price": 0.0,
        "current_price": 0.0,
        "market_value": 0.0,
        "cost_basis": 0.0,
        "gain_loss": 0.0,
        "portfolio_pct": 0.0,
        "sector": "Unknown",
        "industry": "Unknown",
        "asset_class": "",
        "risk_score": 0.0,
        "beta": 0.0,
        "dividend_amount": 0.0,
        "dividend_yield": 0.0,
        "eps": 0.0,
        "pe_ratio": 0.0,
        "pb_ratio": 0.0,
        "market_cap": 0.0,
        "return_on_assets": 0.0,
        "return_on_equity": 0.0,
        "weighted_beta": 0.0,
        "yoc": 0.0,
        "div_annual_total": 0.0,
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # Recalculate derived fields
    df["gain_loss"] = df["market_value"] - df["cost_basis"]
    total = df["market_value"].sum()
    df["portfolio_pct"] = df["market_value"] / total if total else 0.0

    # Return only canonical columns in schema order
    return df[[f.name for f in schema.HOLDINGS_SCHEMA if f.name in df.columns]]


# ---------------------------------------------------------------------------
# Schwab accounts → canonical accounts
# ---------------------------------------------------------------------------

def schwab_accounts_to_canonical(
    raw_df: pd.DataFrame,
    as_of: date | None = None,
) -> pd.DataFrame:
    """Normalize raw Schwab account balances to the canonical accounts schema."""
    if raw_df.empty:
        return pd.DataFrame(columns=schema.ACCOUNTS_COLS)

    df = raw_df.copy()
    df["date"] = as_of or date.today()
    df["source"] = "schwab"

    defaults = {
        "account_type": "UNKNOWN",
        "liquidation_value": 0.0,
        "cash_balance": 0.0,
        "total_value": 0.0,
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    return df[[f.name for f in schema.ACCOUNTS_SCHEMA if f.name in df.columns]]


# ---------------------------------------------------------------------------
# Schwab transactions → canonical transactions
# ---------------------------------------------------------------------------

def schwab_transactions_to_canonical(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize raw Schwab transactions to the canonical schema."""
    if raw_df.empty:
        return pd.DataFrame(columns=schema.TRANSACTION_COLS)

    df = raw_df.copy()
    df["source"] = "schwab"

    # Normalise transaction type to lowercase standard names
    type_map = {
        "buy": "buy",
        "sell": "sell",
        "dividend": "dividend",
        "dividend_reinvestment": "dividend",
        "interest": "interest",
        "trade": "buy",
        "receive_and_deliver": "transfer",
    }
    df["transaction_type"] = df["transaction_type"].str.lower().map(
        lambda t: type_map.get(t, t)
    )

    defaults = {
        "quantity": 0.0,
        "price": 0.0,
        "amount": 0.0,
        "fees": 0.0,
        "symbol": "",
        "account_id": "",
        "account_name": "",
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    return df[[f.name for f in schema.TRANSACTIONS_SCHEMA if f.name in df.columns]]


# ---------------------------------------------------------------------------
# ML Benefits → canonical holdings
# ---------------------------------------------------------------------------

def ml_benefits_to_canonical(
    raw_df: "pd.DataFrame",
    as_of: date | None = None,
) -> "pd.DataFrame":
    """Normalize a parsed ML Benefits DataFrame to the canonical holdings schema.

    Thin wrapper around ml_benefits.to_canonical() that follows the same
    transform pattern as schwab_positions_to_canonical().
    """
    from portfolio.sources import ml_benefits as _ml

    if raw_df.empty:
        return pd.DataFrame(columns=schema.HOLDINGS_COLS)

    # If the DataFrame came from a raw Parquet (already has canonical columns),
    # return it directly; otherwise run the full parse.
    if "account_id" in raw_df.columns and "source" in raw_df.columns:
        # Already in canonical form (loaded from raw Parquet by daily_refresh)
        df = raw_df.copy()
        if as_of:
            df["date"] = as_of
        return df[[f.name for f in schema.HOLDINGS_SCHEMA if f.name in df.columns]]

    return _ml.to_canonical(raw_df)


# ---------------------------------------------------------------------------
# Merge allocation overrides into holdings
# ---------------------------------------------------------------------------

def apply_allocation_overrides(
    holdings_df: pd.DataFrame,
    overrides_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge manual allocation data (Google Sheet) into holdings.

    Preserves existing asset_class / risk_score if overrides are absent for
    a symbol. For look-through columns (pct_*), also merges them.
    """
    if overrides_df.empty:
        return holdings_df

    override_cols = ["symbol", "asset_class", "risk_score"] + schema.LOOK_THROUGH_COLS
    override_cols = [c for c in override_cols if c in overrides_df.columns]

    merged = holdings_df.merge(
        overrides_df[override_cols],
        on="symbol",
        how="left",
        suffixes=("", "_override"),
    )

    # Prefer override values where present
    for col in ["asset_class", "risk_score"]:
        override_col = f"{col}_override"
        if override_col in merged.columns:
            merged[col] = merged[override_col].combine_first(merged[col])
            merged.drop(columns=[override_col], inplace=True)

    # Pull in look-through cols that may not be in holdings_df
    for col in schema.LOOK_THROUGH_COLS:
        override_col = f"{col}_override"
        if override_col in merged.columns:
            merged[col] = merged[override_col]
            merged.drop(columns=[override_col], inplace=True)
        elif col not in merged.columns:
            merged[col] = 0.0

    return merged


# ---------------------------------------------------------------------------
# Sync allocation sheet symbols with current holdings
# ---------------------------------------------------------------------------

def sync_allocation_symbols(
    holdings_df: pd.DataFrame,
    overrides_df: pd.DataFrame,
) -> pd.DataFrame:
    """Add new symbols / remove sold symbols from the allocation overrides.

    - New symbols get a blank row (user fills in allocation manually)
    - Sold symbols are removed
    - Existing manual data is preserved
    """
    current_symbols = set(holdings_df["symbol"].unique())

    if overrides_df.empty:
        # Bootstrap: create a row per symbol with empty overrides
        new_rows = []
        for sym in sorted(current_symbols):
            desc = holdings_df.loc[holdings_df["symbol"] == sym, "description"].iloc[0] \
                   if not holdings_df.empty else ""
            new_rows.append({"symbol": sym, "description": desc})
        return pd.DataFrame(new_rows)

    existing_symbols = set(overrides_df["symbol"].unique())

    # Add new symbols
    new_symbols = current_symbols - existing_symbols
    if new_symbols:
        new_rows = []
        for sym in sorted(new_symbols):
            desc = holdings_df.loc[holdings_df["symbol"] == sym, "description"].iloc[0] \
                   if sym in holdings_df["symbol"].values else ""
            new_rows.append({"symbol": sym, "description": desc})
        overrides_df = pd.concat(
            [overrides_df, pd.DataFrame(new_rows)], ignore_index=True
        )

    # Remove sold symbols
    sold_symbols = existing_symbols - current_symbols
    if sold_symbols:
        overrides_df = overrides_df[~overrides_df["symbol"].isin(sold_symbols)]

    # Update descriptions for existing symbols
    desc_map = holdings_df.set_index("symbol")["description"].to_dict()
    overrides_df["description"] = overrides_df["symbol"].map(
        lambda s: desc_map.get(s, overrides_df.loc[overrides_df["symbol"] == s, "description"].iloc[0]
                               if not overrides_df.empty else "")
    )

    return overrides_df.reset_index(drop=True)
