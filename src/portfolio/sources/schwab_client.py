"""Schwab API data extraction.

Migrated and refactored from /Users/mark/dev/cspull/main.py.

Key design decisions preserved from the original:
  - Uses schwabdev.Client for all API calls
  - OPTION positions are excluded
  - COLLECTIVE_INVESTMENT → ETF
  - Cash balance is included as a synthetic position (symbol='cashBalance')
  - Symbol normalization: '.' → '-' for yfinance, '.' → '/' for instruments API
  - 2-second sleep between yfinance requests

New in this version:
  - Discovers ALL linked accounts dynamically (not hardcoded)
  - Returns DataFrames with the canonical schema from storage.schema
  - Credentials come from Keychain, not os.getenv()
"""

import logging
import time
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf

from portfolio import config
from portfolio.auth import schwab_oauth
from portfolio.storage import schema

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Account setup
# ---------------------------------------------------------------------------

def get_linked_accounts(client) -> list[dict]:
    """Return all linked accounts with their hash values and names.

    Each dict: {account_no, hash_value, account_type, description}
    Dynamic discovery – no hardcoded account numbers.
    """
    linked = client.account_linked().json()
    accounts = []
    for acct in linked:
        accounts.append({
            "account_no": acct["accountNumber"][-4:],   # last 4 digits
            "account_number_full": acct["accountNumber"],
            "hash_value": acct["hashValue"],
            "description": acct.get("displayName", acct["accountNumber"][-4:]),
        })
    log.info("Found %d linked accounts", len(accounts))
    return accounts


# ---------------------------------------------------------------------------
# Account balances
# ---------------------------------------------------------------------------

def fetch_account_balances(client, accounts: list[dict]) -> pd.DataFrame:
    """Return a DataFrame with one row per account showing balances."""
    rows = []
    all_details = client.account_details_all().json()

    hash_to_info = {a["hash_value"]: a for a in accounts}

    if isinstance(all_details, list):
        for detail in all_details:
            sa = detail.get("securitiesAccount", {})
            account_no = sa.get("accountNumber", "")[-4:]
            acct_type = sa.get("type", "UNKNOWN")

            balances = sa.get("currentBalances", {})
            agg = detail.get("aggregatedBalance", {})

            rows.append({
                "date": date.today(),
                "account_id": account_no,
                "account_name": next(
                    (a["description"] for a in accounts if a["account_no"] == account_no),
                    account_no,
                ),
                "account_type": acct_type,
                "liquidation_value": agg.get("liquidationValue", 0),
                "cash_balance": balances.get("cashBalance", 0),
                "total_value": agg.get("liquidationValue", 0),
            })

    df = pd.DataFrame(rows)
    log.info("Fetched balances for %d accounts (total: $%,.0f)",
             len(df), df["liquidation_value"].sum() if not df.empty else 0)
    return df


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

def fetch_positions(client, accounts: list[dict]) -> pd.DataFrame:
    """Fetch all positions across all accounts. Returns raw position DataFrame."""
    rows = []

    for acct in accounts:
        try:
            detail = client.account_details(acct["hash_value"], fields="positions").json()
        except Exception:
            log.exception("Failed to fetch positions for account %s", acct["account_no"])
            continue

        sa = detail.get("securitiesAccount", {})

        # Cash balance as a synthetic position
        cash = sa.get("currentBalances", {}).get("cashBalance", 0)
        if cash:
            rows.append({
                "account_id": acct["account_no"],
                "account_name": acct["description"],
                "symbol": "cashBalance",
                "description": "Cash Balance",
                "security_type": "CASH",
                "quantity": cash,
                "average_price": 1.0,
                "market_value": cash,
                "cost_basis": cash,
                "current_price": 1.0,
            })

        for pos in sa.get("positions", []):
            instrument = pos.get("instrument", {})
            asset_type = instrument.get("assetType", "")

            # Skip options
            if asset_type == "OPTION":
                continue

            raw_symbol = instrument.get("symbol", "")
            # Normalize symbol: '.' → '-' for yfinance compatibility
            symbol = raw_symbol.replace(".", "-")

            # Map asset types to canonical names
            security_type = config.ASSET_TYPE_MAP.get(asset_type, asset_type)

            quantity = pos.get("longQuantity", 0) + pos.get("shortQuantity", 0)
            average_price = pos.get("averagePrice", 0)
            market_value = pos.get("marketValue", 0)
            cost_basis = quantity * average_price

            rows.append({
                "account_id": acct["account_no"],
                "account_name": acct["description"],
                "symbol": symbol,
                "description": "",          # filled below via batch quote
                "security_type": security_type,
                "quantity": quantity,
                "average_price": average_price,
                "market_value": market_value,
                "cost_basis": cost_basis,
                "current_price": market_value / quantity if quantity else 0,
            })

    df = pd.DataFrame(rows)
    log.info("Fetched %d raw positions across %d accounts", len(df), len(accounts))
    return df


def enrich_descriptions(client, df: pd.DataFrame) -> pd.DataFrame:
    """Add security descriptions via Schwab quote API (batch by symbol)."""
    symbols = [s for s in df["symbol"].unique() if s != "cashBalance"]
    desc_map: dict[str, str] = {"cashBalance": "Cash Balance"}

    # Schwab quote API can handle multiple symbols at once
    batch_size = 50
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        try:
            resp = client.quotes(batch, fields="reference")
            if resp.status_code == 200:
                data = resp.json()
                for sym in batch:
                    desc_map[sym] = (
                        data.get(sym, {})
                        .get("reference", {})
                        .get("description", sym)
                    )
        except Exception:
            log.warning("Failed to fetch descriptions for batch starting at %d", i)

    df["description"] = df["symbol"].map(lambda s: desc_map.get(s, s))
    return df


# ---------------------------------------------------------------------------
# Consolidation across accounts
# ---------------------------------------------------------------------------

def consolidate_positions(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate positions across accounts: total quantity, weighted avg price.

    Returns one row per symbol with totals. Preserves per-account detail
    in the raw layer; this produces the consolidated view.
    """
    # Weighted average price
    df = df.copy()
    df["weighted_value"] = df["quantity"] * df["average_price"]

    grp = df.groupby("symbol", as_index=False).agg(
        description=("description", "first"),
        security_type=("security_type", "first"),
        quantity=("quantity", "sum"),
        weighted_value=("weighted_value", "sum"),
        market_value=("market_value", "sum"),
        cost_basis=("cost_basis", "sum"),
    )

    grp["average_price"] = grp.apply(
        lambda r: r["weighted_value"] / r["quantity"] if r["quantity"] != 0 else 0,
        axis=1,
    )
    grp["current_price"] = grp.apply(
        lambda r: r["market_value"] / r["quantity"] if r["quantity"] != 0 else 0,
        axis=1,
    )
    grp["gain_loss"] = grp["market_value"] - grp["cost_basis"]
    grp.drop(columns=["weighted_value"], inplace=True)

    total_value = grp["market_value"].sum()
    grp["portfolio_pct"] = grp["market_value"] / total_value if total_value else 0

    log.info("Consolidated to %d unique positions (total value: $%,.0f)",
             len(grp), total_value)
    return grp


# ---------------------------------------------------------------------------
# Sector / industry enrichment via yfinance
# ---------------------------------------------------------------------------

def enrich_sector_industry(df: pd.DataFrame) -> pd.DataFrame:
    """Add Sector and Industry columns via yfinance. Mirrors cspull logic."""
    if "sector" not in df.columns:
        df["sector"] = None
    if "industry" not in df.columns:
        df["industry"] = None

    for idx, row in df.iterrows():
        symbol = row["symbol"]
        if symbol == "cashBalance":
            df.at[idx, "sector"] = "Cash"
            df.at[idx, "industry"] = "Cash"
            continue

        sec_type = row.get("security_type", "")
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if sec_type == "EQUITY":
                df.at[idx, "sector"] = info.get("sector") or "Unknown"
                df.at[idx, "industry"] = info.get("industry") or "Unknown"
            elif sec_type in ("ETF", "MUTUAL_FUND"):
                df.at[idx, "sector"] = info.get("category") or "Fund"
                df.at[idx, "industry"] = info.get("assetType") or sec_type
            else:
                df.at[idx, "sector"] = sec_type
                df.at[idx, "industry"] = sec_type

            time.sleep(2)  # Rate limiting (preserved from cspull)
        except Exception:
            log.warning("yfinance failed for %s", symbol)
            df.at[idx, "sector"] = "Unknown"
            df.at[idx, "industry"] = "Unknown"

    return df


# ---------------------------------------------------------------------------
# Fundamental data from Schwab instruments API
# ---------------------------------------------------------------------------

FUNDAMENTAL_COLS = [
    "beta", "dividend_amount", "dividend_yield", "eps",
    "gross_margin_mrq", "gross_margin_ttm", "market_cap",
    "pe_ratio", "pb_ratio", "return_on_assets", "return_on_equity",
]

_SCHWAB_FUNDAMENTAL_MAP = {
    "beta": "beta",
    "dividendAmount": "dividend_amount",
    "dividendYield": "dividend_yield",
    "eps": "eps",
    "grossMarginMRQ": "gross_margin_mrq",
    "grossMarginTTM": "gross_margin_ttm",
    "marketCap": "market_cap",
    "peRatio": "pe_ratio",
    "pbRatio": "pb_ratio",
    "returnOnAssets": "return_on_assets",
    "returnOnEquity": "return_on_equity",
}


def enrich_fundamentals(client, df: pd.DataFrame) -> pd.DataFrame:
    """Add fundamental data per position using Schwab's instruments API."""
    for col in FUNDAMENTAL_COLS:
        if col not in df.columns:
            df[col] = None

    for idx, row in df.iterrows():
        symbol = row["symbol"]
        if symbol == "cashBalance":
            continue

        # Schwab instruments API uses '/' separator (e.g., BRK/B)
        schwab_symbol = symbol.replace("-", "/")

        try:
            data = client.instruments(schwab_symbol, "fundamental").json()
            fund = data.get("instruments", [{}])[0].get("fundamental", {})

            for schwab_key, col_name in _SCHWAB_FUNDAMENTAL_MAP.items():
                df.at[idx, col_name] = fund.get(schwab_key)
        except Exception:
            log.warning("Fundamentals failed for %s", symbol)

    df[FUNDAMENTAL_COLS] = df[FUNDAMENTAL_COLS].fillna(0)

    # Derived columns (from cspull)
    total_value = df["market_value"].sum()
    df["portfolio_pct"] = df["market_value"] / total_value if total_value else 0
    df["weighted_beta"] = df["portfolio_pct"] * df["beta"]
    df["yoc"] = (df["dividend_amount"] / df["average_price"] * 100).fillna(0)
    df["div_annual_total"] = (df["dividend_amount"] * df["quantity"]).fillna(0)

    return df


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------

def fetch_transactions(client, accounts: list[dict],
                        start_date: date | None = None,
                        end_date: date | None = None) -> pd.DataFrame:
    """Fetch transaction history for all accounts."""
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=90)

    rows = []
    for acct in accounts:
        try:
            resp = client.account_transactions(
                acct["hash_value"],
                start_datetime=datetime.combine(start_date, datetime.min.time()),
                end_datetime=datetime.combine(end_date, datetime.max.time()),
            )
            if resp.status_code != 200:
                log.warning("Transactions failed for account %s: %s",
                            acct["account_no"], resp.status_code)
                continue

            for tx in resp.json():
                tx_type = tx.get("type", "")
                rows.append({
                    "date": tx.get("tradeDate", tx.get("settleDate", "")),
                    "account_id": acct["account_no"],
                    "account_name": acct["description"],
                    "transaction_type": tx_type.lower(),
                    "symbol": tx.get("transferItems", [{}])[0]
                               .get("instrument", {}).get("symbol", ""),
                    "quantity": tx.get("transferItems", [{}])[0].get("amount", 0),
                    "price": tx.get("transferItems", [{}])[0].get("price", 0),
                    "amount": tx.get("netAmount", 0),
                    "fees": tx.get("fees", {}).get("commission", 0),
                })
        except Exception:
            log.exception("Transactions failed for account %s", acct["account_no"])

    if not rows:
        return pd.DataFrame(columns=schema.TRANSACTION_COLS)

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Full pull (convenience wrapper used by daily_refresh)
# ---------------------------------------------------------------------------

def pull_all(include_fundamentals: bool = True,
             include_sector: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run a full Schwab data pull.

    Returns:
        accounts_df:    Account balances
        positions_df:   All positions (per-account, raw)
        transactions_df: Recent transaction history
    """
    client = schwab_oauth.create_client()
    accounts = get_linked_accounts(client)

    accounts_df = fetch_account_balances(client, accounts)

    positions_df = fetch_positions(client, accounts)
    positions_df = enrich_descriptions(client, positions_df)

    if include_sector:
        consolidated = consolidate_positions(positions_df)
        consolidated = enrich_sector_industry(consolidated)
        if include_fundamentals:
            consolidated = enrich_fundamentals(client, consolidated)
        # Merge enriched data back to per-account positions
        enrich_cols = [c for c in consolidated.columns
                       if c not in ("account_id", "account_name", "quantity",
                                    "average_price", "market_value", "cost_basis")]
        positions_df = positions_df.merge(
            consolidated[["symbol"] + [c for c in enrich_cols if c in consolidated.columns]],
            on="symbol", how="left", suffixes=("", "_enriched"),
        )

    transactions_df = fetch_transactions(client, accounts)

    return accounts_df, positions_df, transactions_df
