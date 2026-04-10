#!/usr/bin/env python3
"""
Export SEA-oriented network time series CSVs only (no maps, no full main.py pipeline).

Writes outputs/sea/network_timeseries_year_all_goods.csv and network_timeseries_year_season_all_goods.csv
(aggregate over all commodities; not per-commodity splits).
Copies NETWORK_METRICS_DEFINITIONS.md into outputs/sea/ when present.

Usage:
  python export_sea_network_timeseries.py
  python export_sea_network_timeseries.py --year-min 1700 --year-max 1750
"""

import argparse
import shutil
from pathlib import Path

from data.loader import load_soundtoll
from data.regression_panel import export_sea_network_timeseries_csvs
from filters.filter import filter_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Export network time series CSVs for SEA")
    parser.add_argument("--year-min", type=int, default=1668, help="Minimum Year (default 1668)")
    parser.add_argument("--year-max", type=int, default=1800, help="Maximum Year (default 1800)")
    parser.add_argument(
        "--min-passages-year",
        type=int,
        default=5,
        help="Min passages per edge for annual graphs (default 5)",
    )
    parser.add_argument(
        "--min-passages-season",
        type=int,
        default=1,
        help="Min passages per edge for year×season graphs (default 1)",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    data_path = base / "2602_soundtoll_with_radii.csv"
    if not data_path.exists():
        print(f"Data file not found: {data_path}")
        return

    print("Loading data...")
    df = load_soundtoll(data_path)
    df = filter_data(df, year_min=args.year_min, year_max=args.year_max)
    print(f"  Rows after filter: {len(df):,} ({args.year_min}-{args.year_max})")

    out_dir = base / "outputs" / "sea"
    sea_y, sea_ys = export_sea_network_timeseries_csvs(
        df,
        out_dir,
        year_min=args.year_min,
        year_max=args.year_max,
        min_passages_year=args.min_passages_year,
        min_passages_season=args.min_passages_season,
    )
    print(f"Wrote:\n  {sea_y}\n  {sea_ys}")

    defs_doc = base / "NETWORK_METRICS_DEFINITIONS.md"
    if defs_doc.exists():
        shutil.copy2(defs_doc, out_dir / defs_doc.name)
        print(f"Copied {defs_doc.name} -> {out_dir}")


if __name__ == "__main__":
    main()
