"""Canonical column definitions for all data layers.

These schemas are the contract between data sources, pipeline transforms,
metrics, and the dashboard. Every Parquet file written by this application
must conform to these column names and types.
"""

import pyarrow as pa

# ---------------------------------------------------------------------------
# Holdings (per-account positions, one row per symbol per account)
# ---------------------------------------------------------------------------

HOLDINGS_SCHEMA = pa.schema([
    pa.field("date",             pa.date32()),
    pa.field("account_id",       pa.string()),
    pa.field("account_name",     pa.string()),
    pa.field("source",           pa.string()),        # schwab | ml_benefits
    pa.field("symbol",           pa.string()),
    pa.field("description",      pa.string()),
    pa.field("security_type",    pa.string()),        # EQUITY | ETF | MUTUAL_FUND | BOND | CASH | OPTION
    pa.field("quantity",         pa.float64()),
    pa.field("average_price",    pa.float64()),
    pa.field("current_price",    pa.float64()),
    pa.field("market_value",     pa.float64()),
    pa.field("cost_basis",       pa.float64()),
    pa.field("gain_loss",        pa.float64()),
    pa.field("portfolio_pct",    pa.float64()),
    pa.field("sector",           pa.string()),
    pa.field("industry",         pa.string()),
    pa.field("asset_class",      pa.string()),        # from Google Sheet
    pa.field("risk_score",       pa.float64()),       # 1-10, from Google Sheet
    pa.field("beta",             pa.float64()),
    pa.field("dividend_amount",  pa.float64()),       # annual dividend per share
    pa.field("dividend_yield",   pa.float64()),
    pa.field("eps",              pa.float64()),
    pa.field("pe_ratio",         pa.float64()),
    pa.field("pb_ratio",         pa.float64()),
    pa.field("market_cap",       pa.float64()),
    pa.field("return_on_assets", pa.float64()),
    pa.field("return_on_equity", pa.float64()),
    pa.field("weighted_beta",    pa.float64()),
    pa.field("yoc",              pa.float64()),       # yield on cost %
    pa.field("div_annual_total", pa.float64()),       # dividend_amount * quantity
])

# Column names only (useful for DataFrame construction)
HOLDINGS_COLS = [f.name for f in HOLDINGS_SCHEMA]

# ---------------------------------------------------------------------------
# Accounts (balances per account)
# ---------------------------------------------------------------------------

ACCOUNTS_SCHEMA = pa.schema([
    pa.field("date",              pa.date32()),
    pa.field("account_id",        pa.string()),
    pa.field("account_name",      pa.string()),
    pa.field("account_type",      pa.string()),       # BROKERAGE | IRA | SEP_IRA | etc.
    pa.field("source",            pa.string()),
    pa.field("liquidation_value", pa.float64()),
    pa.field("cash_balance",      pa.float64()),
    pa.field("total_value",       pa.float64()),
])

ACCOUNTS_COLS = [f.name for f in ACCOUNTS_SCHEMA]

# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

TRANSACTIONS_SCHEMA = pa.schema([
    pa.field("date",             pa.timestamp("us")),
    pa.field("account_id",       pa.string()),
    pa.field("account_name",     pa.string()),
    pa.field("source",           pa.string()),
    pa.field("transaction_type", pa.string()),  # buy|sell|dividend|interest|distribution|transfer
    pa.field("symbol",           pa.string()),
    pa.field("quantity",         pa.float64()),
    pa.field("price",            pa.float64()),
    pa.field("amount",           pa.float64()),
    pa.field("fees",             pa.float64()),
])

TRANSACTION_COLS = [f.name for f in TRANSACTIONS_SCHEMA]

# ---------------------------------------------------------------------------
# Allocation overrides (from Google Sheet)
# ---------------------------------------------------------------------------

ALLOCATIONS_SCHEMA = pa.schema([
    pa.field("symbol",               pa.string()),
    pa.field("description",          pa.string()),
    pa.field("asset_class",          pa.string()),
    pa.field("objective",            pa.string()),
    pa.field("region",               pa.string()),
    pa.field("equity_style",         pa.string()),
    pa.field("fi_style",             pa.string()),
    pa.field("fi_sector",            pa.string()),
    pa.field("factor",               pa.string()),
    pa.field("income_type",          pa.string()),
    pa.field("vehicle_type",         pa.string()),
    pa.field("sector",               pa.string()),
    pa.field("industry",             pa.string()),
    pa.field("risk_score",           pa.float64()),
    pa.field("pct_domestic_stock",   pa.float64()),
    pa.field("pct_intl_stock",       pa.float64()),
    pa.field("pct_em_stock",         pa.float64()),
    pa.field("pct_domestic_bond",    pa.float64()),
    pa.field("pct_intl_bond",        pa.float64()),
    pa.field("pct_cash",             pa.float64()),
    pa.field("pct_alternative",      pa.float64()),
    pa.field("manual_price",         pa.float64()),
])

ALLOCATION_COLS = [f.name for f in ALLOCATIONS_SCHEMA]

# Valid asset class values (expanded 16-value taxonomy)
ASSET_CLASSES = [
    "US Equity",
    "Intl Developed Equity",
    "Emerging Market Equity",
    "Investment-Grade Bond",
    "High-Yield Bond",
    "Intl/EM Bond",
    "TIPS/Inflation-Linked",
    "Cash & Equivalents",
    "Real Estate (REITs)",
    "Commodities",
    "Infrastructure",
    "Private Credit/BDC",
    "MLP/Energy Income",
    "Preferred Stock",
    "Multi-Asset/Allocation",
    "Other Alternative",
]

# Look-through percentage column names (must sum to 100)
LOOK_THROUGH_COLS = [
    "pct_domestic_stock",
    "pct_intl_stock",
    "pct_em_stock",
    "pct_domestic_bond",
    "pct_intl_bond",
    "pct_cash",
    "pct_alternative",
]

# Taxonomy dimension columns (from allocations module)
TAXONOMY_COLS = [
    "asset_class", "objective", "region", "equity_style",
    "fi_style", "fi_sector", "factor", "income_type", "vehicle_type",
]
