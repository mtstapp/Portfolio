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
    """Import a Merrill Lynch Benefits CSV/Excel file."""
    if not args:
        print("Usage: portfolio import ml-benefits <file.csv|file.xlsx>")
        sys.exit(1)

    file_path = args[0]
    print(f"ML Benefits import not yet implemented (Phase 2).")
    print(f"File: {file_path}")
    print("For now, place the file in ~/data/portfolio/imports/ml_benefits/")


def _print_help() -> None:
    print(__doc__)


if __name__ == "__main__":
    main()
