"""Asset allocation metrics.

Breaks down the portfolio by security type, sector, account, and asset class.
Results are saved to ~/data/portfolio/metrics/allocation/.

All functions accept the canonical holdings DataFrame from DataReader.current_holdings().
"""

import logging

import pandas as pd

from portfolio import config
from portfolio.storage import writer

log = logging.getLogger(__name__)

CATEGORY = "allocation"


# ---------------------------------------------------------------------------
# Individual breakdowns
# ---------------------------------------------------------------------------

def by_security_type(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by security type (EQUITY, ETF, MUTUAL_FUND, BOND, CASH).

    Returns:
        DataFrame with columns: security_type, market_value, portfolio_pct
    """
    if holdings.empty or "security_type" not in holdings.columns:
        return pd.DataFrame(columns=["security_type", "market_value", "portfolio_pct"])

    grp = (
        holdings.groupby("security_type", as_index=False)["market_value"]
        .sum()
        .sort_values("market_value", ascending=False)
    )
    total = grp["market_value"].sum()
    grp["portfolio_pct"] = grp["market_value"] / total if total else 0.0
    return grp.reset_index(drop=True)


def by_sector(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by sector (from yfinance enrichment).

    Excludes cashBalance positions and sectors classified as 'Cash'.

    Returns:
        DataFrame with columns: sector, market_value, portfolio_pct
    """
    if holdings.empty or "sector" not in holdings.columns:
        return pd.DataFrame(columns=["sector", "market_value", "portfolio_pct"])

    mask = (
        (holdings["symbol"] != "cashBalance") &
        (holdings["sector"].notna()) &
        (holdings["sector"] != "")
    )
    df = holdings[mask]
    if df.empty:
        return pd.DataFrame(columns=["sector", "market_value", "portfolio_pct"])

    grp = (
        df.groupby("sector", as_index=False)["market_value"]
        .sum()
        .sort_values("market_value", ascending=False)
    )
    total = holdings["market_value"].sum()  # pct of *total* portfolio
    grp["portfolio_pct"] = grp["market_value"] / total if total else 0.0
    return grp.reset_index(drop=True)


def by_account(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by account.

    Returns:
        DataFrame with columns: account_id, account_name, market_value, portfolio_pct
    """
    if holdings.empty:
        return pd.DataFrame(
            columns=["account_id", "account_name", "market_value", "portfolio_pct"]
        )

    grp = (
        holdings.groupby(["account_id", "account_name"], as_index=False)["market_value"]
        .sum()
        .sort_values("market_value", ascending=False)
    )
    total = grp["market_value"].sum()
    grp["portfolio_pct"] = grp["market_value"] / total if total else 0.0
    return grp.reset_index(drop=True)


def by_asset_class(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by asset class.

    Uses the ``asset_class`` column populated from Google Sheet overrides.
    Falls back to ``security_type`` for any position without an override.

    Returns:
        DataFrame with columns: asset_class, market_value, portfolio_pct
    """
    if holdings.empty:
        return pd.DataFrame(columns=["asset_class", "market_value", "portfolio_pct"])

    df = holdings.copy()

    # Fill missing asset_class from security_type
    fallback_map = {
        "EQUITY":     "Domestic Stock",
        "ETF":        "Domestic Stock",
        "MUTUAL_FUND": "Domestic Stock",
        "BOND":       "Domestic Bond",
        "CASH":       "Cash",
    }
    empty_mask = df["asset_class"].isna() | (df["asset_class"] == "")
    df.loc[empty_mask, "asset_class"] = (
        df.loc[empty_mask, "security_type"].map(fallback_map).fillna("Unknown")
    )

    grp = (
        df.groupby("asset_class", as_index=False)["market_value"]
        .sum()
        .sort_values("market_value", ascending=False)
    )
    total = grp["market_value"].sum()
    grp["portfolio_pct"] = grp["market_value"] / total if total else 0.0
    return grp.reset_index(drop=True)


def by_source(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by data source (schwab vs ml_benefits).

    Returns:
        DataFrame with columns: source, market_value, portfolio_pct
    """
    if holdings.empty or "source" not in holdings.columns:
        return pd.DataFrame(columns=["source", "market_value", "portfolio_pct"])

    grp = (
        holdings.groupby("source", as_index=False)["market_value"]
        .sum()
        .sort_values("market_value", ascending=False)
    )
    total = grp["market_value"].sum()
    grp["portfolio_pct"] = grp["market_value"] / total if total else 0.0
    return grp.reset_index(drop=True)


# ---------------------------------------------------------------------------
# New taxonomy dimension breakdowns
# ---------------------------------------------------------------------------

def _group_by_dimension(
    holdings: pd.DataFrame,
    dim_col: str,
    label: str | None = None,
) -> pd.DataFrame:
    """Generic helper: group by a taxonomy dimension column."""
    label = label or dim_col
    if holdings.empty or dim_col not in holdings.columns:
        return pd.DataFrame(columns=[dim_col, "market_value", "portfolio_pct"])

    df = holdings.copy()
    # Fill blanks with "Unclassified"
    df[dim_col] = df[dim_col].fillna("").replace("", "Unclassified")

    grp = (
        df.groupby(dim_col, as_index=False)["market_value"]
        .sum()
        .sort_values("market_value", ascending=False)
    )
    total = grp["market_value"].sum()
    grp["portfolio_pct"] = grp["market_value"] / total if total else 0.0
    return grp.reset_index(drop=True)


def by_objective(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by investment objective (Growth/Income/Preservation).

    Returns:
        DataFrame with columns: objective, market_value, portfolio_pct
    """
    return _group_by_dimension(holdings, "objective")


def by_region(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by geographic region (US/Developed/EM/Global).

    Returns:
        DataFrame with columns: region, market_value, portfolio_pct
    """
    return _group_by_dimension(holdings, "region")


def by_equity_style(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by Morningstar equity style (Large Value, etc.).

    Excludes non-equity positions (where equity_style is blank).

    Returns:
        DataFrame with columns: equity_style, market_value, portfolio_pct
    """
    if holdings.empty or "equity_style" not in holdings.columns:
        return pd.DataFrame(columns=["equity_style", "market_value", "portfolio_pct"])

    df = holdings[
        holdings["equity_style"].notna() & (holdings["equity_style"] != "")
    ]
    if df.empty:
        return pd.DataFrame(columns=["equity_style", "market_value", "portfolio_pct"])

    grp = (
        df.groupby("equity_style", as_index=False)["market_value"]
        .sum()
        .sort_values("market_value", ascending=False)
    )
    total = holdings["market_value"].sum()  # pct of TOTAL portfolio
    grp["portfolio_pct"] = grp["market_value"] / total if total else 0.0
    return grp.reset_index(drop=True)


def by_income_type(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by income type.

    Returns:
        DataFrame with columns: income_type, market_value, portfolio_pct
    """
    return _group_by_dimension(holdings, "income_type")


def by_vehicle_type(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by vehicle type (ETF, Stock, Mutual Fund, etc.).

    Returns:
        DataFrame with columns: vehicle_type, market_value, portfolio_pct
    """
    return _group_by_dimension(holdings, "vehicle_type")


def by_factor(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by factor exposure (Value, Growth, Quality, etc.).

    Returns:
        DataFrame with columns: factor, market_value, portfolio_pct
    """
    return _group_by_dimension(holdings, "factor")


def by_tax_treatment(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio allocation by account tax treatment.

    Returns:
        DataFrame with columns: tax_treatment, market_value, portfolio_pct
    """
    return _group_by_dimension(holdings, "tax_treatment")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def compute_all(holdings: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Compute all allocation breakdowns and save to metrics/allocation/.

    Args:
        holdings: Current canonical holdings DataFrame.

    Returns:
        Dict mapping metric name → DataFrame (also written to Parquet).
    """
    results = {}

    breakdowns = {
        "by_security_type": by_security_type,
        "by_sector":        by_sector,
        "by_account":       by_account,
        "by_asset_class":   by_asset_class,
        "by_source":        by_source,
        "by_objective":     by_objective,
        "by_region":        by_region,
        "by_equity_style":  by_equity_style,
        "by_income_type":   by_income_type,
        "by_vehicle_type":  by_vehicle_type,
        "by_factor":        by_factor,
        "by_tax_treatment": by_tax_treatment,
    }

    for name, fn in breakdowns.items():
        try:
            df = fn(holdings)
            writer.write_metrics(df, CATEGORY, name)
            results[name] = df
            log.debug("Allocation metric '%s': %d rows", name, len(df))
        except Exception:
            log.exception("Failed to compute allocation metric: %s", name)

    log.info("Allocation metrics written (%d breakdowns)", len(results))
    return results
