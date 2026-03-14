"""Daily ETL pipeline: Extract → Transform → Load.

Called by launchd at 4:30 PM ET on trading days, and by 'portfolio refresh'.

Pipeline steps:
  1. Check if today is a trading day; skip if weekend/holiday
  2. Check Schwab token health; warn if expiring soon
  3. Pull Schwab data (accounts, positions, transactions)
  4. Write raw Parquet snapshots
  5. Transform to canonical schema
  6. Write canonical Parquet (current + dated snapshot)
  7. Read allocation overrides from Google Sheet (if configured)
  8. Merge overrides into canonical holdings
  9. Write updated canonical holdings
  10. Log summary
"""

import logging
import subprocess
import sys
from datetime import date, datetime

from portfolio import config
from portfolio.auth import schwab_oauth
from portfolio.pipeline import transforms
from portfolio.sources import schwab_client
from portfolio.storage import reader as _reader
from portfolio.storage import writer

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trading day check
# ---------------------------------------------------------------------------

def is_trading_day(as_of: date | None = None) -> bool:
    """Return True if the given date is a US stock market trading day."""
    d = as_of or date.today()
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    if d.isoformat() in config.MARKET_HOLIDAYS_2026:
        return False
    return True


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(force: bool = False, skip_sector: bool = False) -> dict:
    """Run the full daily data refresh.

    Args:
        force: Run even if today is not a trading day.
        skip_sector: Skip yfinance sector enrichment (faster, for testing).

    Returns:
        Summary dict with counts and status.
    """
    today = date.today()
    summary = {
        "date": today.isoformat(),
        "status": "skipped",
        "accounts": 0,
        "positions": 0,
        "transactions": 0,
        "errors": [],
    }

    if not force and not is_trading_day(today):
        log.info("Skipping refresh – not a trading day (%s)", today.strftime("%A %Y-%m-%d"))
        return summary

    log.info("=== Starting daily refresh: %s ===", today.isoformat())
    config.ensure_dirs()

    # Token health check
    days_left = schwab_oauth.token_days_remaining()
    if days_left is not None:
        if days_left < 1:
            log.error("Schwab token EXPIRED. Run: portfolio auth")
            summary["status"] = "error"
            summary["errors"].append("Token expired")
            _notify("Portfolio: Re-authentication required",
                    "Schwab token has expired. Run: portfolio auth")
            return summary
        if days_left < 2:
            log.warning("Schwab token expires in %.1f days!", days_left)
            _notify("Portfolio: Re-authenticate soon",
                    f"Schwab token expires in {days_left:.1f} days. Run: portfolio auth")

    # 1. Extract from Schwab
    log.info("Pulling Schwab data...")
    try:
        accounts_df, positions_df, transactions_df = schwab_client.pull_all(
            include_fundamentals=True,
            include_sector=not skip_sector,
        )
    except Exception as exc:
        log.exception("Schwab pull failed")
        summary["status"] = "error"
        summary["errors"].append(f"Schwab pull: {exc}")
        return summary

    # 2. Write raw Parquet
    writer.write_raw(accounts_df, "schwab", "accounts", today)
    writer.write_raw(positions_df, "schwab", "positions", today)
    if not transactions_df.empty:
        writer.write_raw(transactions_df, "schwab", "transactions", today)

    summary["accounts"] = len(accounts_df)
    summary["positions"] = len(positions_df)
    summary["transactions"] = len(transactions_df)

    # 3. Transform to canonical schema
    canonical_holdings = transforms.schwab_positions_to_canonical(positions_df, today)
    canonical_accounts = transforms.schwab_accounts_to_canonical(accounts_df, today)
    canonical_transactions = transforms.schwab_transactions_to_canonical(transactions_df)

    # 4. Write canonical layers (Schwab-only snapshot before ML merge)
    writer.write_canonical(canonical_holdings, "holdings", today, snapshot=True)
    writer.write_canonical(canonical_accounts, "accounts")

    # Append transactions to the unified history
    _append_transactions(canonical_transactions)

    # 5. Merge latest ML Benefits import (if available)
    canonical_holdings = _merge_ml_benefits(canonical_holdings, today)

    # 6. Load allocation overrides (Google Sheet) — after ML merge so all symbols present
    overrides_df = _load_allocation_overrides(canonical_holdings)

    # 7. Merge overrides into holdings
    if not overrides_df.empty:
        canonical_holdings = transforms.apply_allocation_overrides(
            canonical_holdings, overrides_df
        )

    # 7b. Derive account tax treatment (Dimension 11)
    canonical_holdings = transforms.apply_tax_treatment(canonical_holdings)

    # 8. Compute metrics from final merged holdings
    _compute_metrics(canonical_holdings)

    summary["status"] = "success"
    log.info(
        "=== Refresh complete: %d positions across %d accounts | %d transactions ===",
        summary["positions"], summary["accounts"], summary["transactions"],
    )
    return summary


# ---------------------------------------------------------------------------
# Allocation overrides loader (uses new allocations module)
# ---------------------------------------------------------------------------

def _load_allocation_overrides(current_holdings) -> "pd.DataFrame":
    """Read allocation overrides from Google Sheet, sync symbols, and classify.

    Uses ``portfolio.sources.allocations.sync_and_classify()`` which:
    - Reads the current Sheet
    - Adds new symbols with LLM-assisted (or rule-based) classification
    - Removes sold symbols
    - Installs dropdown validation
    - Writes the updated data back to the Sheet
    """
    import pandas as pd

    gs_creds = None
    openai_key = None
    try:
        from portfolio.auth import keychain
        gs_creds = keychain.get("google-sheets-creds")
        openai_key = keychain.get("openai-api-key")
    except Exception:
        pass

    if not gs_creds:
        log.debug("Google Sheets not configured – skipping allocation overrides")
        return pd.DataFrame()

    try:
        from portfolio.sources import allocations

        overrides_df = allocations.sync_and_classify(
            holdings_df=current_holdings,
            gs_creds_path=gs_creds,
            openai_api_key=openai_key,
            setup_dropdowns_flag=True,
        )

        writer.write_canonical(overrides_df, "allocations")
        log.info("Allocation overrides: %d symbols synced", len(overrides_df))
        return overrides_df

    except Exception:
        log.exception("Failed to load allocation overrides from Google Sheets")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Transaction history append
# ---------------------------------------------------------------------------

def _append_transactions(new_txns) -> None:
    """Append new transactions to the unified history Parquet."""
    if new_txns.empty:
        return
    path = config.CANONICAL_DIR / "transactions" / "all.parquet"
    try:
        writer.append_parquet(new_txns, path)
        log.debug("Appended %d transactions", len(new_txns))
    except Exception:
        log.exception("Failed to append transactions")


# ---------------------------------------------------------------------------
# ML Benefits merge
# ---------------------------------------------------------------------------

def _merge_ml_benefits(schwab_holdings: "pd.DataFrame", as_of: date) -> "pd.DataFrame":
    """Merge the latest ML Benefits raw Parquet into the canonical holdings.

    Looks for the most recent Parquet file under raw/ml_benefits/retirement/.
    If found, converts it to canonical form and merges with Schwab holdings,
    then rewrites canonical/holdings/current.parquet.

    Returns the merged DataFrame (or the original if no ML data found).
    """
    import pandas as pd
    from portfolio.sources import ml_benefits as _ml

    retirement_dir = config.RAW_DIR / "ml_benefits" / "retirement"
    if not retirement_dir.exists():
        return schwab_holdings

    parquet_files = sorted(retirement_dir.glob("*.parquet"))
    if not parquet_files:
        return schwab_holdings

    latest = parquet_files[-1]  # sorted alphabetically = date order
    try:
        import pyarrow.parquet as pq
        ml_raw = pq.read_table(latest).to_pandas()

        # If the raw Parquet already has canonical columns (written by import cmd),
        # use it directly; otherwise transform from parsed CSV columns.
        if "account_id" in ml_raw.columns:
            canonical_ml = transforms.ml_benefits_to_canonical(ml_raw)
        else:
            canonical_ml = _ml.to_canonical(ml_raw)

        # Drop any existing BofA 401k rows from Schwab holdings then concat
        merged = schwab_holdings[schwab_holdings["account_id"] != _ml.ACCOUNT_ID].copy()
        merged = pd.concat([merged, canonical_ml], ignore_index=True)

        # Rewrite canonical with merged data (snapshot already taken above for Schwab-only)
        writer.write_canonical(merged, "holdings", as_of, snapshot=False)
        log.info(
            "Merged %d ML Benefits positions from %s", len(canonical_ml), latest.name
        )
        return merged

    except Exception:
        log.exception("Failed to merge ML Benefits data from %s", latest)
        return schwab_holdings


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def _compute_metrics(holdings: "pd.DataFrame") -> None:
    """Run all metrics modules against the current canonical holdings."""
    if holdings.empty:
        log.debug("No holdings data — skipping metrics computation")
        return

    try:
        from portfolio.metrics import allocation, performance, income, risk
        reader = _reader.DataReader()
        log.info("Computing metrics...")
        allocation.compute_all(holdings)
        performance.compute_all(holdings, reader=reader)
        income.compute_all(holdings)
        risk.compute_all(holdings, reader=reader)
        log.info("Metrics computation complete")
    except Exception:
        log.exception("Metrics computation failed (non-fatal)")


# ---------------------------------------------------------------------------
# macOS notification helper
# ---------------------------------------------------------------------------

def _notify(title: str, message: str) -> None:
    """Send a macOS desktop notification."""
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    except Exception:
        pass  # Non-critical – notification failure should not break the pipeline
