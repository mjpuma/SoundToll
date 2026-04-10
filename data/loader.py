"""
Load Sound Toll Registers CSV with network-relevant columns.
Uses usecols to reduce memory for large files (~300+ MB).
"""

import pandas as pd
from pathlib import Path

# Extra columns for commodity analysis
CARGO_COLUMNS = ["cargo_ids", "ce_ids"]

# Network-relevant columns only (reduces memory)
NETWORK_COLUMNS = [
    "departure",
    "destination",
    "departure_latitude",
    "departure_longitude",
    "destination_latitude",
    "destination_longitude",
    "Year",
    "Season_Num",
    "route",
    "num_passages",
    "departure_Region",
    "Destination_Region",
    "departure_distance_km",
    "departure_within200km_ofGdansk",
    "departure_within500km_ofGdansk",
    "departure_within700km_ofGdansk",
    "departure_within1300km_ofGdansk",
    "destination_distance_km",
    "destination_within200km_ofGdansk",
    "destination_within500km_ofGdansk",
    "destination_within700km_ofGdansk",
    "destination_within1300km_ofGdansk",
    "departure_plague_10",
    "destination_plague_10",
    "departure_plague_25",
    "destination_plague_25",
    "departure_plague_50",
    "destination_plague_50",
    "passage_distance",
]


def load_soundtoll(
    path: str | Path,
    usecols: list[str] | None = None,
    chunksize: int | None = None,
) -> pd.DataFrame:
    """
    Load Sound Toll Registers CSV.

    Parameters
    ----------
    path : str | Path
        Path to 2602_soundtoll_with_radii.csv
    usecols : list[str] | None
        Columns to load. Default: NETWORK_COLUMNS. Use None to load all.
    chunksize : int | None
        If set, read in chunks and concatenate (for very large files).

    Returns
    -------
    pd.DataFrame
        Loaded data.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    cols = usecols if usecols is not None else NETWORK_COLUMNS

    if chunksize is not None:
        chunks = []
        for chunk in pd.read_csv(path, usecols=cols, chunksize=chunksize):
            chunks.append(chunk)
        return pd.concat(chunks, ignore_index=True)

    return pd.read_csv(path, usecols=cols)


def load_soundtoll_with_cargo(
    path: str | Path,
    base_columns: list[str] | None = None,
    usecols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Load Sound Toll CSV with cargo_ids (and ce_ids) for commodity analysis.

    Uses NETWORK_COLUMNS + CARGO_COLUMNS by default.
    """
    base = base_columns or NETWORK_COLUMNS
    extra = [c for c in CARGO_COLUMNS if c not in base]
    cols = base + extra if usecols is None else usecols
    return pd.read_csv(path, usecols=cols)
