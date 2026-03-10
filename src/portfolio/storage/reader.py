"""Read Parquet files from ~/data/portfolio/ with a DuckDB query interface.

DuckDB reads Parquet files directly with SQL – no ETL into a database.
The query() method exposes the full data lake for ad-hoc and AI queries.

Example:
    reader = DataReader()
    holdings = reader.current_holdings()
    total = reader.query(
        "SELECT SUM(market_value) FROM read_parquet('~/data/portfolio/canonical/holdings/current.parquet')"
    )
"""

import logging
from pathlib import Path

import duckdb
import pandas as pd

from portfolio import config

log = logging.getLogger(__name__)


class DataReader:
    """Central access point for all portfolio data."""

    def __init__(self, base_path: Path | None = None):
        self.base = base_path or config.DATA_DIR
        self._con = duckdb.connect()  # in-memory, reads Parquet directly

    # ------------------------------------------------------------------
    # Convenience readers
    # ------------------------------------------------------------------

    def current_holdings(self) -> pd.DataFrame:
        return self._read_parquet(config.CANONICAL_DIR / "holdings" / "current.parquet")

    def current_accounts(self) -> pd.DataFrame:
        return self._read_parquet(config.CANONICAL_DIR / "accounts" / "current.parquet")

    def transactions(self) -> pd.DataFrame:
        return self._read_parquet(config.CANONICAL_DIR / "transactions" / "all.parquet")

    def allocation_overrides(self) -> pd.DataFrame:
        return self._read_parquet(config.CANONICAL_DIR / "allocations" / "overrides.parquet")

    def holdings_snapshot(self, date_str: str) -> pd.DataFrame:
        """Load holdings for a specific date (YYYY-MM-DD)."""
        path = config.CANONICAL_DIR / "holdings" / "snapshots" / f"{date_str}.parquet"
        return self._read_parquet(path)

    def holdings_history(self) -> pd.DataFrame:
        """Load all daily snapshots concatenated."""
        snap_dir = config.CANONICAL_DIR / "holdings" / "snapshots"
        if not snap_dir.exists():
            return pd.DataFrame()
        files = sorted(snap_dir.glob("*.parquet"))
        if not files:
            return pd.DataFrame()
        pattern = str(snap_dir / "*.parquet")
        return self._con.execute(
            f"SELECT * FROM read_parquet('{pattern}')"
        ).fetchdf()

    def portfolio_value_history(self, days: int = 365) -> pd.DataFrame:
        """Daily total portfolio value over the last N days."""
        snap_dir = config.CANONICAL_DIR / "holdings" / "snapshots"
        if not snap_dir.exists() or not list(snap_dir.glob("*.parquet")):
            return pd.DataFrame(columns=["date", "total_value"])

        pattern = str(snap_dir / "*.parquet")
        return self._con.execute(f"""
            SELECT date, SUM(market_value) AS total_value
            FROM read_parquet('{pattern}')
            WHERE date >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY date
            ORDER BY date
        """).fetchdf()

    def metric(self, category: str, name: str) -> pd.DataFrame:
        """Load a pre-computed metric file."""
        path = config.METRICS_DIR / category / f"{name}.parquet"
        return self._read_parquet(path)

    # ------------------------------------------------------------------
    # Raw data access
    # ------------------------------------------------------------------

    def raw_schwab_positions(self, date_str: str | None = None) -> pd.DataFrame:
        if date_str:
            path = config.RAW_DIR / "schwab" / "positions" / f"{date_str}.parquet"
            return self._read_parquet(path)
        pattern = str(config.RAW_DIR / "schwab" / "positions" / "*.parquet")
        return self._con.execute(
            f"SELECT * FROM read_parquet('{pattern}') ORDER BY date"
        ).fetchdf()

    # ------------------------------------------------------------------
    # Ad-hoc SQL query interface (for AI queries and exploration)
    # ------------------------------------------------------------------

    def query(self, sql: str) -> pd.DataFrame:
        """Execute arbitrary SQL against the Parquet data lake.

        Paths in SQL should use full absolute paths or the helper variables
        exposed by register_tables().
        """
        return self._con.execute(sql).fetchdf()

    def register_tables(self) -> None:
        """Register named views so SQL can reference tables by short name."""
        mappings = {
            "holdings":     config.CANONICAL_DIR / "holdings" / "current.parquet",
            "accounts":     config.CANONICAL_DIR / "accounts" / "current.parquet",
            "transactions": config.CANONICAL_DIR / "transactions" / "all.parquet",
            "allocations":  config.CANONICAL_DIR / "allocations" / "overrides.parquet",
        }
        for name, path in mappings.items():
            if path.exists():
                self._con.execute(
                    f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{path}')"
                )

    # ------------------------------------------------------------------
    # Data availability check
    # ------------------------------------------------------------------

    def has_data(self) -> bool:
        """Return True if canonical holdings exist."""
        return (config.CANONICAL_DIR / "holdings" / "current.parquet").exists()

    def last_refresh_date(self) -> str | None:
        """Return the date string of the most recent snapshot, or None."""
        snap_dir = config.CANONICAL_DIR / "holdings" / "snapshots"
        if not snap_dir.exists():
            return None
        files = sorted(snap_dir.glob("*.parquet"))
        return files[-1].stem if files else None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_parquet(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            log.debug("Parquet not found: %s", path)
            return pd.DataFrame()
        return pd.read_parquet(path)
