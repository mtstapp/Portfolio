"""Income page – dividend and distribution projections."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from portfolio.storage.reader import DataReader
from portfolio.metrics import income as income_module
from portfolio.dashboard.components import sidebar as _sidebar

st.set_page_config(
    page_title="Income – Portfolio",
    page_icon="💰",
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

    summary_df   = reader.metric("income", "summary")
    by_pos_df    = reader.metric("income", "by_position")
    by_acct_df   = reader.metric("income", "by_account")
    monthly_df   = reader.metric("income", "monthly_estimate")

    if holdings.empty:
        return holdings, summary_df, by_pos_df, by_acct_df, monthly_df

    if summary_df.empty:
        summary_df = income_module.summary(holdings)
    if by_pos_df.empty:
        by_pos_df = income_module.by_position(holdings)
    if by_acct_df.empty:
        by_acct_df = income_module.by_account(holdings)
    if monthly_df.empty:
        monthly_df = income_module.monthly_estimate(holdings)

    return holdings, summary_df, by_pos_df, by_acct_df, monthly_df


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("💰 Income")
st.caption(
    "Projected annual income is based on trailing-twelve-month dividend data "
    "from Schwab fundamentals. ML Benefits 401k positions show $0 until "
    "enrichment data is available."
)

holdings, summary_df, by_pos_df, by_acct_df, monthly_df = _load()

if holdings.empty:
    st.info("No holdings data found. Run `portfolio refresh` to pull data.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------

if not summary_df.empty:
    row = summary_df.iloc[0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Projected Annual Income", f"${row['total_projected_income']:,.0f}")
    col2.metric("Portfolio Yield",         f"{row['portfolio_yield_pct']:.2f}%")
    col3.metric("Income-Paying Positions", f"{int(row['paying_positions'])}")
    monthly_est = row["total_projected_income"] / 12
    col4.metric("Est. Monthly Income",     f"${monthly_est:,.0f}")
else:
    st.warning("Income summary not available. Run `portfolio refresh` to compute metrics.")

st.divider()

# ---------------------------------------------------------------------------
# Monthly income estimate (bar chart)
# ---------------------------------------------------------------------------

if not monthly_df.empty:
    st.subheader("Monthly Income Estimate")
    st.caption("Simplified estimate: annual income ÷ 12. Actual payment months vary by security.")

    monthly_val = monthly_df.iloc[0]["month_1"]  # all months equal in simple model
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_chart_df = pd.DataFrame({
        "Month": months,
        "Estimated Income": [monthly_val] * 12,
    })

    fig = px.bar(
        monthly_chart_df,
        x="Month",
        y="Estimated Income",
        labels={"Estimated Income": "Est. Income ($)"},
        color_discrete_sequence=["#27ae60"],
        text_auto="$.0f",
    )
    fig.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=10, b=0),
        yaxis_tickprefix="$",
        yaxis_tickformat=",.0f",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.divider()

# ---------------------------------------------------------------------------
# Top income positions
# ---------------------------------------------------------------------------

if not by_pos_df.empty:
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Top Income Positions")

        top20 = by_pos_df.nlargest(20, "div_annual_total") if "div_annual_total" in by_pos_df.columns else by_pos_df.head(20)
        fig = px.bar(
            top20,
            x="div_annual_total",
            y="symbol",
            orientation="h",
            labels={"div_annual_total": "Annual Income ($)", "symbol": ""},
            color="div_annual_total",
            color_continuous_scale="Greens",
        )
        fig.update_layout(
            height=520,
            margin=dict(l=0, r=0, t=10, b=0),
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
        )
        fig.update_xaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Position Detail")
        tbl = by_pos_df.copy()
        format_map = {}
        if "market_value" in tbl.columns:
            tbl["market_value"] = tbl["market_value"].map("${:,.0f}".format)
        if "div_annual_total" in tbl.columns:
            tbl["div_annual_total"] = by_pos_df["div_annual_total"].map("${:,.0f}".format)
        if "dividend_yield" in tbl.columns:
            tbl["dividend_yield"] = (by_pos_df["dividend_yield"] * 100).map("{:.2f}%".format)
        if "yoc" in tbl.columns:
            tbl["yoc"] = (by_pos_df["yoc"] * 100).map("{:.2f}%".format)

        show_cols = [c for c in ["symbol", "description", "market_value",
                                  "div_annual_total", "dividend_yield", "yoc"]
                     if c in tbl.columns]
        col_labels = {
            "symbol":          "Symbol",
            "description":     "Name",
            "market_value":    "Value",
            "div_annual_total":"Annual Inc.",
            "dividend_yield":  "Div Yield",
            "yoc":             "YOC",
        }
        tbl = tbl[show_cols].rename(columns=col_labels)
        st.dataframe(tbl, use_container_width=True, hide_index=True, height=520)

    st.divider()

else:
    st.info(
        "No income-paying positions found. "
        "This may be because no dividend data was returned from Schwab fundamentals."
    )
    st.divider()

# ---------------------------------------------------------------------------
# By account
# ---------------------------------------------------------------------------

if not by_acct_df.empty:
    st.subheader("Income by Account")

    col_left, col_right = st.columns(2)

    with col_left:
        fig = px.bar(
            by_acct_df,
            x="projected_income",
            y="account_name",
            orientation="h",
            text="yield_pct",
            labels={"projected_income": "Annual Income ($)", "account_name": ""},
            color="projected_income",
            color_continuous_scale="Greens",
        )
        fig.update_traces(
            texttemplate="%{text:.2f}%",
            textposition="outside",
        )
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
        )
        fig.update_xaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        tbl = by_acct_df.copy()
        tbl["projected_income"] = by_acct_df["projected_income"].map("${:,.0f}".format)
        tbl["yield_pct"] = by_acct_df["yield_pct"].map("{:.2f}%".format)
        tbl = tbl[["account_name", "projected_income", "yield_pct"]]
        tbl.columns = ["Account", "Annual Income", "Yield"]
        st.dataframe(tbl, use_container_width=True, hide_index=True)
