"""Performance page – returns, gain/loss, and portfolio history."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from portfolio.storage.reader import DataReader
from portfolio.metrics import performance as perf_module
from portfolio.dashboard.components import sidebar as _sidebar

st.set_page_config(
    page_title="Performance – Portfolio",
    page_icon="📈",
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

    summary_df  = reader.metric("performance", "summary")
    by_pos_df   = reader.metric("performance", "by_position")
    by_acct_df  = reader.metric("performance", "by_account")
    history_df  = reader.portfolio_value_history(days=365)
    bench_df    = reader.metric("performance", "vs_benchmark")

    # Fall back to inline computation if metrics not yet written
    if holdings.empty:
        return holdings, summary_df, by_pos_df, by_acct_df, history_df, bench_df

    if summary_df.empty:
        summary_df = perf_module.summary(holdings)
    if by_pos_df.empty:
        by_pos_df = perf_module.by_position(holdings)
    if by_acct_df.empty:
        by_acct_df = perf_module.by_account(holdings)
    if bench_df.empty and not history_df.empty:
        bench_df = perf_module.vs_benchmark(history_df)

    return holdings, summary_df, by_pos_df, by_acct_df, history_df, bench_df


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("📈 Performance")

holdings, summary_df, by_pos_df, by_acct_df, history_df, bench_df = _load()

if holdings.empty:
    st.info("No holdings data found. Run `portfolio refresh` to pull data.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------

if not summary_df.empty:
    row = summary_df.iloc[0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Value",    f"${row['total_value']:,.0f}")
    col2.metric("Total Cost",     f"${row['total_cost']:,.0f}")
    col3.metric(
        "Total Gain / Loss",
        f"${row['total_gain']:,.0f}",
        delta=f"{row['total_gain_pct']:+.1f}%",
    )
    col4.metric("Positions", f"{int(row['position_count'])}")

st.divider()

# ---------------------------------------------------------------------------
# Portfolio value history
# ---------------------------------------------------------------------------

if not history_df.empty and len(history_df) > 1:
    st.subheader("Portfolio Value History")

    col_left, col_right = st.columns([3, 1])

    with col_left:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=history_df["date"],
            y=history_df["total_value"],
            mode="lines",
            fill="tozeroy",
            name="Portfolio",
            line=dict(color="#00a3e0", width=2),
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis_tickprefix="$",
            yaxis_tickformat=",.0f",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        if len(history_df) >= 2:
            first_val = history_df["total_value"].iloc[0]
            last_val  = history_df["total_value"].iloc[-1]
            period_gain = last_val - first_val
            period_pct  = period_gain / first_val * 100 if first_val else 0
            n_days = len(history_df)

            st.metric(f"{n_days}-day gain",
                      f"${period_gain:,.0f}",
                      delta=f"{period_pct:+.1f}%")
            st.metric("Start value", f"${first_val:,.0f}")
            st.metric("End value",   f"${last_val:,.0f}")

    # Return chart
    if not bench_df.empty and len(bench_df) > 1:
        st.subheader("Cumulative Return")
        fig2 = px.line(
            bench_df,
            x="date",
            y="portfolio_return_pct",
            labels={"portfolio_return_pct": "Return (%)", "date": "Date"},
        )
        fig2.update_layout(
            height=250,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        fig2.add_hline(y=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

elif len(history_df) <= 1:
    st.info(
        "Portfolio history chart will appear after multiple daily refreshes. "
        "Each `portfolio refresh` adds a snapshot."
    )
    st.divider()

# ---------------------------------------------------------------------------
# By account
# ---------------------------------------------------------------------------

if not by_acct_df.empty:
    st.subheader("Performance by Account")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        colors = by_acct_df["gain_loss"].apply(lambda v: "#2ecc71" if v >= 0 else "#e74c3c")
        fig = go.Figure(go.Bar(
            x=by_acct_df["gain_loss"],
            y=by_acct_df["account_name"],
            orientation="h",
            marker_color=colors.tolist(),
            text=by_acct_df["gain_pct"].apply(lambda v: f"{v:+.1f}%"),
            textposition="outside",
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_tickprefix="$",
            xaxis_tickformat=",.0f",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        tbl = by_acct_df.copy()
        tbl["market_value"] = tbl["market_value"].map("${:,.0f}".format)
        tbl["cost_basis"]   = tbl["cost_basis"].map("${:,.0f}".format)
        tbl["gain_loss"]    = by_acct_df["gain_loss"].map("${:,.0f}".format)
        tbl["gain_pct"]     = by_acct_df["gain_pct"].map("{:+.1f}%".format)
        tbl = tbl[["account_name", "market_value", "cost_basis", "gain_loss", "gain_pct"]]
        tbl.columns = ["Account", "Value", "Cost", "Gain/Loss", "Return"]
        st.dataframe(tbl, use_container_width=True, hide_index=True)

    st.divider()

# ---------------------------------------------------------------------------
# By position
# ---------------------------------------------------------------------------

st.subheader("All Positions")

if not by_pos_df.empty:
    # Add sort control
    sort_col = st.selectbox(
        "Sort by",
        options=["market_value", "gain_loss", "gain_pct", "portfolio_pct"],
        format_func=lambda c: {
            "market_value": "Market Value",
            "gain_loss":    "Gain / Loss ($)",
            "gain_pct":     "Return (%)",
            "portfolio_pct": "% Portfolio",
        }.get(c, c),
    )
    ascending = st.checkbox("Ascending", value=False)

    display_df = by_pos_df.sort_values(sort_col, ascending=ascending).copy()
    display_df = display_df[display_df["symbol"] != "cashBalance"]

    # Format
    for col in ["market_value", "cost_basis", "gain_loss"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].map("${:,.0f}".format)
    if "gain_pct" in display_df.columns:
        display_df["gain_pct"] = by_pos_df.sort_values(
            sort_col, ascending=ascending
        )["gain_pct"].map("{:+.1f}%".format)
    if "portfolio_pct" in display_df.columns:
        display_df["portfolio_pct"] = by_pos_df.sort_values(
            sort_col, ascending=ascending
        )["portfolio_pct"].apply(lambda v: f"{v*100:.2f}%")

    col_rename = {
        "symbol":        "Symbol",
        "description":   "Description",
        "security_type": "Type",
        "account_name":  "Account",
        "market_value":  "Value",
        "cost_basis":    "Cost",
        "gain_loss":     "Gain/Loss",
        "gain_pct":      "Return",
        "portfolio_pct": "% Portfolio",
    }
    available_cols = [c for c in col_rename if c in display_df.columns]
    display_df = display_df[available_cols].rename(columns=col_rename)

    st.dataframe(display_df, use_container_width=True, hide_index=True, height=480)
