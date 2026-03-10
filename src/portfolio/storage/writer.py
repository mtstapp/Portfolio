"""Write DataFrames to date-stamped Parquet files in ~/data/portfolio/."""

import logging
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from portfolio import config

log = logging.getLogger(__name__)


def _parquet_path(sub_dir: Path, name: str, as_of: date | None = None) -> Path:
    """Build a path like ~/data/portfolio/<sub_dir>/<name>/<YYYY-MM-DD>.parquet
    or ~/data/portfolio/<sub_dir>/<name>.parquet when as_of is None.
    """
    if as_of:
        return sub_dir / name / f"{as_of.isoformat()}.parquet"
    return sub_dir / f"{name}.parquet"


def write_raw(df: pd.DataFrame, source: str, data_type: str,
              as_of: date | None = None) -> Path:
    """Write a raw DataFrame to ~/data/portfolio/raw/<source>/<data_type>/<date>.parquet."""
    if as_of is None:
        as_of = date.today()
    path = config.RAW_DIR / source / data_type / f"{as_of.isoformat()}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(df, path)
    return path


def write_canonical(df: pd.DataFrame, name: str,
                    as_of: date | None = None,
                    snapshot: bool = False) -> Path:
    """Write to canonical layer.

    If snapshot=True, also writes a dated snapshot alongside current.parquet.
    """
    base = config.CANONICAL_DIR
    current_path = base / name / "current.parquet"
    current_path.parent.mkdir(parents=True, exist_ok=True)
    _write(df, current_path)

    if snapshot and as_of:
        snap_path = base / name / "snapshots" / f"{as_of.isoformat()}.parquet"
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        _write(df, snap_path)
        return snap_path

    return current_path


def write_metrics(df: pd.DataFrame, category: str, name: str) -> Path:
    """Write to metrics layer: ~/data/portfolio/metrics/<category>/<name>.parquet."""
    path = config.METRICS_DIR / category / f"{name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(df, path)
    return path


def _write(df: pd.DataFrame, path: Path) -> None:
    """Write DataFrame to Parquet with snappy compression."""
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, path, compression="snappy")
    log.debug("Wrote %d rows to %s", len(df), path)


def append_parquet(df: pd.DataFrame, path: Path) -> None:
    """Append rows to an existing Parquet file (reads, concatenates, rewrites)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_parquet(path)
        df = pd.concat([existing, df], ignore_index=True)
    _write(df, path)
