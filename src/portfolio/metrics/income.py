"""Income metrics: projected dividends, yield, and distribution estimates.

Uses the fundamental data enriched during the Schwab pull (dividend_amount,
dividend_yield, div_annual_total, yoc columns).  ML Benefits positions will
show $0 income until fundamental data is added manually or via enrichment.

Results are saved to ~/data/portfolio/metrics/income/.
"""

import logging

import pandas as pd

from portfolio.storage import writer

log = logging.getLogger(__name__)

CATEGORY = "income"


# ---------------------------------------------------------------------------
# Individual metrics
# ---------------------------------------------------------------------------

def summary(holdings: pd.DataFrame) -> pd.DataFrame:
    """Total portfolio income summary.

    Returns:
        Single-row DataFrame with:
            total_projected_income, portfolio_yield_pct, paying_positions
    """
    if holdings.empty:
        return pd.DataFrame(
            columns=["total_projected_income", "portfolio_yield_pct", "paying_positions"]
        )

    div_col = "div_annual_total" if "div_annual_total" in holdings.columns else None
    if div_col is None:
        return pd.DataFrame(
            columns=["total_projected_income", "portfolio_yield_pct", "paying_positions"]
        )

    total_income  = holdings[div_col].sum()
    total_value   = holdings["market_value"].sum()
    yield_pct     = (total_income / total_value * 100) if total_value else 0.0
    paying        = int((holdings[div_col] > 0).sum())

    return pd.DataFrame([{
        "total_projected_income": total_income,
        "portfolio_yield_pct":    yield_pct,
        "paying_positions":       paying,
    }])


def by_position(holdings: pd.DataFrame) -> pd.DataFrame:
    """Per-position income detail, filtered to income-paying positions.

    Returns:
        DataFrame with columns:
            symbol, description, account_id, market_value,
            dividend_amount, dividend_yield, div_annual_total, yoc
        Sorted by div_annual_total descending.
    """
    if holdings.empty:
        return pd.DataFrame()

    income_cols = ["dividend_amount", "dividend_yield", "div_annual_total", "yoc"]
    available_income = [c for c in income_cols if c in holdings.columns]
    if not available_income:
        return pd.DataFrame()

    # Filter to positions that pay dividends
    if "div_annual_total" in holdings.columns:
        df = holdings[holdings["div_annual_total"] > 0].copy()
    else:
        df = holdings.copy()

    if df.empty:
        return df

    base_cols = ["symbol", "description", "account_id", "account_name", "market_value"]
    cols = [c for c in base_cols + available_income if c in df.columns]
    return (
        df[cols]
        .sort_values("div_annual_total", ascending=False)
        .reset_index(drop=True)
    )


def by_account(holdings: pd.DataFrame) -> pd.DataFrame:
    """Per-account projected income.

    Returns:
        DataFrame with columns:
            account_id, account_name, projected_income, yield_pct
    """
    if holdings.empty or "div_annual_total" not in holdings.columns:
        return pd.DataFrame(
            columns=["account_id", "account_name", "projected_income", "yield_pct"]
        )

    grp = holdings.groupby(
        ["account_id", "account_name"], as_index=False
    ).agg(
        projected_income=("div_annual_total", "sum"),
        market_value=("market_value", "sum"),
    )
    grp["yield_pct"] = grp.apply(
        lambda r: (r["projected_income"] / r["market_value"] * 100)
        if r["market_value"] else 0.0,
        axis=1,
    )
    return (
        grp[["account_id", "account_name", "projected_income", "yield_pct"]]
        .sort_values("projected_income", ascending=False)
        .reset_index(drop=True)
    )


def monthly_estimate(holdings: pd.DataFrame) -> pd.DataFrame:
    """Rough monthly income estimate (annual income / 12).

    Note: This is a simplification — actual dividend payment months vary.
    A more accurate calendar would require payment date data from transaction history.

    Returns:
        Single-row DataFrame with columns month_1 … month_12, each = income / 12.
    """
    if holdings.empty or "div_annual_total" not in holdings.columns:
        return pd.DataFrame(columns=[f"month_{m}" for m in range(1, 13)])

    annual = holdings["div_annual_total"].sum()
    monthly = annual / 12
    return pd.DataFrame([{f"month_{m}": monthly for m in range(1, 13)}])


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def compute_all(holdings: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Compute all income metrics and save to metrics/income/.

    Args:
        holdings: Current canonical holdings DataFrame.

    Returns:
        Dict mapping metric name → DataFrame.
    """
    results = {}

    metrics = {
        "summary":          lambda: summary(holdings),
        "by_position":      lambda: by_position(holdings),
        "by_account":       lambda: by_account(holdings),
        "monthly_estimate": lambda: monthly_estimate(holdings),
    }

    for name, fn in metrics.items():
        try:
            df = fn()
            writer.write_metrics(df, CATEGORY, name)
            results[name] = df
            log.debug("Income metric '%s': %d rows", name, len(df))
        except Exception:
            log.exception("Failed to compute income metric: %s", name)

    log.info("Income metrics written (%d metrics)", len(results))
    return results
