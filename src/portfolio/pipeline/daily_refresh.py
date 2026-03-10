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

    # 4. Load allocation overrides (Google Sheet)
    overrides_df = _load_allocation_overrides(canonical_holdings)

    # 5. Merge overrides into holdings
    if not overrides_df.empty:
        canonical_holdings = transforms.apply_allocation_overrides(
            canonical_holdings, overrides_df
        )

    # 6. Write canonical layers
    writer.write_canonical(canonical_holdings, "holdings", today, snapshot=True)
    writer.write_canonical(canonical_accounts, "accounts")

    # Append transactions to the unified history
    _append_transactions(canonical_transactions)

    summary["status"] = "success"
    log.info(
        "=== Refresh complete: %d positions across %d accounts | %d transactions ===",
        summary["positions"], summary["accounts"], summary["transactions"],
    )
    return summary


# ---------------------------------------------------------------------------
# Allocation overrides loader
# ---------------------------------------------------------------------------

def _load_allocation_overrides(current_holdings) -> "pd.DataFrame":
    """Read allocation overrides from Google Sheet and sync symbols."""
    import pandas as pd

    gs_creds = None
    try:
        from portfolio.auth import keychain
        gs_creds = keychain.get("google-sheets-creds")
    except Exception:
        pass

    if not gs_creds:
        log.debug("Google Sheets not configured – skipping allocation overrides")
        return pd.DataFrame()

    try:
        import pygsheets
        gc = pygsheets.authorize(service_file=gs_creds)
        wb = gc.open("Portfolio")
        ws = wb.worksheet_by_title("Allocations")
        overrides_df = ws.get_as_df()

        # Sync symbols (add new, remove sold)
        synced = transforms.sync_allocation_symbols(current_holdings, overrides_df)
        if not synced.equals(overrides_df):
            ws.set_dataframe(synced, (1, 1), fit=True)
            log.info("Synced allocation sheet: %d symbols", len(synced))

        writer.write_canonical(synced, "allocations")
        return synced

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
# macOS notification helper
# ---------------------------------------------------------------------------

def _notify(title: str, message: str) -> None:
    """Send a macOS desktop notification."""
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    except Exception:
        pass  # Non-critical – notification failure should not break the pipeline
