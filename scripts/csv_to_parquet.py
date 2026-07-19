"""
Convert CSV files in DATA_ROOT/raw/ to Parquet (same directory, .parquet suffix).
Runs conversions in parallel. Skips files with an up-to-date .parquet already present.

Usage:
    norm_env/bin/python scripts/csv_to_parquet.py [--force]
"""

import os
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd


def convert(csv_path: Path, force: bool = False) -> str:
    out = csv_path.with_suffix(".parquet")
    if not force and out.exists() and out.stat().st_mtime >= csv_path.stat().st_mtime:
        return f"skip    {csv_path.name}  (up to date)"

    df = pd.read_csv(csv_path, on_bad_lines="skip", low_memory=False)
    df.to_parquet(out, index=False)
    mb = out.stat().st_size / 1_048_576
    return f"done    {csv_path.name}  →  {len(df):,} rows  {mb:.0f} MB"


def main() -> None:
    force = "--force" in sys.argv

    data_root = os.environ.get("DATA_ROOT")
    if not data_root:
        try:
            from dotenv import load_dotenv, find_dotenv
            load_dotenv(find_dotenv())
            data_root = os.environ.get("DATA_ROOT")
        except ImportError:
            pass

    if not data_root or not Path(data_root).is_dir():
        sys.exit(f"DATA_ROOT not set or not found: {data_root!r}")

    # Only convert CSVs directly in raw/ (not subdirectories)
    raw = Path(data_root) / "raw"
    csvs = sorted(raw.glob("*.csv"))
    if not csvs:
        sys.exit(f"No CSV files found in {raw}")

    print(f"Converting {len(csvs)} CSV file(s) in {raw}\n")

    with ProcessPoolExecutor() as pool:
        futures = {pool.submit(convert, p, force): p for p in csvs}
        for fut in as_completed(futures):
            try:
                print(" ", fut.result())
            except Exception as e:
                print(f"  ERROR  {futures[fut].name}: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
