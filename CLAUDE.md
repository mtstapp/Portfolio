# Portfolio Dashboard - Development Guide

## Project Overview

Python application that aggregates investment data from Charles Schwab (6+ accounts) and Merrill Lynch Benefits (401k + RSU/ESPP), computes portfolio metrics, and displays an interactive Streamlit dashboard. Served from Mac Mini on local network.

See `PRD.md` for full product requirements.

## Tech Stack

- **Python 3.11** (pyenv)
- **schwabdev** - Schwab API client (OAuth 2.0)
- **keyring** - macOS Keychain for all secrets
- **pandas** + **pyarrow** - Data manipulation and Parquet I/O
- **duckdb** - In-process SQL queries on Parquet files
- **streamlit** + **plotly** - Dashboard and interactive charts
- **yfinance** - Market data enrichment (sector, industry, benchmarks)
- **pygsheets** - Google Sheets for manual allocation overrides
- **flask** - Web-based OAuth flow

## Project Structure

```
src/portfolio/
  __init__.py
  config.py                 # Paths, constants, account mappings
  cli.py                    # CLI entry points (setup, auth, refresh, import)
  auth/
    __init__.py
    keychain.py             # keyring get/set wrappers (service: portfolio-dashboard)
    schwab_oauth.py         # Flask-based web OAuth flow
    setup_secrets.py        # One-time CLI to store credentials in Keychain
  sources/
    __init__.py
    base.py                 # Abstract base for data sources
    schwab_client.py        # Schwab API: accounts, positions, fundamentals
    ml_benefits.py          # CSV/Excel parser for ML Benefits exports
    market_data.py          # yfinance: sector/industry, benchmarks, risk-free rate
    allocations.py          # Google Sheet reader/writer for manual overrides
    plaid_client.py         # Phase 2 stub
  storage/
    __init__.py
    schema.py               # Canonical column definitions and types
    writer.py               # Write DataFrames to dated Parquet files
    reader.py               # Read Parquet, DuckDB query interface
  pipeline/
    __init__.py
    daily_refresh.py        # Main ETL orchestration
    transforms.py           # Normalize, enrich, classify securities
  metrics/
    __init__.py
    allocation.py           # Multi-dimensional allocation with look-through
    performance.py          # Returns: total, annualized, TWR, benchmark
    income.py               # Dividend/interest aggregation, projections
    risk.py                 # Volatility, Sharpe, drawdown, beta, correlation
  dashboard/
    __init__.py
    app.py                  # Streamlit entry point (multipage)
    components/
      __init__.py
      charts.py             # Plotly chart builders
      metrics_cards.py      # KPI summary cards
      filters.py            # Account/date/asset class filter widgets
    pages/
      1_Overview.py
      2_Holdings.py
      3_Allocation.py
      4_Performance.py
      5_Income.py
      6_Risk.py
      7_Accounts.py
tests/
  conftest.py
  test_sources/
  test_metrics/
  test_pipeline/
  test_storage/
deploy/
  com.portfolio.refresh.plist    # launchd: daily refresh at 4:30 PM ET
  com.portfolio.dashboard.plist  # launchd: Streamlit server (RunAtLoad)
  install.sh                     # Mac Mini deployment script
```

## Key Conventions

### Secrets
- **All secrets in macOS Keychain** via `keyring` library
- Service name: `portfolio-dashboard`
- Keys: `schwab-api-key`, `schwab-app-secret`, `schwab-callback-url`, `schwab-oauth-token`, `schwab-token-created-at`, `perplexity-api-key`, `google-sheets-service-account`
- **Never** store secrets in `.env`, config files, or code
- Access pattern: `keyring.get_password("portfolio-dashboard", "schwab-api-key")`

### Data
- All data at `~/data/portfolio/` (not in repo)
- Parquet format for everything (portable, AI-queryable)
- DuckDB for in-process SQL queries on Parquet
- Date-stamped files: `raw/schwab/positions/2026-03-09.parquet`
- Canonical layer unifies all sources into standard schema

### Schwab API Patterns (from existing cspull)
- Library: `schwabdev.Client(api_key, app_secret, callback_url)`
- Symbol normalization: `.` → `-` for yfinance, `.` → `/` for Schwab instruments
- Exclude OPTION positions
- Map COLLECTIVE_INVESTMENT → ETF
- Track cash as position with symbol `cashBalance`
- Rate limiting: 2-second sleep between yfinance calls, sequential Schwab API calls

### Google Sheets (Allocations)
- Uses `pygsheets` with service account JSON
- Service account file path stored in Keychain
- Sheet: "Portfolio" workbook, "Allocations" worksheet
- Auto-sync: code adds new symbols, removes sold ones, preserves manual data
- Look-through: percentage columns must sum to 100%

## Commands

```bash
# One-time setup - store credentials in Keychain
portfolio setup

# Schwab OAuth - opens browser for authentication
portfolio auth

# Manual data refresh
portfolio refresh

# Import ML Benefits CSV/Excel
portfolio import ml-benefits path/to/file.csv

# Start dashboard
streamlit run src/portfolio/dashboard/app.py

# Run tests
pytest tests/
```

## Data Flow

```
Schwab API ──────────┐
ML Benefits CSV ─────┤──→ raw/ (Parquet) ──→ canonical/ ──→ metrics/ ──→ Streamlit
yfinance ────────────┤
Google Sheet alloc ──┘
```

1. **Extract**: Pull from each source, write timestamped Parquet to `raw/`
2. **Transform**: Normalize to canonical schema, enrich with classifications
3. **Compute**: Generate metrics from canonical data, write to `metrics/`
4. **Display**: Streamlit reads canonical + metrics Parquet via DuckDB

## Testing

- Unit tests for all metrics computations (allocation, performance, income, risk)
- Mock Schwab API responses for source tests
- Sample Parquet fixtures in `tests/fixtures/`
- Run: `pytest tests/ -v`

## Deployment (Mac Mini)

- Copy repo to Mac Mini
- Run `portfolio setup` to store credentials in Keychain
- Run `portfolio auth` to authenticate with Schwab
- Run `deploy/install.sh` to install launchd agents
- Dashboard at `http://<mac-mini>.local:8501`
