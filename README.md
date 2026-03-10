# Portfolio Dashboard

Personal investment portfolio aggregation and analytics dashboard. Consolidates holdings from Charles Schwab (6+ accounts) and Merrill Lynch Benefits (401k + RSU/ESPP) into a single Streamlit dashboard with rich metrics, interactive charts, and automated daily data refresh.

**Status:** Phase 1 (foundation) ✅ | Phase 2-5 (features) 🚧

## Features (Phase 1)

✅ **Schwab API integration** – Dynamically discovers all linked accounts, fetches positions, balances, fundamentals (P/E, beta, dividends)

✅ **Secure credential storage** – All API keys and OAuth tokens in macOS Keychain (never on disk)

✅ **Web-based Schwab OAuth** – Browser-friendly authentication via HTTPS at `https://127.0.0.1:8182`

✅ **Daily automated data pull** – Runs at 4:30 PM ET via launchd (skips weekends/holidays)

✅ **Parquet data lake** – Raw and canonical data at `~/data/portfolio/` for reuse by other tools/AI queries

✅ **DuckDB query interface** – In-process SQL queries on Parquet files

✅ **Streamlit dashboard** – Portfolio overview with KPIs, account breakdown, top holdings, value history

✅ **Always-on service** – Dashboard runs as a macOS service, accessible from any device on your local network

## Upcoming Features (Phases 2-5)

- Asset allocation with manual overrides and look-through blending
- Multi-dimensional allocation views (by asset class, sector, geography, risk score)
- Performance tracking (total return, annualized, time-weighted return, benchmark comparison)
- Income tracking (dividends, distributions, projected annual income)
- Risk metrics (volatility, Sharpe ratio, max drawdown, beta, correlation)
- Merrill Lynch Benefits CSV import (Phase 2), then Plaid integration (Phase 3)
- Historical performance analysis with rolling metrics
- Full test suite

## Quick Start

### On Mac Mini (production)

Follow the **[INSTALL.md](INSTALL.md)** guide. Takes ~10 minutes:

```bash
git clone https://github.com/mtstapp/Portfolio.git
cd Portfolio
bash deploy/install.sh
.venv/bin/portfolio setup
.venv/bin/portfolio auth
.venv/bin/portfolio refresh
```

Then access the dashboard at `http://<mac-mini>.local:8501`

### On development machine (MacBook)

```bash
git clone https://github.com/mtstapp/Portfolio.git
cd Portfolio
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
portfolio setup
portfolio auth
portfolio refresh
streamlit run src/portfolio/dashboard/app.py
```

## Project Layout

```
Portfolio/
├── PRD.md                    # Product requirements document
├── CLAUDE.md                 # Development conventions & tech stack
├── INSTALL.md                # Mac Mini installation guide
├── README.md                 # This file
├── pyproject.toml            # Dependencies & package config
│
├── src/portfolio/            # Main application package
│   ├── config.py             # Paths, constants, account mappings
│   ├── cli.py                # Command-line interface (portfolio setup/auth/refresh)
│   │
│   ├── auth/                 # OAuth & credential storage
│   │   ├── keychain.py       # macOS Keychain wrappers
│   │   ├── schwab_oauth.py   # Flask HTTPS OAuth server
│   │   └── setup_secrets.py  # Interactive credential setup
│   │
│   ├── sources/              # Data source adapters
│   │   └── schwab_client.py  # Schwab API client (migrated from cspull)
│   │
│   ├── storage/              # Data persistence layer
│   │   ├── schema.py         # Canonical column definitions
│   │   ├── writer.py         # Write DataFrames to Parquet
│   │   └── reader.py         # Read Parquet + DuckDB queries
│   │
│   ├── pipeline/             # ETL orchestration
│   │   ├── transforms.py     # Data normalization
│   │   └── daily_refresh.py  # Main refresh pipeline
│   │
│   ├── metrics/              # Computation stubs (Phase 2+)
│   │
│   └── dashboard/            # Streamlit app
│       ├── app.py            # Main dashboard (overview page)
│       ├── pages/            # Additional pages (Phase 2+)
│       └── components/       # Reusable UI components (Phase 2+)
│
├── deploy/                   # Mac Mini deployment
│   ├── install.sh            # Installation script
│   ├── com.portfolio.refresh.plist      # Daily refresh launchd agent
│   └── com.portfolio.dashboard.plist    # Dashboard launchd agent
│
└── tests/                    # Test suite (Phase 4+)
```

## Data Storage

All data at `~/data/portfolio/` (outside the git repo):

```
raw/                # Raw API responses (date-stamped Parquet)
  └─ schwab/positions/, accounts/, transactions/
  └─ ml_benefits/retirement/, stock_plan/

canonical/          # Unified, normalized data
  └─ holdings/current.parquet (latest positions)
  └─ holdings/snapshots/*.parquet (daily snapshots)

metrics/            # Pre-computed metrics (Phase 3+)
  └─ allocation/, performance/, income/, risk/
```

## Commands

```bash
# One-time setup (store credentials in Keychain)
portfolio setup

# Authenticate with Schwab (opens browser)
portfolio auth

# Manual data refresh
portfolio refresh

# Check status
portfolio status

# Start dashboard locally
streamlit run src/portfolio/dashboard/app.py
```

## Architecture Highlights

**Security:**
- All secrets (API keys, OAuth tokens) stored in macOS Keychain
- Tokens stored securely, no `.env` files or plaintext credentials
- 7-day token refresh via Keychain notification at day 5

**Data:**
- Parquet files for portability (readable by pandas, R, Spark, DuckDB, LLMs)
- DuckDB for in-process SQL queries without a database server
- Date-stamped snapshots enable historical analysis

**Automation:**
- macOS `launchd` agents for reliable, native scheduling
- Daily refresh at 4:30 PM ET (after market close)
- Skips weekends and US market holidays automatically

**Reliability:**
- Dashboard runs as a persistent service (`KeepAlive=true`)
- Automatic restart on crash
- Comprehensive logging to `~/data/portfolio/logs/`

## Development

### Tech Stack

- **Python 3.11** (pyenv)
- **schwabdev** – Schwab API wrapper
- **keyring** – macOS Keychain
- **pandas** + **pyarrow** – Data manipulation & Parquet I/O
- **duckdb** – In-process SQL on Parquet
- **streamlit** + **plotly** – Dashboard & charts
- **yfinance** – Market data enrichment
- **flask** – Web-based OAuth server
- **pygsheets** – Google Sheets integration (Phase 2)

### Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### Code Style

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## FAQ

**Q: Do I need a remote database?**
A: No. DuckDB queries Parquet files directly in-process. No server to manage.

**Q: How often is data refreshed?**
A: Daily at 4:30 PM ET (after market close). Manual refresh anytime with `portfolio refresh`.

**Q: How often do I need to re-authenticate with Schwab?**
A: Every 7 days (OAuth refresh token expiry). You'll get a macOS notification at day 5. Just run `portfolio auth` again.

**Q: Can I access the dashboard from outside my home network?**
A: Currently no – it's bound to `0.0.0.0` but only accessible on your local network. Remote access requires additional security setup (VPN, reverse proxy, etc.).

**Q: Can I add ML Benefits data without Plaid?**
A: Yes – Phase 2 includes CSV/Excel import for manual exports from benefits.ml.com. Plaid integration comes in Phase 3.

**Q: How do I export data for use in other tools?**
A: Query via DuckDB or read Parquet files directly. Example:
```python
import duckdb
con = duckdb.connect()
df = con.execute(
    "SELECT * FROM read_parquet('~/data/portfolio/canonical/holdings/current.parquet')"
).fetchdf()
```

## Support & Issues

Check the logs:
- Dashboard: `~/data/portfolio/logs/dashboard*.log`
- Refresh: `~/data/portfolio/logs/refresh*.log`

For feature requests or bugs, open an issue on GitHub.

## License

This project is private and personal-use only.

---

**Created:** March 2026
**Version:** 0.1.0 (Phase 1 Foundation)
