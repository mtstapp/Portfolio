"""Streamlit portfolio dashboard – main entry point.

Run with:
    streamlit run src/portfolio/dashboard/app.py

Pages are defined in dashboard/pages/ and loaded automatically by Streamlit's
multipage app convention (files prefixed with a number).
"""

import subprocess
import sys
from datetime import timezone
from pathlib import Path

# Resolve the portfolio CLI to the same venv as the running Streamlit process,
# so subprocess.run() works regardless of the shell's PATH.
_PORTFOLIO = str(Path(sys.executable).parent / "portfolio")

import streamlit as st

from portfolio.auth import schwab_oauth
from portfolio.storage.reader import DataReader

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
# Shared data reader (cached for the session)
# ---------------------------------------------------------------------------

@st.cache_resource
def get_reader() -> DataReader:
    return DataReader()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.title("📈 Portfolio")
        st.divider()

        # Auth status
        days = schwab_oauth.token_days_remaining()
        if days is None:
            st.error("⚠️ Not authenticated")
        elif days < 2:
            st.warning(f"⚠️ Token expires in {days:.1f} days")
        else:
            st.success(f"✓ Schwab connected ({days:.0f}d)")

        # Re-auth button
        if st.button("🔐 Re-authenticate with Schwab", use_container_width=True):
            st.info("Starting auth server… A browser tab will open.\n\n"
                    "If you see a security warning, click **Advanced → Proceed**.")
            with st.spinner("Waiting for Schwab authentication…"):
                try:
                    result = subprocess.run(
                        [_PORTFOLIO, "auth", "--no-browser"],
                        capture_output=True, text=True, timeout=180,
                    )
                    if result.returncode == 0:
                        st.success("Authentication successful!")
                        st.rerun()
                    else:
                        st.error(f"Auth failed:\n{result.stderr}")
                except subprocess.TimeoutExpired:
                    st.error("Authentication timed out (3 min). Please try again.")

        st.divider()

        # Last refresh
        reader = get_reader()
        last = reader.last_refresh_date()
        if last:
            st.caption(f"Last refresh: **{last}**")
        else:
            st.caption("No data yet – run `portfolio refresh`")

        # Manual refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            with st.spinner("Refreshing Schwab data…"):
                result = subprocess.run(
                    [_PORTFOLIO, "refresh"],
                    capture_output=True, text=True, timeout=600,
                )
            if result.returncode == 0:
                st.success("Data refreshed!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"Refresh failed:\n{result.stderr[-500:]}")

        st.divider()
        st.caption("Portfolio Dashboard v0.1")


# ---------------------------------------------------------------------------
# Main page content (Overview)
# ---------------------------------------------------------------------------

def render_overview() -> None:
    st.title("Portfolio Overview")

    reader = get_reader()

    if not reader.has_data():
        st.info("No portfolio data found.")
        st.markdown("""
        **To get started:**
        1. Run `portfolio setup` to store your Schwab credentials in Keychain
        2. Run `portfolio auth` to authenticate with Schwab
        3. Run `portfolio refresh` to pull your portfolio data
        4. Reload this page
        """)
        return

    holdings = reader.current_holdings()
    accounts = reader.current_accounts()

    if holdings.empty:
        st.warning("Holdings data is empty. Try running `portfolio refresh`.")
        return

    # --- KPI Cards ---
    total_value = holdings["market_value"].sum()
    total_cost = holdings["cost_basis"].sum()
    total_gain = total_value - total_cost
    total_gain_pct = total_gain / total_cost * 100 if total_cost else 0
    projected_income = holdings["div_annual_total"].sum() if "div_annual_total" in holdings.columns else 0
    portfolio_beta = holdings["weighted_beta"].sum() if "weighted_beta" in holdings.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Portfolio Value", f"${total_value:,.0f}")
    with col2:
        st.metric("Total Gain / Loss",
                  f"${total_gain:,.0f}",
                  delta=f"{total_gain_pct:.1f}%")
    with col3:
        st.metric("Projected Annual Income", f"${projected_income:,.0f}")
    with col4:
        st.metric("Portfolio Beta", f"{portfolio_beta:.2f}")

    st.divider()

    col_left, col_right = st.columns([1, 1])

    # --- Account breakdown ---
    with col_left:
        st.subheader("By Account")
        if not accounts.empty and "account_name" in accounts.columns:
            import plotly.express as px
            fig = px.bar(
                accounts.sort_values("total_value", ascending=True),
                x="total_value",
                y="account_name",
                orientation="h",
                labels={"total_value": "Value ($)", "account_name": "Account"},
                text_auto="$.3s",
            )
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Aggregate from holdings if accounts df not available
            by_acct = holdings.groupby("account_name")["market_value"].sum().reset_index()
            import plotly.express as px
            fig = px.bar(
                by_acct.sort_values("market_value", ascending=True),
                x="market_value",
                y="account_name",
                orientation="h",
                labels={"market_value": "Value ($)", "account_name": "Account"},
                text_auto="$.3s",
            )
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

    # --- Asset type breakdown ---
    with col_right:
        st.subheader("By Security Type")
        if "security_type" in holdings.columns:
            import plotly.express as px
            by_type = holdings.groupby("security_type")["market_value"].sum().reset_index()
            fig = px.pie(by_type, values="market_value", names="security_type",
                         hole=0.4)
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Top 10 Holdings ---
    st.subheader("Top 10 Holdings")
    top10 = (
        holdings[holdings["symbol"] != "cashBalance"]
        .nlargest(10, "market_value")
        [["symbol", "description", "security_type", "market_value",
          "gain_loss", "portfolio_pct"]]
        .copy()
    )
    top10["market_value"] = top10["market_value"].map("${:,.0f}".format)
    top10["gain_loss"] = top10["gain_loss"].map("${:,.0f}".format)
    top10["portfolio_pct"] = (top10["portfolio_pct"] * 100).map("{:.1f}%".format)
    top10.columns = ["Symbol", "Description", "Type", "Value", "Gain/Loss", "% Portfolio"]
    st.dataframe(top10, use_container_width=True, hide_index=True)

    # --- Portfolio value history (if available) ---
    history = reader.portfolio_value_history(days=365)
    if not history.empty and len(history) > 1:
        st.divider()
        st.subheader("Portfolio Value History")
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=history["date"], y=history["total_value"],
            mode="lines", fill="tozeroy",
            line=dict(color="#00a3e0", width=2),
        ))
        fig.update_layout(
            yaxis_tickprefix="$", yaxis_tickformat=",.0f",
            height=300, margin=dict(l=0, r=0, t=0, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

render_sidebar()
render_overview()
