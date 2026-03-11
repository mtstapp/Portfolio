"""Streamlit portfolio dashboard – main entry point (Overview page).

Run with:
    streamlit run src/portfolio/dashboard/app.py

Additional pages are auto-loaded by Streamlit from dashboard/pages/:
    2_Holdings.py, 3_Allocation.py, 4_Performance.py,
    5_Income.py, 6_Risk.py, 7_Accounts.py
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from portfolio.storage.reader import DataReader
from portfolio.dashboard.components import sidebar as _sidebar

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Portfolio Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_resource
def _get_reader() -> DataReader:
    """Cache the DataReader as a resource (holds a duckdb connection)."""
    return DataReader()


@st.cache_data(ttl=300)
def _load():
    reader = _get_reader()
    return reader.current_holdings(), reader.current_accounts()


# ---------------------------------------------------------------------------
# Sidebar + Overview
# ---------------------------------------------------------------------------

_sidebar.render()

st.title("Portfolio Overview")

holdings, accounts = _load()
reader = _get_reader()

if not reader.has_data():
    st.info("No portfolio data found.")
    st.markdown("""
**To get started:**
1. Run `portfolio setup` to store your Schwab credentials in Keychain
2. Run `portfolio auth` to authenticate with Schwab
3. Run `portfolio refresh` to pull your portfolio data
4. Reload this page
""")
    st.stop()

if holdings.empty:
    st.warning("Holdings data is empty. Try running `portfolio refresh`.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------

total_value      = holdings["market_value"].sum()
total_cost       = holdings["cost_basis"].sum()
total_gain       = total_value - total_cost
total_gain_pct   = total_gain / total_cost * 100 if total_cost else 0.0
projected_income = holdings["div_annual_total"].sum() if "div_annual_total" in holdings.columns else 0.0
portfolio_beta   = holdings["weighted_beta"].sum() if "weighted_beta" in holdings.columns else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Portfolio Value",   f"${total_value:,.0f}")
col2.metric("Total Gain / Loss",       f"${total_gain:,.0f}", f"{total_gain_pct:+.1f}%")
col3.metric("Projected Annual Income", f"${projected_income:,.0f}")
col4.metric("Portfolio Beta",          f"{portfolio_beta:.2f}")

st.divider()

# ---------------------------------------------------------------------------
# Account breakdown  +  Security type pie
# ---------------------------------------------------------------------------

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("By Account")
    if not accounts.empty and "total_value" in accounts.columns:
        src_df = accounts.rename(columns={"total_value": "market_value",
                                           "account_name": "account_name"})
    else:
        src_df = holdings.groupby("account_name", as_index=False)["market_value"].sum()

    fig = px.bar(
        src_df.sort_values("market_value"),
        x="market_value",
        y="account_name",
        orientation="h",
        text_auto="$.3s",
        labels={"market_value": "Value ($)", "account_name": ""},
    )
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
    fig.update_xaxes(tickprefix="$", tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("By Security Type")
    by_type = holdings.groupby("security_type", as_index=False)["market_value"].sum()
    fig = px.pie(
        by_type,
        values="market_value",
        names="security_type",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Plotly,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Top 10 Holdings
# ---------------------------------------------------------------------------

st.subheader("Top 10 Holdings")

top10 = (
    holdings[holdings["symbol"] != "cashBalance"]
    .nlargest(10, "market_value")
    [["symbol", "description", "security_type", "account_name",
      "market_value", "gain_loss", "portfolio_pct"]]
    .copy()
)
top10["market_value"]  = top10["market_value"].map("${:,.0f}".format)
top10["gain_loss"]     = top10["gain_loss"].map("${:,.0f}".format)
top10["portfolio_pct"] = (top10["portfolio_pct"] * 100).map("{:.1f}%".format)
top10.columns = ["Symbol", "Description", "Type", "Account",
                 "Value", "Gain/Loss", "% Portfolio"]
st.dataframe(top10, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Portfolio value history (when available)
# ---------------------------------------------------------------------------

history = reader.portfolio_value_history(days=365)
if not history.empty and len(history) > 1:
    st.divider()
    st.subheader("Portfolio Value History")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=history["date"],
        y=history["total_value"],
        mode="lines",
        fill="tozeroy",
        line=dict(color="#00a3e0", width=2),
    ))
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=0, b=0),
        yaxis_tickprefix="$",
        yaxis_tickformat=",.0f",
    )
    st.plotly_chart(fig, use_container_width=True)
