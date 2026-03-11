"""Application configuration: paths, constants, and account mappings."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Directory paths
# ---------------------------------------------------------------------------
DATA_DIR = Path.home() / "data" / "portfolio"
SECRETS_DIR = Path.home() / ".portfolio"

RAW_DIR = DATA_DIR / "raw"
CANONICAL_DIR = DATA_DIR / "canonical"
METRICS_DIR = DATA_DIR / "metrics"
IMPORTS_DIR = DATA_DIR / "imports"
ML_BENEFITS_IMPORT_DIR = IMPORTS_DIR / "ml_benefits"
LOGS_DIR = DATA_DIR / "logs"

# Schwab OAuth token DB (outside repo, chmod 600)
# schwabdev stores tokens in a SQLite database
TOKENS_FILE = SECRETS_DIR / ".schwab_tokens.db"

# ---------------------------------------------------------------------------
# Schwab OAuth endpoints
# ---------------------------------------------------------------------------
SCHWAB_AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
SCHWAB_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
SCHWAB_DEFAULT_CALLBACK = "https://127.0.0.1:8182"

# OAuth callback server settings
OAUTH_SERVER_HOST = "127.0.0.1"
OAUTH_SERVER_PORT = 8182

# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------
BENCHMARK_SYMBOL = "$SPX"      # S&P 500 index

# ---------------------------------------------------------------------------
# Security type mapping (from Schwab assetType to canonical type)
# ---------------------------------------------------------------------------
ASSET_TYPE_MAP = {
    "EQUITY": "EQUITY",
    "ETF": "ETF",
    "COLLECTIVE_INVESTMENT": "ETF",     # Schwab's name for ETFs
    "MUTUAL_FUND": "MUTUAL_FUND",
    "FIXED_INCOME": "BOND",
    "BOND": "BOND",
    "CASH_EQUIVALENT": "CASH",
    "OPTION": "OPTION",                 # Excluded from processing
}

# ---------------------------------------------------------------------------
# Refresh schedule
# ---------------------------------------------------------------------------
# US market holidays (add as needed; format YYYY-MM-DD)
MARKET_HOLIDAYS_2026 = {
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # MLK Day
    "2026-02-16",  # Presidents Day
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-07-03",  # Independence Day (observed)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-11-27",  # Black Friday (early close - treat as holiday)
    "2026-12-25",  # Christmas
}


def ensure_dirs() -> None:
    """Create all required data directories."""
    for d in [RAW_DIR / "schwab" / "accounts",
              RAW_DIR / "schwab" / "positions",
              RAW_DIR / "schwab" / "transactions",
              RAW_DIR / "ml_benefits" / "retirement",
              RAW_DIR / "ml_benefits" / "stock_plan",
              RAW_DIR / "market_data" / "benchmarks",
              RAW_DIR / "market_data" / "risk_free",
              CANONICAL_DIR / "holdings" / "snapshots",
              CANONICAL_DIR / "transactions",
              CANONICAL_DIR / "accounts",
              CANONICAL_DIR / "allocations",
              METRICS_DIR / "allocation",
              METRICS_DIR / "performance",
              METRICS_DIR / "income",
              METRICS_DIR / "risk",
              IMPORTS_DIR / "ml_benefits",
              LOGS_DIR,
              SECRETS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    SECRETS_DIR.chmod(0o700)
