"""Accounts page – per-account summary and holdings drill-down."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from portfolio.storage.reader import DataReader
from portfolio.dashboard.components import sidebar as _sidebar

st.set_page_config(
    page_title="Accounts – Portfolio",
    page_icon="🏦",
    layout="wide",
)

_sidebar.render()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def _load():
    reader = DataReader()
    return reader.current_holdings(), reader.current_accounts()


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("🏦 Accounts")

holdings, accounts = _load()

if holdings.empty:
    st.info("No holdings data found. Run `portfolio refresh` to pull data.")
    st.stop()

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------

total_value  = holdings["market_value"].sum()
total_gain   = holdings["gain_loss"].sum()
total_cost   = holdings["cost_basis"].sum()
gain_pct     = total_gain / total_cost * 100 if total_cost else 0.0
n_accounts   = holdings["account_id"].nunique()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Portfolio Value", f"${total_value:,.0f}")
col2.metric("Total Gain / Loss",     f"${total_gain:,.0f}", f"{gain_pct:+.1f}%")
col3.metric("Accounts",              f"{n_accounts}")
col4.metric("Total Positions",       f"{len(holdings[holdings['symbol'] != 'cashBalance'])}")

st.divider()

# ---------------------------------------------------------------------------
# Account value chart
# ---------------------------------------------------------------------------

if not accounts.empty and "total_value" in accounts.columns:
    acct_df = accounts.copy()
    value_col = "total_value"
else:
    # Build from holdings
    acct_df = (
        holdings.groupby(["account_id", "account_name"], as_index=False)["market_value"]
        .sum()
        .rename(columns={"market_value": "total_value"})
    )
    value_col = "total_value"

col_left, col_right = st.columns([2, 1])

with col_left:
    fig = px.bar(
        acct_df.sort_values("total_value"),
        x="total_value",
        y="account_name",
        orientation="h",
        text_auto="$.3s",
        labels={"total_value": "Value ($)", "account_name": ""},
        color="total_value",
        color_continuous_scale="Blues",
    )
    fig.update_layout(
        height=max(260, 55 * len(acct_df)),
        margin=dict(l=0, r=0, t=10, b=0),
        coloraxis_showscale=False,
    )
    fig.update_xaxes(tickprefix="$", tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    # Pie
    fig2 = px.pie(
        acct_df,
        values="total_value",
        names="account_name",
        hole=0.4,
    )
    fig2.update_traces(textposition="inside", textinfo="percent+label")
    fig2.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Accounts table (from accounts Parquet)
# ---------------------------------------------------------------------------

if not accounts.empty:
    st.subheader("Account Balances")

    display_cols = [c for c in [
        "account_id", "account_name", "account_type", "source",
        "total_value", "liquidation_value", "cash_balance",
    ] if c in accounts.columns]
    tbl = accounts[display_cols].copy()

    fmt_cols = ["total_value", "liquidation_value", "cash_balance"]
    for col in fmt_cols:
        if col in tbl.columns:
            tbl[col] = accounts[col].map("${:,.0f}".format)

    col_labels = {
        "account_id":         "Account ID",
        "account_name":       "Account",
        "account_type":       "Type",
        "source":             "Source",
        "total_value":        "Total Value",
        "liquidation_value":  "Liquidation Value",
        "cash_balance":       "Cash Balance",
    }
    tbl = tbl.rename(columns={k: v for k, v in col_labels.items() if k in tbl.columns})
    st.dataframe(tbl, use_container_width=True, hide_index=True)
    st.divider()

# ---------------------------------------------------------------------------
# Per-account holdings drill-down
# ---------------------------------------------------------------------------

st.subheader("Holdings by Account")

all_accounts = sorted(holdings["account_name"].dropna().unique())
selected = st.selectbox("Select Account", options=all_accounts)

if selected:
    acct_holdings = holdings[
        (holdings["account_name"] == selected) &
        (holdings["symbol"] != "cashBalance")
    ].copy()

    cash_rows = holdings[
        (holdings["account_name"] == selected) &
        (holdings["symbol"] == "cashBalance")
    ]

    # Account KPIs
    acct_value = holdings[holdings["account_name"] == selected]["market_value"].sum()
    acct_gain  = acct_holdings["gain_loss"].sum()
    acct_cost  = acct_holdings["cost_basis"].sum()
    acct_gain_pct = acct_gain / acct_cost * 100 if acct_cost else 0.0

    cash_balance = cash_rows["market_value"].sum() if not cash_rows.empty else 0.0

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Account Value",  f"${acct_value:,.0f}")
    mc2.metric("Gain / Loss",    f"${acct_gain:,.0f}", f"{acct_gain_pct:+.1f}%")
    mc3.metric("Positions",      f"{len(acct_holdings)}")
    mc4.metric("Cash Balance",   f"${cash_balance:,.0f}")

    if acct_holdings.empty:
        st.info("No positions for this account.")
    else:
        # Treemap of positions
        if "sector" in acct_holdings.columns:
            fig = px.treemap(
                acct_holdings[acct_holdings["market_value"] > 0],
                path=["sector", "symbol"],
                values="market_value",
                color="gain_loss",
                color_continuous_scale=["#e74c3c", "#95a5a6", "#2ecc71"],
                color_continuous_midpoint=0,
                hover_data={"market_value": ":$,.0f", "gain_loss": ":$,.0f"},
            )
            fig.update_layout(
                height=400,
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Detail table
        display_cols = [c for c in [
            "symbol", "description", "security_type",
            "quantity", "current_price", "market_value",
            "cost_basis", "gain_loss", "portfolio_pct",
        ] if c in acct_holdings.columns]
        tbl = acct_holdings[display_cols].copy()

        fmt = {}
        if "current_price" in tbl.columns:
            tbl["current_price"] = acct_holdings["current_price"].map("${:,.2f}".format)
        if "market_value" in tbl.columns:
            tbl["market_value"] = acct_holdings["market_value"].map("${:,.0f}".format)
        if "cost_basis" in tbl.columns:
            tbl["cost_basis"] = acct_holdings["cost_basis"].map("${:,.0f}".format)
        if "gain_loss" in tbl.columns:
            tbl["gain_loss"] = acct_holdings["gain_loss"].map("${:,.0f}".format)
        if "portfolio_pct" in tbl.columns:
            tbl["portfolio_pct"] = (acct_holdings["portfolio_pct"] * 100).map("{:.2f}%".format)
        if "quantity" in tbl.columns:
            tbl["quantity"] = acct_holdings["quantity"].map("{:,.4g}".format)

        col_labels = {
            "symbol":        "Symbol",
            "description":   "Description",
            "security_type": "Type",
            "quantity":      "Qty",
            "current_price": "Price",
            "market_value":  "Value",
            "cost_basis":    "Cost",
            "gain_loss":     "Gain/Loss",
            "portfolio_pct": "% Portfolio",
        }
        tbl = tbl.rename(columns={k: v for k, v in col_labels.items() if k in tbl.columns})
        st.dataframe(
            tbl.sort_values("Value", ascending=False) if "Value" in tbl.columns else tbl,
            use_container_width=True,
            hide_index=True,
            height=400,
        )
