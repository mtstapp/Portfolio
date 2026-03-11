"""Shared sidebar renderer for all dashboard pages.

Import and call render() at the top of each page file so the sidebar
appears consistently across the multipage app.
"""

import subprocess
import sys
from pathlib import Path

import streamlit as st

from portfolio.auth import schwab_oauth
from portfolio.storage.reader import DataReader

# Resolve the portfolio CLI binary to the same venv as the running process.
_PORTFOLIO = str(Path(sys.executable).parent / "portfolio")


def render() -> None:
    """Render the shared sidebar: auth status, refresh controls, last refresh date."""
    with st.sidebar:
        st.title("📈 Portfolio")
        st.divider()

        # -- Auth status --------------------------------------------------
        days = schwab_oauth.token_days_remaining()
        if days is None:
            st.error("⚠️ Not authenticated")
        elif days < 2:
            st.warning(f"⚠️ Token expires in {days:.1f} days")
        else:
            st.success(f"✓ Schwab connected ({days:.0f}d)")

        if st.button("🔐 Re-authenticate with Schwab", use_container_width=True):
            st.info(
                "Starting auth server… A browser tab will open.\n\n"
                "If you see a security warning, click **Advanced → Proceed**."
            )
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

        # -- Last refresh & manual refresh --------------------------------
        reader = DataReader()
        last = reader.last_refresh_date()
        if last:
            st.caption(f"Last refresh: **{last}**")
        else:
            st.caption("No data yet – run `portfolio refresh`")

        if st.button("🔄 Refresh Data", use_container_width=True):
            with st.spinner("Refreshing portfolio data…"):
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
