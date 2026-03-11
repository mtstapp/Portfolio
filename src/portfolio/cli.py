"""Portfolio Dashboard CLI.

Installed as 'portfolio' via pyproject.toml [project.scripts].

Commands:
    portfolio setup             Store API credentials in macOS Keychain
    portfolio auth              Authenticate with Schwab via browser
    portfolio auth --no-browser Start auth server without opening browser
    portfolio refresh           Pull latest data from all sources
    portfolio refresh --force   Refresh even on weekends/holidays
    portfolio refresh --fast    Skip slow yfinance sector enrichment
    portfolio status            Show auth and data status
    portfolio import ml-benefits <file>   Import ML Benefits CSV/Excel
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        _print_help()
        return

    cmd = args[0]

    if cmd == "setup":
        _cmd_setup(args[1:])
    elif cmd == "auth":
        _cmd_auth(args[1:])
    elif cmd == "refresh":
        _cmd_refresh(args[1:])
    elif cmd == "status":
        _cmd_status()
    elif cmd == "import" and len(args) >= 2 and args[1] == "ml-benefits":
        _cmd_import_ml(args[2:])
    else:
        print(f"Unknown command: {cmd}\nRun 'portfolio --help' for usage.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def _cmd_setup(args: list[str]) -> None:
    """Store credentials in macOS Keychain."""
    from portfolio.auth.setup_secrets import run_setup

    migrate_env = None
    for i, arg in enumerate(args):
        if arg == "--migrate-env" and i + 1 < len(args):
            migrate_env = args[i + 1]

    run_setup(migrate_env=migrate_env)


def _cmd_auth(args: list[str]) -> None:
    """Run the Schwab OAuth web flow."""
    from portfolio.auth import keychain, schwab_oauth
    from portfolio import config

    if not keychain.is_configured():
        print("Schwab credentials not found in Keychain.")
        print("Run: portfolio setup")
        sys.exit(1)

    open_browser = "--no-browser" not in args

    print("\nStarting Schwab authentication server…")
    print(f"Auth page: https://{config.OAUTH_SERVER_HOST}:{config.OAUTH_SERVER_PORT}")
    if open_browser:
        print("Opening browser…")
    else:
        print(f"Open your browser to: "
              f"https://{config.OAUTH_SERVER_HOST}:{config.OAUTH_SERVER_PORT}")
        print("(Accept the self-signed certificate warning)")

    schwab_oauth.start_auth_server(open_browser=open_browser)


def _cmd_refresh(args: list[str]) -> None:
    """Pull latest data from Schwab."""
    from portfolio.pipeline.daily_refresh import run

    force = "--force" in args
    skip_sector = "--fast" in args

    summary = run(force=force, skip_sector=skip_sector)

    if summary["status"] == "success":
        print(
            f"\n✓ Refresh complete – {summary['positions']} positions across "
            f"{summary['accounts']} accounts"
        )
    elif summary["status"] == "skipped":
        print("Skipped – not a trading day. Use --force to override.")
    else:
        print(f"\n✗ Refresh failed: {', '.join(summary['errors'])}")
        sys.exit(1)


def _cmd_status() -> None:
    """Show authentication and data status."""
    from portfolio.auth import keychain, schwab_oauth
    from portfolio.storage.reader import DataReader

    print("\n=== Portfolio Dashboard Status ===\n")

    # Credentials
    has_creds = keychain.is_configured()
    print(f"Credentials:  {'✓ Configured' if has_creds else '✗ Not set (run: portfolio setup)'}")

    # Auth
    days = schwab_oauth.token_days_remaining()
    if days is None:
        print("Auth:         ✗ Not authenticated (run: portfolio auth)")
    elif days < 1:
        print(f"Auth:         ✗ Token EXPIRED (run: portfolio auth)")
    elif days < 2:
        print(f"Auth:         ⚠ Token expires in {days:.1f} days (run: portfolio auth)")
    else:
        print(f"Auth:         ✓ Token valid ({days:.1f} days remaining)")

    # Data
    reader = DataReader()
    last = reader.last_refresh_date()
    if last:
        print(f"Last refresh: {last}")
        holdings = reader.current_holdings()
        if not holdings.empty:
            total = holdings["market_value"].sum()
            print(f"Holdings:     {len(holdings)} positions, total ${total:,.0f}")
    else:
        print("Data:         No data yet (run: portfolio refresh)")

    print()


def _cmd_import_ml(args: list[str]) -> None:
    """Import a Merrill Lynch Benefits 401k CSV file."""
    if not args:
        print("Usage: portfolio import ml-benefits <file.csv> [--date YYYY-MM-DD]")
        sys.exit(1)

    from datetime import date, datetime
    import pandas as pd
    from portfolio import config
    from portfolio.sources import ml_benefits
    from portfolio.storage import reader as _reader, writer
    from portfolio.pipeline import transforms

    file_path = args[0]

    # Optional --date override
    as_of = None
    if "--date" in args:
        idx = args.index("--date")
        if idx + 1 < len(args):
            try:
                as_of = datetime.strptime(args[idx + 1], "%Y-%m-%d").date()
            except ValueError:
                print(f"Invalid date format: {args[idx + 1]}. Use YYYY-MM-DD.")
                sys.exit(1)

    effective_date = as_of or date.today()

    print(f"Importing ML Benefits 401k from: {file_path}")
    try:
        # 1. Parse CSV
        raw_df = ml_benefits.parse_csv(file_path, as_of=effective_date)

        # 2. Convert to canonical holdings
        canonical_ml = ml_benefits.to_canonical(raw_df)

        # 3. Write raw Parquet
        config.ensure_dirs()
        writer.write_raw(raw_df, "ml_benefits", "retirement", effective_date)

        # 4. Merge into canonical holdings:
        #    - Load existing canonical holdings (Schwab + any prior ML import)
        #    - Drop any existing BofA 401k rows
        #    - Append new ML rows
        #    - Write merged result back
        reader = _reader.DataReader()
        if reader.has_data():
            existing = reader.current_holdings()
            existing = existing[existing["account_id"] != ml_benefits.ACCOUNT_ID]
            merged = pd.concat([existing, canonical_ml], ignore_index=True)
        else:
            merged = canonical_ml

        writer.write_canonical(merged, "holdings", effective_date, snapshot=True)

        # 5. Update accounts Parquet with BofA 401k balance
        total_value = raw_df["market_value"].sum()
        acct_row = pd.DataFrame([
            ml_benefits.canonical_account_row(effective_date, total_value)
        ])
        if reader.has_data():
            existing_accts = reader.current_accounts()
            existing_accts = existing_accts[
                existing_accts["account_id"] != ml_benefits.ACCOUNT_ID
            ]
            merged_accts = pd.concat([existing_accts, acct_row], ignore_index=True)
        else:
            merged_accts = acct_row
        writer.write_canonical(merged_accts, "accounts")

        n = len(canonical_ml)
        print(
            f"\n✓ Imported {n} positions for {ml_benefits.ACCOUNT_NAME} "
            f"(total: ${total_value:,.0f})"
        )
        print(f"  Date: {effective_date}  |  Raw saved to: raw/ml_benefits/retirement/")
        print("  Canonical holdings updated. Reload the dashboard to see changes.")

    except FileNotFoundError as exc:
        print(f"\n✗ File not found: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n✗ Import failed: {exc}")
        raise


def _print_help() -> None:
    print(__doc__)


if __name__ == "__main__":
    main()
