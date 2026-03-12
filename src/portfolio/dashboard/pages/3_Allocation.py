"""Allocation page – multi-dimensional portfolio breakdown.

Shows portfolio allocation across all taxonomy dimensions:
  - Asset Class, Objective, Region, Equity Style, Factor,
    Income Type, Vehicle Type, Tax Treatment, Sector, Account
  - Look-through blended allocation
"""

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

@st.cache_resource
def _get_reader() -> DataReader:
    return DataReader()


@st.cache_data(ttl=300)
def _load():
    reader = _get_reader()
    holdings = reader.current_holdings()
    return holdings


def _load_metric(name: str, compute_fn, holdings):
    """Load a pre-computed metric, falling back to inline computation."""
    reader = _get_reader()
    df = reader.metric("allocation", name)
    if df.empty and not holdings.empty:
        df = compute_fn(holdings)
    return df


# ---------------------------------------------------------------------------
# Reusable chart helpers
# ---------------------------------------------------------------------------

def _pie_chart(df: pd.DataFrame, values_col: str, names_col: str,
               color_seq=None, height: int = 380):
    """Render a donut chart + summary table."""
    if df.empty:
        st.info("No data available.")
        return

    color_seq = color_seq or px.colors.qualitative.Plotly
    fig = px.pie(
        df, values=values_col, names=names_col,
        hole=0.45, color_discrete_sequence=color_seq,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=10, b=10),
        showlegend=True,
        legend=dict(orientation="v", x=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

    tbl = df.copy()
    tbl[values_col] = tbl[values_col].map("${:,.0f}".format)
    tbl["portfolio_pct"] = (df["portfolio_pct"] * 100).map("{:.1f}%".format)
    display_cols = [names_col, values_col, "portfolio_pct"]
    display_cols = [c for c in display_cols if c in tbl.columns]
    nice_names = {names_col: names_col.replace("_", " ").title(),
                  values_col: "Value", "portfolio_pct": "% Portfolio"}
    tbl = tbl[display_cols].rename(columns=nice_names)
    st.dataframe(tbl, use_container_width=True, hide_index=True)


def _bar_chart(df: pd.DataFrame, x_col: str, y_col: str,
               color_scale: str = "Blues", height: int = 400):
    """Render a horizontal bar chart."""
    if df.empty:
        st.info("No data available.")
        return

    fig = px.bar(
        df, x=x_col, y=y_col, orientation="h",
        text="portfolio_pct",
        labels={x_col: "Value ($)", y_col: ""},
        color=x_col, color_continuous_scale=color_scale,
    )
    fig.update_traces(texttemplate="%{text:.1%}", textposition="outside")
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_showscale=False,
        yaxis={"categoryorder": "total ascending"},
    )
    fig.update_xaxes(tickprefix="$", tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)


def _render_style_box(by_style: pd.DataFrame, total_value: float):
    """Render a 3x3 Morningstar-style equity style box as a heatmap."""
    sizes = ["Large", "Mid", "Small"]
    styles = ["Value", "Blend", "Growth"]

    # Build 3x3 matrix
    matrix = []
    for cap in sizes:
        row = []
        for style in styles:
            cell_name = f"{cap} {style}"
            match = by_style[by_style["equity_style"] == cell_name]
            val = match["market_value"].sum() if not match.empty else 0
            row.append(val / total_value * 100 if total_value else 0)
        matrix.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=styles,
        y=sizes,
        text=[[f"{v:.1f}%" for v in row] for row in matrix],
        texttemplate="%{text}",
        colorscale="Blues",
        showscale=False,
    ))
    fig.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=30, b=0),
        title_text="Equity Style Box (% of Portfolio)",
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("🥧 Asset Allocation")

holdings = _load()

if holdings.empty:
    st.info("No holdings data found. Run `portfolio refresh` to pull data.")
    st.stop()

total_value = holdings["market_value"].sum()
st.metric("Total Portfolio Value", f"${total_value:,.0f}")
st.divider()

# ---------------------------------------------------------------------------
# Tabs for each dimension
# ---------------------------------------------------------------------------

tab_names = [
    "Asset Class", "Objective", "Region", "Equity Style",
    "Factor", "Income Type", "Vehicle Type", "Tax Treatment",
    "Sector", "Account", "Look-Through",
]
tabs = st.tabs(tab_names)

# ── Tab: Asset Class ────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("By Asset Class")
    by_class = _load_metric("by_asset_class", alloc_module.by_asset_class, holdings)
    col1, col2 = st.columns([1, 1])
    with col1:
        _pie_chart(by_class, "market_value", "asset_class",
                   px.colors.qualitative.Safe)
    with col2:
        _bar_chart(by_class, "market_value", "asset_class", "Tealgrn")

# ── Tab: Objective ──────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("By Investment Objective")
    by_obj = _load_metric("by_objective", alloc_module.by_objective, holdings)
    col1, col2 = st.columns([1, 1])
    with col1:
        _pie_chart(by_obj, "market_value", "objective",
                   px.colors.qualitative.Set2)
    with col2:
        if not by_obj.empty:
            st.caption("Growth = capital appreciation, Income = cash distributions, "
                       "Preservation = capital safety, Growth & Income = blend of both.")

# ── Tab: Region ─────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("By Geographic Region")
    by_reg = _load_metric("by_region", alloc_module.by_region, holdings)
    col1, col2 = st.columns([1, 1])
    with col1:
        _pie_chart(by_reg, "market_value", "region",
                   px.colors.qualitative.Dark2)
    with col2:
        _bar_chart(by_reg, "market_value", "region", "Viridis")

# ── Tab: Equity Style ──────────────────────────────────────────────────
with tabs[3]:
    st.subheader("By Equity Style (Morningstar Style Box)")
    by_style = _load_metric("by_equity_style", alloc_module.by_equity_style, holdings)
    if by_style.empty:
        st.info("No equity style data available. "
                "Set equity style values in the Google Sheet Allocations tab.")
    else:
        col1, col2 = st.columns([1, 1])
        with col1:
            _pie_chart(by_style, "market_value", "equity_style",
                       px.colors.qualitative.Plotly)
        with col2:
            _render_style_box(by_style, total_value)

# ── Tab: Factor ─────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("By Factor Exposure")
    by_fac = _load_metric("by_factor", alloc_module.by_factor, holdings)
    col1, col2 = st.columns([1, 1])
    with col1:
        _pie_chart(by_fac, "market_value", "factor",
                   px.colors.qualitative.Pastel)
    with col2:
        _bar_chart(by_fac, "market_value", "factor", "Purp")

# ── Tab: Income Type ───────────────────────────────────────────────────
with tabs[5]:
    st.subheader("By Income Type")
    by_inc = _load_metric("by_income_type", alloc_module.by_income_type, holdings)
    col1, col2 = st.columns([1, 1])
    with col1:
        _pie_chart(by_inc, "market_value", "income_type",
                   px.colors.qualitative.Bold)
    with col2:
        _bar_chart(by_inc, "market_value", "income_type", "Oranges")

# ── Tab: Vehicle Type ──────────────────────────────────────────────────
with tabs[6]:
    st.subheader("By Vehicle Type")
    by_veh = _load_metric("by_vehicle_type", alloc_module.by_vehicle_type, holdings)
    col1, col2 = st.columns([1, 1])
    with col1:
        _pie_chart(by_veh, "market_value", "vehicle_type",
                   px.colors.qualitative.Plotly)
    with col2:
        if not by_veh.empty:
            st.caption("Individual Stock, ETF, Open-End Mutual Fund, etc.")

# ── Tab: Tax Treatment ─────────────────────────────────────────────────
with tabs[7]:
    st.subheader("By Account Tax Treatment")
    by_tax = _load_metric("by_tax_treatment", alloc_module.by_tax_treatment, holdings)
    col1, col2 = st.columns([1, 1])
    with col1:
        _pie_chart(by_tax, "market_value", "tax_treatment",
                   ["#2ecc71", "#e67e22", "#3498db", "#9b59b6"])
    with col2:
        if not by_tax.empty:
            st.caption(
                "Taxable = gains taxed annually | Tax-Deferred = taxed on withdrawal | "
                "Tax-Exempt = tax-free withdrawals | HSA = triple-tax-advantaged"
            )

# ── Tab: Sector ─────────────────────────────────────────────────────────
with tabs[8]:
    st.subheader("By Sector")
    by_sector = _load_metric("by_sector", alloc_module.by_sector, holdings)
    if not by_sector.empty:
        top_sectors = by_sector.nlargest(15, "market_value")
        _bar_chart(top_sectors, "market_value", "sector", "Blues", height=460)
    else:
        st.info("No sector data available (requires yfinance enrichment).")

# ── Tab: Account ────────────────────────────────────────────────────────
with tabs[9]:
    st.subheader("By Account")
    by_acct = _load_metric("by_account", alloc_module.by_account, holdings)
    if not by_acct.empty:
        col1, col2 = st.columns([1, 1])
        with col1:
            _bar_chart(by_acct, "market_value", "account_name", "Greens")
        with col2:
            tbl = by_acct.copy()
            tbl["market_value"] = tbl["market_value"].map("${:,.0f}".format)
            tbl["portfolio_pct"] = (by_acct["portfolio_pct"] * 100).map("{:.1f}%".format)
            tbl = tbl[["account_name", "market_value", "portfolio_pct"]]
            tbl.columns = ["Account", "Value", "% Portfolio"]
            st.dataframe(tbl, use_container_width=True, hide_index=True)

# ── Tab: Look-Through ──────────────────────────────────────────────────
with tabs[10]:
    st.subheader("Look-Through Allocation (Blended)")
    st.caption(
        "Blended allocation computed from look-through percentages set in the "
        "Google Sheet Allocations tab. Funds without percentages use their raw security type."
    )

    LOOK_THROUGH_COLS = [
        "pct_domestic_stock", "pct_intl_stock", "pct_em_stock",
        "pct_domestic_bond", "pct_intl_bond", "pct_cash", "pct_alternative",
    ]
    lt_available = [
        c for c in LOOK_THROUGH_COLS
        if c in holdings.columns and (holdings[c] > 0).any()
    ]

    if lt_available:
        lt_data = {}
        for col in lt_available:
            label = col.replace("pct_", "").replace("_", " ").title()
            blended_value = (holdings["market_value"] * holdings[col]).sum()
            lt_data[label] = blended_value

        lt_df = pd.DataFrame(
            list(lt_data.items()), columns=["Asset Class", "Blended Value"]
        ).sort_values("Blended Value", ascending=False)
        lt_df["portfolio_pct"] = lt_df["Blended Value"] / lt_df["Blended Value"].sum()

        col1, col2 = st.columns(2)
        with col1:
            fig = px.pie(
                lt_df, values="Blended Value", names="Asset Class",
                hole=0.45, color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            lt_display = lt_df.copy()
            lt_display["Blended Value"] = lt_display["Blended Value"].map("${:,.0f}".format)
            lt_display["portfolio_pct"] = (lt_df["portfolio_pct"] * 100).map("{:.1f}%".format)
            lt_display.columns = ["Asset Class", "Value", "% Portfolio"]
            st.dataframe(lt_display, use_container_width=True, hide_index=True)
    else:
        st.info(
            "No look-through percentages configured yet. "
            "Set the pct_* columns in the Google Sheet Allocations tab to enable blending."
        )
