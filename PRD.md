# Portfolio Dashboard - Product Requirements Document

## 1. Product Overview

Personal investment portfolio aggregation and analytics dashboard. Consolidates holdings from 6+ Charles Schwab accounts and Merrill Lynch Benefits accounts (401k + RSU/ESPP) into a single Streamlit dashboard with rich metrics, interactive charts, and automated daily data refresh.

**Deployment**: Mac Mini on local network
**Development**: MacBook laptop
**Language**: Python 3.11

## 2. Data Sources

### 2.1 Charles Schwab API (Primary)

**Library**: `schwabdev` (existing, proven in `/Users/mark/dev/cspull/`)
**Auth**: OAuth 2.0 via developer.schwab.com
**Accounts**: 6+ accounts (brokerage, IRA, SEP, joint, trust, etc.)

Known accounts from existing code:
- Account 0510: Mark Roth
- Account 0986: Mark SEP
- Account 8523: Leigh SEP
- Account 1817: Leigh IRA
- Additional accounts to be discovered via API

**Data pulled**:
- Account balances and liquidation values
- Positions: symbol, quantity, average price, market value, asset type
- Security descriptions via `client.quote()`
- Fundamental data via `client.instruments()`: beta, dividend amount/yield, EPS, P/E, P/B, margins, market cap, ROA, ROE
- Transaction history (for income tracking)

**Existing patterns to preserve** (from `cspull/main.py`):
- Symbol normalization: `.` → `-` for yfinance, `.` → `/` for Schwab instruments API
- OPTION positions excluded from processing
- COLLECTIVE_INVESTMENT asset type mapped to ETF
- Cash balance tracked as a synthetic position (symbol: `cashBalance`)
- 2-second sleep between yfinance requests to avoid rate limiting

### 2.2 Merrill Lynch Benefits (benefits.ml.com)

**Phase 1**: Manual CSV/Excel export ingestion
- User downloads holdings export from benefits.ml.com
- Places file in `~/data/portfolio/imports/ml_benefits/`
- CLI command or file watcher triggers parsing
- Flexible column mapping with header-based auto-detection
- Supports both retirement (401k) and stock plan (RSU/ESPP) formats

**Phase 2**: Plaid integration for automated access
- `plaid-python` library
- Plaid Link flow for account connection
- Access token stored in macOS Keychain

### 2.3 Market Data (yfinance)

Already used in existing codebase:
- Sector and industry classification for equities
- Category and asset type for ETFs/mutual funds
- S&P 500 daily prices for benchmark comparison
- Treasury bill yields for risk-free rate (Sharpe ratio calculation)

### 2.4 Google Sheet "Allocations" (Manual Overrides)

**Library**: `pygsheets` with service account (existing pattern from cspull)
**Purpose**: Manual classification and look-through allocation data

**Sheet structure**:
- **Column A**: Symbol (auto-synced as positions change - new symbols added, sold positions removed)
- **Column B**: Description (auto-populated from Schwab data)
- **Asset Class**: Dropdown - Domestic Stock, Intl Stock, EM Stock, Domestic Bond, Intl Bond, Cash, Alternative
- **Risk Score**: 1-10 numeric score assigned by user
- **Look-through columns**: `Pct Domestic Stock`, `Pct Intl Stock`, `Pct EM Stock`, `Pct Domestic Bond`, `Pct Intl Bond`, `Pct Cash`, `Pct Alternative` (must sum to 100%)
- **Manual Price**: For unrecognized investments without market data

**Auto-sync behavior**:
- Pipeline reads current holdings, compares to sheet symbols
- New holdings get a new row (symbol + description populated, allocation columns blank)
- Sold holdings are removed (or marked inactive)
- Existing manual data preserved when symbols persist

## 3. Metrics

### 3.1 Asset Allocation (Multi-Dimensional)

**Automatic dimensions** (derived from API + yfinance):
- Security type: ETF vs Stock vs Mutual Fund vs Bond vs Cash
- Sector (equities): Technology, Healthcare, Financials, Energy, etc.

**Manual dimensions** (from Google Sheet "Allocations"):
- Asset class: Domestic Stock, Intl Stock, EM Stock, Domestic Bond, Intl Bond, Cash, Alternative
- Risk score: 1-10
- Look-through allocation: For multi-asset funds (e.g., target-date fund = 60% domestic stock / 20% intl stock / 10% bonds / 10% cash), user specifies percentage breakdown. Dashboard computes blended portfolio allocation by distributing each fund's market value across its component asset classes.

**For unrecognized investments**: Full manual breakdown via Google Sheet - asset class, geography, sub-type, risk score, and manual price.

**Dashboard views**:
- Pie/donut chart: By asset class (using look-through for blended funds)
- Pie/donut chart: By geography (domestic / international / emerging)
- Bar chart: By risk score distribution (weighted by market value)
- Treemap: By security type → sector
- Table: All holdings with their allocation classifications

### 3.2 Performance / Returns

- Total return (adjusted for cash flows)
- Annualized return
- Time-weighted return (TWR)
- Benchmark comparison: portfolio vs S&P 500
- Cumulative return chart with period selectors (1M, 3M, 6M, YTD, 1Y, ALL)
- Monthly returns heatmap
- Per-account performance comparison

### 3.3 Income Tracking

- Dividend, interest, and distribution income aggregated by month/quarter/year
- Income by security table
- YTD income vs prior year comparison
- Projected annual income based on current holdings and trailing 12-month dividend rates
- Yield on cost (YOC) per holding (existing calculation from cspull)
- Total portfolio dividend amount

### 3.4 Risk Metrics

- Annualized volatility (standard deviation of daily returns)
- Sharpe ratio (using Treasury bill rate as risk-free rate)
- Maximum drawdown
- Portfolio beta (vs S&P 500) - currently calculated as weighted beta in cspull
- Correlation matrix across top holdings
- Rolling risk metrics (30/90/365-day windows)
- Drawdown chart over time
- Risk score distribution (from manual Google Sheet scores)

## 4. Security Requirements

### 4.1 Credential Storage

All secrets stored in **macOS Keychain** via the `keyring` library. No `.env` files, no `tokens.json`, no secrets on disk.

**Keychain entries** (service: `portfolio-dashboard`):
| Key | Value |
|-----|-------|
| `schwab-api-key` | Schwab client ID |
| `schwab-app-secret` | Schwab client secret |
| `schwab-callback-url` | OAuth callback URL |
| `schwab-oauth-token` | JSON-serialized OAuth token |
| `schwab-token-created-at` | ISO timestamp for expiry tracking |
| `perplexity-api-key` | Perplexity API key (for AI updates feature) |
| `google-sheets-service-account` | Path to service account JSON (or the JSON itself) |
| `plaid-client-id` | (Phase 2) Plaid client ID |
| `plaid-secret` | (Phase 2) Plaid secret |
| `plaid-access-token-ml` | (Phase 2) ML Benefits Plaid access token |

### 4.2 Web-Based OAuth Flow

Replace the current CLI-based Schwab OAuth with a browser-friendly flow:

1. Small Flask app serves an auth page at `http://localhost:5050/auth/schwab`
2. User clicks "Authenticate with Schwab" button
3. Browser redirects to Schwab OAuth authorize URL
4. User logs in at Schwab, grants access
5. Schwab redirects back to `https://127.0.0.1:8182` (callback URL)
6. Flask callback handler captures authorization code
7. Exchanges code for access + refresh tokens
8. Stores tokens in macOS Keychain
9. Displays success page

**Trigger points**:
- CLI: `portfolio auth`
- Streamlit sidebar: "Re-authenticate with Schwab" button
- Automatic prompt when token is within 2 days of 7-day expiry

### 4.3 Network Security

- Streamlit binds to `0.0.0.0:8501` for local network access
- No port forwarding to internet
- No authentication layer needed (local network trusted)
- Data directory (`~/data/portfolio/`) contains only financial data, no credentials

## 5. Data Architecture

### 5.1 Storage Format

**Primary**: Apache Parquet files (columnar, compressed, tool-agnostic)
**Query layer**: DuckDB (in-process, reads Parquet directly with SQL)

Parquet chosen because:
- Readable by pandas, polars, R, Spark, DuckDB, and any AI/LLM agent
- Self-describing schema, no migration headaches
- Fast columnar reads for analytical queries
- Natural append-only pattern (one file per day)

### 5.2 Directory Structure

```
~/data/portfolio/
  raw/
    schwab/
      accounts/{date}.parquet       # Account balances snapshot
      positions/{date}.parquet      # All positions across all accounts
      transactions/{date}.parquet   # New transactions since last fetch
    ml_benefits/
      retirement/{date}.parquet     # 401k holdings from CSV import
      stock_plan/{date}.parquet     # RSU/ESPP from CSV import
    market_data/
      benchmarks/spy_daily.parquet  # S&P 500 daily prices (appended)
      risk_free/tbill_rates.parquet # Treasury yields
  canonical/
    holdings/
      current.parquet               # Latest consolidated holdings
      snapshots/{date}.parquet      # Historical daily snapshots
    transactions/
      all.parquet                   # Unified transaction history
    accounts/
      current.parquet               # Account metadata and balances
    allocations/
      overrides.parquet             # Latest Google Sheet allocation data
  metrics/
    allocation/
      by_asset_class.parquet
      by_sector.parquet
      by_geography.parquet
      by_risk_score.parquet
      look_through_blend.parquet    # Blended allocation after look-through
    performance/
      daily_returns.parquet
      cumulative_returns.parquet
      benchmark_comparison.parquet
    income/
      history.parquet
      projected.parquet
    risk/
      current_metrics.parquet
      rolling_metrics.parquet
  imports/
    ml_benefits/                    # Drop zone for ML Benefits CSV/Excel files
  logs/
    refresh.log
    refresh_error.log
    dashboard.log
```

### 5.3 Canonical Holdings Schema

```
date:                date        # Snapshot date
account_id:          string      # Account number (last 4 digits)
account_name:        string      # Human-readable name
source:              string      # schwab | ml_benefits
symbol:              string      # Ticker symbol (normalized)
description:         string      # Security name
security_type:       string      # EQUITY | ETF | MUTUAL_FUND | BOND | cash
quantity:            float64     # Number of shares/units
average_price:       float64     # Average cost per share
market_value:        float64     # Current total market value
cost_basis:          float64     # Total cost basis
current_price:       float64     # Current price per share
gain_loss:           float64     # Unrealized gain/loss
sector:              string      # From yfinance (equities)
industry:            string      # From yfinance (equities)
asset_class:         string      # From Google Sheet overrides
risk_score:          int         # From Google Sheet (1-10)
beta:                float64     # From Schwab fundamentals
dividend_amount:     float64     # Annual dividend per share
dividend_yield:      float64     # Current dividend yield
pe_ratio:            float64     # Price/earnings ratio
market_cap:          float64     # Market capitalization
```

## 6. Dashboard (Streamlit)

### 6.1 Pages

**Page 1: Overview**
- KPI cards: Total Portfolio Value, Day Change ($, %), YTD Return, Projected Annual Income, Portfolio Beta
- Asset allocation donut chart (look-through blended)
- Portfolio value over time line chart (1M/3M/6M/1Y/ALL toggles)
- Top 10 holdings table
- Account breakdown bar chart

**Page 2: Holdings**
- Full holdings table with sort, filter, search
- Columns: Symbol, Name, Account, Shares, Price, Value, Cost Basis, Gain/Loss, % of Portfolio, Risk Score
- Filter sidebar: by account, asset class, sector, risk score
- Treemap visualization by market value

**Page 3: Asset Allocation**
- Pie/donut: By asset class (with look-through blending)
- Pie/donut: By geography (domestic / international / emerging)
- Bar: Risk score distribution (value-weighted)
- Treemap: Security type → sector
- Table: All holdings with allocation classifications
- Comparison: Current allocation vs target (if targets defined)

**Page 4: Performance**
- Portfolio vs S&P 500 cumulative return chart
- Period selector: 1M, 3M, 6M, YTD, 1Y, ALL
- Returns summary table: Total, annualized, TWR
- Monthly returns heatmap
- Per-account performance comparison

**Page 5: Income**
- Monthly income bar chart (stacked by type: dividends/interest/distributions)
- YTD income vs prior year
- Income by security table
- Projected annual income summary
- YOC by holding

**Page 6: Risk**
- Risk metrics cards: Volatility, Sharpe, Max Drawdown, Beta
- Rolling risk metrics chart (30/90/365-day windows)
- Correlation matrix heatmap (top holdings)
- Drawdown chart over time
- Risk score distribution (from manual scores)

**Page 7: Accounts**
- Account selector dropdown
- Per-account: value, allocation, holdings, performance
- Account type grouping (taxable vs tax-advantaged)

### 6.2 Streamlit Configuration

```toml
[server]
address = "0.0.0.0"
port = 8501
headless = true

[browser]
gatherUsageStats = false
```

### 6.3 Sidebar

- Last refresh timestamp
- Schwab token health indicator (days until expiry)
- "Refresh Data" button (manual trigger)
- "Re-authenticate with Schwab" button
- Account filter (multi-select)

## 7. Automation

### 7.1 Daily Refresh

**Schedule**: 4:30 PM ET weekdays via macOS `launchd`
**Behavior**:
1. Check if trading day (skip weekends + US market holidays)
2. Fetch Schwab positions and account balances
3. Fetch Schwab transactions (new since last fetch)
4. Fetch market data (S&P 500 close, Treasury yields)
5. Read Google Sheet "Allocations" for manual overrides
6. Write raw data to Parquet
7. Transform to canonical schema
8. Compute all metrics
9. Log results

**Token expiry management**:
- Check token age on each refresh
- At day 5 of 7: macOS notification prompting re-authentication
- Dashboard shows token health in sidebar

### 7.2 launchd Agents

Two plist files in `~/Library/LaunchAgents/`:
- `com.portfolio.refresh.plist` - Daily data refresh at 4:30 PM ET
- `com.portfolio.dashboard.plist` - Streamlit server (RunAtLoad + KeepAlive)

## 8. Phased Implementation

### Phase 1: Foundation
- Project scaffolding (pyproject.toml, src layout, git)
- Keychain integration (`keyring` wrappers, setup CLI)
- Schwab client migration from cspull (refactored into modules)
- Web-based OAuth flow (Flask)
- Raw Parquet storage for Schwab data
- Minimal Streamlit page showing positions

### Phase 2: Core Pipeline + Allocation
- ETL pipeline orchestration
- Canonical data layer with unified schema
- Google Sheet "Allocations" integration:
  - Auto-sync symbol list
  - Read manual asset class, risk score, look-through percentages
- Security classification (merge API + yfinance + manual overrides)
- Multi-dimensional allocation metrics with look-through blending
- Allocation dashboard page with all chart types
- ML Benefits CSV import CLI

### Phase 3: Performance + Income
- S&P 500 benchmark data pipeline
- Return calculations: total, annualized, TWR
- Portfolio vs benchmark comparison
- Income aggregation from Schwab transactions
- Projected annual income
- Performance + Income dashboard pages

### Phase 4: Risk + Automation
- Risk metrics: volatility, Sharpe, max drawdown, beta, correlation
- Rolling risk windows
- Daily launchd schedule
- Mac Mini deployment (install.sh)
- Token expiry notifications

### Phase 5: Polish + Plaid
- Historical transaction backfill
- Reconstruct historical snapshots
- Plaid integration for ML Benefits
- Dashboard refinements (theming, loading states, responsiveness)
- Unit and integration tests

## 9. Existing Code Reference

Source code to migrate from `/Users/mark/dev/cspull/`:

| File | Key Functions | Destination |
|------|--------------|-------------|
| `main.py` | `setup_schwab_accounts()` | `src/portfolio/sources/schwab_client.py` |
| `main.py` | `create_schwab_dataframe()` | `src/portfolio/sources/schwab_client.py` |
| `main.py` | `update_schwab_totals()` | `src/portfolio/pipeline/transforms.py` |
| `main.py` | `update_sector_and_industry()` | `src/portfolio/sources/market_data.py` |
| `main.py` | `update_with_fundamental_data()` | `src/portfolio/sources/schwab_client.py` |
| `main.py` | `sync_portfolio_with_schwab()` | `src/portfolio/pipeline/transforms.py` |
| `main.py` | Google Sheets setup | `src/portfolio/sources/allocations.py` |
| `updates.py` | Perplexity AI summaries | `src/portfolio/sources/ai_updates.py` (future) |
| `SectorLookup.py` | yfinance sector lookup | `src/portfolio/sources/market_data.py` |

## 10. Dependencies

```
schwabdev>=1.0
pandas>=2.0
pyarrow>=14.0
duckdb>=0.9
streamlit>=1.30
plotly>=5.18
keyring>=25.0
yfinance>=0.2
pygsheets>=2.0
flask>=3.0
httpx>=0.25
numpy>=1.26
python-dotenv>=1.0  # only for migration period, remove after Keychain cutover
```

Optional (Phase 2+):
```
plaid-python>=20.0
```

Dev:
```
pytest>=7.0
ruff
```
