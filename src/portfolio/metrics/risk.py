"""Risk metrics: beta, volatility, Sharpe ratio, drawdown.

Beta and weighted beta are available immediately from Schwab fundamentals.
Volatility, Sharpe ratio, and max drawdown require sufficient daily snapshot
history (≥30 days) and will return empty DataFrames until then — they
populate automatically as daily refreshes accumulate data.

Results are saved to ~/data/portfolio/metrics/risk/.
"""

import logging

import pandas as pd

from portfolio.storage import writer

log = logging.getLogger(__name__)

CATEGORY = "risk"

_MIN_HISTORY_FOR_VOLATILITY = 30   # trading days
_RISK_FREE_RATE_ANNUAL = 0.045     # approximate 10-yr Treasury yield; update periodically
_TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# Individual metrics
# ---------------------------------------------------------------------------

def portfolio_beta_summary(holdings: pd.DataFrame) -> pd.DataFrame:
    """Portfolio-level beta summary.

    Returns:
        Single-row DataFrame with:
            portfolio_beta, total_value, beta_adjusted_exposure
    """
    if holdings.empty or "weighted_beta" not in holdings.columns:
        return pd.DataFrame(
            columns=["portfolio_beta", "total_value", "beta_adjusted_exposure"]
        )

    port_beta   = holdings["weighted_beta"].sum()
    total_value = holdings["market_value"].sum()

    return pd.DataFrame([{
        "portfolio_beta":          port_beta,
        "total_value":             total_value,
        "beta_adjusted_exposure":  port_beta * total_value,
    }])


def by_security_type(holdings: pd.DataFrame) -> pd.DataFrame:
    """Average beta (weighted by market value) broken down by security type.

    Returns:
        DataFrame with columns: security_type, avg_beta, market_value
    """
    if holdings.empty or "beta" not in holdings.columns:
        return pd.DataFrame(
            columns=["security_type", "avg_beta", "market_value"]
        )

    # Exclude zero-beta / unfilled rows (cash, bonds) from the average
    equities = holdings[holdings["beta"] > 0].copy()
    if equities.empty:
        return pd.DataFrame(columns=["security_type", "avg_beta", "market_value"])

    grp = equities.groupby("security_type", as_index=False).apply(
        lambda g: pd.Series({
            "avg_beta":    (g["beta"] * g["market_value"]).sum() / g["market_value"].sum(),
            "market_value": g["market_value"].sum(),
        }),
        include_groups=False,
    ).reset_index()

    return grp.sort_values("market_value", ascending=False).reset_index(drop=True)


def beta_distribution(holdings: pd.DataFrame) -> pd.DataFrame:
    """Per-position beta and its contribution to portfolio beta.

    Sorted by beta contribution (highest → biggest portfolio risk driver).

    Returns:
        DataFrame with columns:
            symbol, description, security_type, market_value,
            beta, portfolio_pct, beta_contribution
    """
    if holdings.empty or "beta" not in holdings.columns:
        return pd.DataFrame()

    df = holdings[holdings["beta"] > 0].copy()
    if df.empty:
        return df

    cols = [
        "symbol", "description", "security_type",
        "account_id", "market_value", "beta", "portfolio_pct", "weighted_beta",
    ]
    available = [c for c in cols if c in df.columns]
    result = df[available].rename(columns={"weighted_beta": "beta_contribution"})
    return result.sort_values("beta_contribution", ascending=False).reset_index(drop=True)


def volatility_and_sharpe(history_df: pd.DataFrame) -> pd.DataFrame:
    """Annualised volatility and Sharpe ratio from daily portfolio returns.

    Requires at least 30 daily snapshots.  Returns an empty DataFrame until
    sufficient history accumulates — this will populate over time.

    Args:
        history_df: DataFrame from DataReader.portfolio_value_history()
                    with columns: date, total_value

    Returns:
        Single-row DataFrame with:
            annualised_volatility_pct, sharpe_ratio, max_drawdown_pct,
            snapshot_count
    """
    if history_df.empty or len(history_df) < _MIN_HISTORY_FOR_VOLATILITY:
        log.debug(
            "volatility_and_sharpe: need >=%d snapshots, have %d — skipping",
            _MIN_HISTORY_FOR_VOLATILITY, len(history_df),
        )
        return pd.DataFrame(
            columns=[
                "annualised_volatility_pct", "sharpe_ratio",
                "max_drawdown_pct", "snapshot_count",
            ]
        )

    df = history_df.sort_values("date").copy()
    df["daily_return"] = df["total_value"].pct_change()
    df = df.dropna(subset=["daily_return"])

    # Annualised volatility
    vol_annual = df["daily_return"].std() * (_TRADING_DAYS_PER_YEAR ** 0.5) * 100

    # Sharpe ratio (using a constant risk-free rate approximation)
    daily_rf = _RISK_FREE_RATE_ANNUAL / _TRADING_DAYS_PER_YEAR
    excess   = df["daily_return"] - daily_rf
    sharpe   = (excess.mean() / excess.std() * (_TRADING_DAYS_PER_YEAR ** 0.5)) if excess.std() else 0.0

    # Max drawdown
    rolling_max = df["total_value"].cummax()
    drawdown    = (df["total_value"] - rolling_max) / rolling_max * 100
    max_dd      = drawdown.min()

    return pd.DataFrame([{
        "annualised_volatility_pct": vol_annual,
        "sharpe_ratio":              sharpe,
        "max_drawdown_pct":          max_dd,
        "snapshot_count":            len(history_df),
    }])


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def compute_all(
    holdings: pd.DataFrame,
    reader=None,
) -> dict[str, pd.DataFrame]:
    """Compute all risk metrics and save to metrics/risk/.

    Args:
        holdings: Current canonical holdings DataFrame.
        reader:   Optional DataReader for fetching portfolio history.

    Returns:
        Dict mapping metric name → DataFrame.
    """
    results = {}

    metrics = {
        "portfolio_beta":    lambda: portfolio_beta_summary(holdings),
        "by_security_type":  lambda: by_security_type(holdings),
        "beta_distribution": lambda: beta_distribution(holdings),
    }

    # History-dependent metrics
    if reader is not None:
        try:
            history = reader.portfolio_value_history(days=365)
            metrics["volatility_and_sharpe"] = lambda: volatility_and_sharpe(history)
        except Exception:
            log.debug("Could not load portfolio history for volatility metrics")

    for name, fn in metrics.items():
        try:
            df = fn()
            writer.write_metrics(df, CATEGORY, name)
            results[name] = df
            log.debug("Risk metric '%s': %d rows", name, len(df))
        except Exception:
            log.exception("Failed to compute risk metric: %s", name)

    log.info("Risk metrics written (%d metrics)", len(results))
    return results
