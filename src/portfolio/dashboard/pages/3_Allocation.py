"""Allocation page – multi-dimensional portfolio breakdown."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from portfolio.storage.reader import DataReader
from portfolio.metrics import allocation as alloc_module
from portfolio.dashboard.components import sidebar as _sidebar

st.set_page_config(
    page_title="Allocation – Portfolio",
    page_icon="🥧",
    layout="wide",
)

_sidebar.render()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def _load():
    reader = DataReader()
    holdings = reader.current_holdings()

    # Try pre-computed metrics first; fall back to computing inline
    by_type    = reader.metric("allocation", "by_security_type")
    by_sector  = reader.metric("allocation", "by_sector")
    by_account = reader.metric("allocation", "by_account")
    by_class   = reader.metric("allocation", "by_asset_class")

    if holdings.empty:
        return holdings, by_type, by_sector, by_account, by_class

    if by_type.empty:
        by_type = alloc_module.by_security_type(holdings)
    if by_sector.empty:
        by_sector = alloc_module.by_sector(holdings)
    if by_account.empty:
        by_account = alloc_module.by_account(holdings)
    if by_class.empty:
        by_class = alloc_module.by_asset_class(holdings)

    return holdings, by_type, by_sector, by_account, by_class


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("🥧 Asset Allocation")

holdings, by_type, by_sector, by_account, by_class = _load()

if holdings.empty:
    st.info("No holdings data found. Run `portfolio refresh` to pull data.")
    st.stop()

total_value = holdings["market_value"].sum()
st.metric("Total Portfolio Value", f"${total_value:,.0f}")
st.divider()

# ---------------------------------------------------------------------------
# Row 1: Security Type & Asset Class (two pies)
# ---------------------------------------------------------------------------

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("By Security Type")
    if not by_type.empty:
        fig = px.pie(
            by_type,
            values="market_value",
            names="security_type",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Plotly,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(
            height=380,
            margin=dict(l=0, r=0, t=10, b=10),
            showlegend=True,
            legend=dict(orientation="v", x=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Table
        tbl = by_type.copy()
        tbl["market_value"] = tbl["market_value"].map("${:,.0f}".format)
        tbl["portfolio_pct"] = (by_type["portfolio_pct"] * 100).map("{:.1f}%".format)
        tbl.columns = ["Security Type", "Value", "% Portfolio"]
        st.dataframe(tbl, use_container_width=True, hide_index=True)
    else:
        st.info("No security type data available.")

with col_right:
    st.subheader("By Asset Class")
    if not by_class.empty:
        fig = px.pie(
            by_class,
            values="market_value",
            names="asset_class",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(
            height=380,
            margin=dict(l=0, r=0, t=10, b=10),
            showlegend=True,
            legend=dict(orientation="v", x=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

        tbl = by_class.copy()
        tbl["market_value"] = tbl["market_value"].map("${:,.0f}".format)
        tbl["portfolio_pct"] = (by_class["portfolio_pct"] * 100).map("{:.1f}%".format)
        tbl.columns = ["Asset Class", "Value", "% Portfolio"]
        st.dataframe(tbl, use_container_width=True, hide_index=True)
    else:
        st.info(
            "Asset class data not available. "
            "Add asset class assignments in the Google Sheet Allocations tab."
        )

st.divider()

# ---------------------------------------------------------------------------
# Row 2: Sector & Account (horizontal bars)
# ---------------------------------------------------------------------------

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("By Sector")
    if not by_sector.empty:
        # Filter to top 15 sectors by value
        top_sectors = by_sector.nlargest(15, "market_value")
        fig = px.bar(
            top_sectors,
            x="market_value",
            y="sector",
            orientation="h",
            text="portfolio_pct",
            labels={"market_value": "Value ($)", "sector": ""},
            color="market_value",
            color_continuous_scale="Blues",
        )
        fig.update_traces(
            texttemplate="%{text:.1%}",
            textposition="outside",
        )
        fig.update_layout(
            height=460,
            margin=dict(l=0, r=0, t=0, b=0),
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
        )
        fig.update_xaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No sector data available (requires yfinance enrichment).")

with col_right:
    st.subheader("By Account")
    if not by_account.empty:
        fig = px.bar(
            by_account,
            x="market_value",
            y="account_name",
            orientation="h",
            text="portfolio_pct",
            labels={"market_value": "Value ($)", "account_name": ""},
            color="market_value",
            color_continuous_scale="Greens",
        )
        fig.update_traces(
            texttemplate="%{text:.1%}",
            textposition="outside",
        )
        fig.update_layout(
            height=460,
            margin=dict(l=0, r=0, t=0, b=0),
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
        )
        fig.update_xaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(fig, use_container_width=True)

        tbl = by_account.copy()
        tbl["market_value"] = tbl["market_value"].map("${:,.0f}".format)
        tbl["portfolio_pct"] = (by_account["portfolio_pct"] * 100).map("{:.1f}%".format)
        tbl = tbl[["account_name", "market_value", "portfolio_pct"]]
        tbl.columns = ["Account", "Value", "% Portfolio"]
        st.dataframe(tbl, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Look-through allocation (if Google Sheet look-through columns are present)
# ---------------------------------------------------------------------------

LOOK_THROUGH_COLS = [
    "pct_domestic_stock", "pct_intl_stock", "pct_emerging_stock",
    "pct_domestic_bond", "pct_intl_bond", "pct_cash", "pct_alternative",
]
lt_available = [c for c in LOOK_THROUGH_COLS if c in holdings.columns and (holdings[c] > 0).any()]

if lt_available:
    st.subheader("Look-Through Allocation (Blended)")
    st.caption(
        "Blended allocation computed from look-through percentages set in the "
        "Google Sheet Allocations tab. Funds without percentages use their raw security type."
    )

    lt_data = {}
    for col in lt_available:
        label = col.replace("pct_", "").replace("_", " ").title()
        blended_value = (holdings["market_value"] * holdings[col]).sum()
        lt_data[label] = blended_value

    lt_df = pd.DataFrame(
        list(lt_data.items()), columns=["Asset Class", "Blended Value"]
    ).sort_values("Blended Value", ascending=False)
    lt_df["% Portfolio"] = lt_df["Blended Value"] / lt_df["Blended Value"].sum()

    col_left, col_right = st.columns(2)
    with col_left:
        fig = px.pie(
            lt_df,
            values="Blended Value",
            names="Asset Class",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        lt_display = lt_df.copy()
        lt_display["Blended Value"] = lt_display["Blended Value"].map("${:,.0f}".format)
        lt_display["% Portfolio"] = (lt_df["% Portfolio"] * 100).map("{:.1f}%".format)
        st.dataframe(lt_display, use_container_width=True, hide_index=True)
