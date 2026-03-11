"""Holdings page – full position detail with filters and search."""

import streamlit as st
import pandas as pd
import plotly.express as px

from portfolio.storage.reader import DataReader
from portfolio.dashboard.components import sidebar as _sidebar

st.set_page_config(
    page_title="Holdings – Portfolio",
    page_icon="📋",
    layout="wide",
)

_sidebar.render()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def _load() -> tuple[pd.DataFrame, pd.DataFrame]:
    reader = DataReader()
    return reader.current_holdings(), reader.current_accounts()


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("📋 Holdings")

holdings, accounts = _load()

if holdings.empty:
    st.info("No holdings data found. Run `portfolio refresh` to pull data.")
    st.stop()

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

with st.expander("🔍 Filters", expanded=True):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        all_accounts = sorted(holdings["account_name"].dropna().unique().tolist())
        selected_accounts = st.multiselect(
            "Account",
            options=all_accounts,
            default=all_accounts,
        )

    with col2:
        all_types = sorted(holdings["security_type"].dropna().unique().tolist())
        selected_types = st.multiselect(
            "Security Type",
            options=all_types,
            default=all_types,
        )

    with col3:
        all_sectors = sorted(
            s for s in holdings["sector"].dropna().unique()
            if s not in ("", "Unknown")
        )
        selected_sectors = st.multiselect(
            "Sector",
            options=all_sectors,
            default=all_sectors,
        )

    with col4:
        search = st.text_input("Search symbol / description", "")

# Apply filters
df = holdings.copy()

if selected_accounts:
    df = df[df["account_name"].isin(selected_accounts)]
if selected_types:
    df = df[df["security_type"].isin(selected_types)]
if selected_sectors:
    df = df[df["sector"].isin(selected_sectors)]
if search:
    mask = (
        df["symbol"].str.contains(search, case=False, na=False) |
        df["description"].str.contains(search, case=False, na=False)
    )
    df = df[mask]

# Exclude cash rows from main table (shown separately)
cash_df = df[df["symbol"] == "cashBalance"]
positions_df = df[df["symbol"] != "cashBalance"]

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------

total_value  = df["market_value"].sum()
total_gain   = df["gain_loss"].sum()
total_cost   = df["cost_basis"].sum()
gain_pct     = total_gain / total_cost * 100 if total_cost else 0.0
n_positions  = len(positions_df)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Value",     f"${total_value:,.0f}")
col2.metric("Gain / Loss",     f"${total_gain:,.0f}", f"{gain_pct:+.1f}%")
col3.metric("Positions",       f"{n_positions}")
col4.metric("Accounts",        f"{df['account_id'].nunique()}")

st.divider()

# ---------------------------------------------------------------------------
# Holdings table
# ---------------------------------------------------------------------------

display_cols = [
    "account_name", "symbol", "description", "security_type",
    "quantity", "current_price", "market_value",
    "cost_basis", "gain_loss", "portfolio_pct",
    "sector", "beta", "dividend_yield",
]
available = [c for c in display_cols if c in positions_df.columns]
table_df = positions_df[available].copy()

# Format numeric columns for display
if "portfolio_pct" in table_df.columns:
    table_df["portfolio_pct"] = (table_df["portfolio_pct"] * 100).round(2)
if "dividend_yield" in table_df.columns:
    table_df["dividend_yield"] = (table_df["dividend_yield"] * 100).round(2)

col_rename = {
    "account_name":  "Account",
    "symbol":        "Symbol",
    "description":   "Description",
    "security_type": "Type",
    "quantity":      "Qty",
    "current_price": "Price",
    "market_value":  "Value ($)",
    "cost_basis":    "Cost Basis ($)",
    "gain_loss":     "Gain/Loss ($)",
    "portfolio_pct": "% Portfolio",
    "sector":        "Sector",
    "beta":          "Beta",
    "dividend_yield": "Div Yield (%)",
}
table_df = table_df.rename(columns={k: v for k, v in col_rename.items() if k in table_df.columns})

# Colour helper for gain/loss
def _color_gain(val):
    if isinstance(val, (int, float)):
        color = "green" if val >= 0 else "red"
        return f"color: {color}"
    return ""

styled = (
    table_df.style
    .format({
        "Price":         "${:,.2f}",
        "Value ($)":     "${:,.0f}",
        "Cost Basis ($)":"${:,.0f}",
        "Gain/Loss ($)": "${:,.0f}",
        "% Portfolio":   "{:.2f}%",
        "Qty":           "{:,.4g}",
        "Beta":          "{:.2f}",
        "Div Yield (%)": "{:.2f}%",
    }, na_rep="–")
    .applymap(_color_gain, subset=["Gain/Loss ($)"] if "Gain/Loss ($)" in table_df.columns else [])
)

st.dataframe(styled, use_container_width=True, hide_index=True, height=500)

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

csv_data = table_df.to_csv(index=False).encode()
st.download_button(
    label="⬇️ Download CSV",
    data=csv_data,
    file_name="holdings.csv",
    mime="text/csv",
)

# ---------------------------------------------------------------------------
# Cash positions (separate section)
# ---------------------------------------------------------------------------

if not cash_df.empty:
    st.divider()
    st.subheader("Cash & Sweep Positions")
    cash_total = cash_df["market_value"].sum()
    st.metric("Total Cash", f"${cash_total:,.0f}")

    cash_display = cash_df[["account_name", "market_value"]].copy()
    cash_display.columns = ["Account", "Cash Balance ($)"]
    st.dataframe(
        cash_display.style.format({"Cash Balance ($)": "${:,.0f}"}),
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# Top 10 by market value (chart)
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Top 20 Positions by Value")

top20 = (
    positions_df
    .nlargest(20, "market_value")
    [["symbol", "market_value", "gain_loss", "account_name"]]
    .copy()
)
top20["color"] = top20["gain_loss"].apply(lambda v: "gain" if v >= 0 else "loss")
fig = px.bar(
    top20,
    x="market_value",
    y="symbol",
    orientation="h",
    color="color",
    color_discrete_map={"gain": "#2ecc71", "loss": "#e74c3c"},
    hover_data={"gain_loss": ":.0f", "account_name": True, "color": False},
    labels={"market_value": "Market Value ($)", "symbol": ""},
)
fig.update_layout(
    height=520,
    showlegend=False,
    margin=dict(l=0, r=0, t=0, b=0),
    yaxis={"categoryorder": "total ascending"},
)
fig.update_xaxes(tickprefix="$", tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
