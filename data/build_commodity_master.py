#!/usr/bin/env python3
"""
Build data/commodity_master.csv: all unique raw commodity strings from cargoes_regs
with frequencies, auto-mapping status, and review columns.

Run from project root: python data/build_commodity_master.py
(or: python -m data.build_commodity_master)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd

from data.cargo_lookup import (
    _build_excel_commodity_map,
    _latin_ascii_normalize,
    _prepare_soort_for_match,
    _regex_standardize_commodity,
    _standardize_one_raw_commodity,
    standard_category_for_label,
)


def _excel_row_exact_match(raw: str, cargo_df: pd.DataFrame) -> str | None:
    """Return Excel translations value if raw matches 'cargo names in dataset' (case-insensitive strip)."""
    raw_col = "cargo names in dataset"
    trans_col = "translations"
    r = str(raw).strip().lower()
    for _, row in cargo_df.iterrows():
        cell = row[raw_col]
        if pd.isna(cell):
            continue
        if str(cell).strip().lower() == r:
            t = row[trans_col]
            if pd.isna(t) or str(t).strip() == "" or str(t).lower() == "nan":
                return None
            return str(t).strip()
    return None


def _classify_and_label(
    raw: str,
    excel_map: dict[str, str],
    cargo_df: pd.DataFrame,
) -> tuple[str, str, str | None]:
    """
    Returns (match_status, standard_label, excel_manual_label_or_none).

    standard_label = best auto mapping (Excel > regex > title-case raw).
    """
    raw_clean = str(raw).strip()
    excel_manual = _excel_row_exact_match(raw_clean, cargo_df)

    standard = _standardize_one_raw_commodity(raw_clean, excel_map)

    raw_clean = str(raw).strip()
    if not raw_clean or raw_clean == "-":
        return "unmatched", "Unknown", excel_manual

    soort = _prepare_soort_for_match(raw_clean)
    if not soort:
        return "unmatched", standard, excel_manual

    in_excel_keys = soort in excel_map or _latin_ascii_normalize(soort).lower() in excel_map
    if in_excel_keys:
        return "excel_exact", standard, excel_manual

    rx = _regex_standardize_commodity(soort)
    if rx is not None:
        status = "regex_matched"
        if _partial_heuristic(raw_clean, standard):
            status = "partial"
        return status, standard, excel_manual

    status = "unmatched"
    if _partial_heuristic(raw_clean, standard):
        status = "partial"
    return status, standard, excel_manual


def _partial_heuristic(raw_clean: str, standard_label: str) -> bool:
    if len(raw_clean) < 4:
        return True
    if any(ch.isdigit() for ch in raw_clean):
        return True
    if "?" in raw_clean:
        return True
    # No translation: fallback title-case equals display
    soort = _prepare_soort_for_match(raw_clean)
    if soort and standard_label.strip().lower() == soort.title().lower():
        return True
    return False


def build_commodity_master(
    cargoes_regs_path: Path,
    mappings_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    df = pd.read_csv(
        cargoes_regs_path,
        sep=";",
        usecols=["commodity"],
        low_memory=False,
        encoding="utf-8",
    )
    s = df["commodity"].astype(str).str.strip()
    vc = s.value_counts()
    total_rows = int(len(df))

    cargo_df = pd.read_excel(mappings_path, sheet_name="Cargo", header=0)
    excel_map = _build_excel_commodity_map(cargo_df)

    rows = []
    cum = 0.0
    for raw_commodity, row_count in vc.items():
        if raw_commodity.lower() == "nan":
            continue
        pct = 100.0 * row_count / total_rows if total_rows else 0.0
        cum += pct
        match_status, standard_label, _ = _classify_and_label(
            raw_commodity, excel_map, cargo_df
        )
        cat = standard_category_for_label(standard_label, match_status)
        rows.append(
            {
                "raw_commodity": raw_commodity,
                "row_count": int(row_count),
                "pct_of_total": round(pct, 6),
                "cumulative_pct": round(cum, 6),
                "standard_label": standard_label,
                "match_status": match_status,
                "standard_category": cat,
                "notes": "",
                "reviewed": "",
            }
        )

    out = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig writes UTF-8 with BOM so Excel (Windows) recognizes encoding on open
    out.to_csv(output_path, index=False, encoding="utf-8-sig")
    return out


def _print_summary(out: pd.DataFrame, total_rows: int) -> None:
    n_unique = len(out)
    print(f"Total unique raw values: {n_unique:,}")
    print(f"Total cargo rows: {total_rows:,}")

    vol = out.groupby("match_status")["row_count"].sum()
    for status in ("excel_exact", "regex_matched", "partial", "unmatched"):
        rc = int(vol.get(status, 0))
        p = 100.0 * rc / total_rows if total_rows else 0.0
        print(f"  {status}: {rc:,} rows ({p:.2f}% of total cargo volume)")

    top_u = out[out["match_status"] == "unmatched"].sort_values("row_count", ascending=False).head(20)
    print("\nTop 20 unmatched by row_count:")
    if top_u.empty:
        print("  (none)")
    else:
        for _, r in top_u.iterrows():
            print(f"  {int(r['row_count']):>8}  {r['raw_commodity']!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build data/commodity_master.csv")
    parser.add_argument(
        "--cargoes",
        type=Path,
        default=Path("data/cargoes_regs.csv"),
        help="Path to cargoes_regs.csv",
    )
    parser.add_argument(
        "--mappings",
        type=Path,
        default=Path("Fixed Port City & Cargo Mappings.xlsx"),
        help="Excel mappings file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/commodity_master.csv"),
        help="Output CSV path",
    )
    args = parser.parse_args()

    df_in = pd.read_csv(
        args.cargoes,
        sep=";",
        usecols=["commodity"],
        low_memory=False,
        encoding="utf-8",
    )
    total_rows = len(df_in)

    out = build_commodity_master(args.cargoes, args.mappings, args.output)
    print(f"\nWrote {args.output} ({len(out):,} rows)\n")
    _print_summary(out, total_rows)


if __name__ == "__main__":
    main()
