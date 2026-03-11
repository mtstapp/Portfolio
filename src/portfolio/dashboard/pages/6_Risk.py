"""Risk page – beta, volatility, Sharpe ratio, and drawdown."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from portfolio.storage.reader import DataReader
from portfolio.metrics import risk as risk_module
from portfolio.dashboard.components import sidebar as _sidebar

st.set_page_config(
    page_title="Risk – Portfolio",
    page_icon="⚠️",
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
    history  = reader.portfolio_value_history(days=365)

    beta_summary = reader.metric("risk", "portfolio_beta")
    by_type_df   = reader.metric("risk", "by_security_type")
    beta_dist_df = reader.metric("risk", "beta_distribution")
    vol_df       = reader.metric("risk", "volatility_and_sharpe")

    if holdings.empty:
        return holdings, history, beta_summary, by_type_df, beta_dist_df, vol_df

    if beta_summary.empty:
        beta_summary = risk_module.portfolio_beta_summary(holdings)
    if by_type_df.empty:
        by_type_df = risk_module.by_security_type(holdings)
    if beta_dist_df.empty:
        beta_dist_df = risk_module.beta_distribution(holdings)
    if vol_df.empty and not history.empty:
        vol_df = risk_module.volatility_and_sharpe(history)

    return holdings, history, beta_summary, by_type_df, beta_dist_df, vol_df


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("⚠️ Risk")
st.caption(
    "Beta and weighted beta come from Schwab fundamentals (updated daily). "
    "Volatility, Sharpe ratio, and max drawdown require ≥ 30 daily snapshots "
    "and will populate automatically as data accumulates."
)

holdings, history, beta_summary, by_type_df, beta_dist_df, vol_df = _load()

if holdings.empty:
    st.info("No holdings data found. Run `portfolio refresh` to pull data.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

if not beta_summary.empty:
    row = beta_summary.iloc[0]
    col1.metric("Portfolio Beta",          f"{row['portfolio_beta']:.3f}")
    col2.metric("Total Value",             f"${row['total_value']:,.0f}")
    col3.metric("Beta-Adjusted Exposure",  f"${row['beta_adjusted_exposure']:,.0f}")
else:
    col1.metric("Portfolio Beta", "–")

if not vol_df.empty:
    vrow = vol_df.iloc[0]
    col4.metric("Annualised Volatility",   f"{vrow['annualised_volatility_pct']:.1f}%")
else:
    snapshots = len(history)
    col4.metric("Annualised Volatility",
                "–",
                delta=f"{snapshots}/30 snapshots" if snapshots < 30 else None,
                delta_color="off")

st.divider()

# ---------------------------------------------------------------------------
# Sharpe + Max Drawdown (when available)
# ---------------------------------------------------------------------------

if not vol_df.empty:
    vrow = vol_df.iloc[0]
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Sharpe Ratio",    f"{vrow['sharpe_ratio']:.2f}")
    col_b.metric("Max Drawdown",    f"{vrow['max_drawdown_pct']:.1f}%")
    col_c.metric("Snapshots Used",  f"{int(vrow['snapshot_count'])}")
    st.divider()
else:
    need_more = 30 - len(history)
    if need_more > 0:
        st.info(
            f"Volatility, Sharpe ratio, and max drawdown will be available "
            f"after **{need_more} more** daily refresh(es) accumulate."
        )
    st.divider()

# ---------------------------------------------------------------------------
# Beta by security type & Beta distribution
# ---------------------------------------------------------------------------

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Weighted Beta by Security Type")
    if not by_type_df.empty:
        fig = px.bar(
            by_type_df,
            x="avg_beta",
            y="security_type",
            orientation="h",
            text="avg_beta",
            labels={"avg_beta": "Avg Beta (weighted)", "security_type": ""},
            color="avg_beta",
            color_continuous_scale="Oranges",
        )
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig.update_layout(
            height=320,
            margin=dict(l=0, r=0, t=10, b=0),
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
        )
        fig.add_vline(x=1.0, line_dash="dash", line_color="gray",
                      annotation_text="Market β=1", annotation_position="top right")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Beta data not available (requires Schwab fundamentals enrichment).")

with col_right:
    st.subheader("Portfolio Beta Explanation")
    st.markdown("""
**Portfolio Beta** measures sensitivity to market movements:
- **β = 1.0** moves in line with the market (S&P 500)
- **β > 1.0** is more volatile than the market
- **β < 1.0** is less volatile than the market
- **β = 0** has no correlation (cash, some bonds)

**Sharpe Ratio** measures return per unit of risk:
- **> 1.0** is generally considered good
- **> 2.0** is considered very good

**Max Drawdown** is the largest peak-to-trough decline
in portfolio value during the measured period.
""")

st.divider()

# ---------------------------------------------------------------------------
# Beta distribution table
# ---------------------------------------------------------------------------

if not beta_dist_df.empty:
    st.subheader("Beta Contribution by Position")
    st.caption(
        "Sorted by beta contribution (beta × portfolio weight). "
        "Positions with higher contributions drive more of the portfolio's market risk."
    )

    # Chart: top 20 by beta contribution
    top20 = beta_dist_df.head(20)
    col_left, col_right = st.columns([2, 1])

    with col_left:
        fig = px.bar(
            top20,
            x="beta_contribution",
            y="symbol",
            orientation="h",
            color="beta",
            color_continuous_scale="RdYlGn_r",
            labels={"beta_contribution": "Beta Contribution", "symbol": ""},
            hover_data={"beta": ":.3f", "market_value": ":$,.0f"},
        )
        fig.update_layout(
            height=480,
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        tbl = beta_dist_df.head(30).copy()
        format_cols = {}
        if "market_value" in tbl.columns:
            tbl["market_value"] = beta_dist_df.head(30)["market_value"].map("${:,.0f}".format)
        if "beta" in tbl.columns:
            tbl["beta"] = beta_dist_df.head(30)["beta"].map("{:.2f}".format)
        if "beta_contribution" in tbl.columns:
            tbl["beta_contribution"] = beta_dist_df.head(30)["beta_contribution"].map("{:.4f}".format)
        if "portfolio_pct" in tbl.columns:
            tbl["portfolio_pct"] = (beta_dist_df.head(30)["portfolio_pct"] * 100).map("{:.2f}%".format)

        show_cols = [c for c in ["symbol", "security_type", "market_value",
                                  "beta", "portfolio_pct", "beta_contribution"]
                     if c in tbl.columns]
        col_labels = {
            "symbol":           "Symbol",
            "security_type":    "Type",
            "market_value":     "Value",
            "beta":             "Beta",
            "portfolio_pct":    "% Portfolio",
            "beta_contribution":"Beta Contrib.",
        }
        tbl = tbl[show_cols].rename(columns=col_labels)
        st.dataframe(tbl, use_container_width=True, hide_index=True, height=480)

# ---------------------------------------------------------------------------
# Portfolio value drawdown chart (when history available)
# ---------------------------------------------------------------------------

if not history.empty and len(history) >= 5:
    st.divider()
    st.subheader("Portfolio Value & Drawdown")

    hist = history.sort_values("date").copy()
    hist["rolling_max"] = hist["total_value"].cummax()
    hist["drawdown_pct"] = (hist["total_value"] - hist["rolling_max"]) / hist["rolling_max"] * 100

    col_left, col_right = st.columns(2)

    with col_left:
        fig = px.line(
            hist, x="date", y="total_value",
            labels={"total_value": "Portfolio Value ($)", "date": ""},
        )
        fig.update_layout(
            height=250,
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis_tickprefix="$",
            yaxis_tickformat=",.0f",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        fig2 = px.area(
            hist, x="date", y="drawdown_pct",
            labels={"drawdown_pct": "Drawdown (%)", "date": ""},
            color_discrete_sequence=["#e74c3c"],
        )
        fig2.update_layout(
            height=250,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig2, use_container_width=True)
