"""
Filter Sound Toll data by year, radii, region, and plague.
"""

import pandas as pd

# Radii column name patterns
RADII_COLUMNS = {
    200: "destination_within200km_ofGdansk",
    500: "destination_within500km_ofGdansk",
    700: "destination_within700km_ofGdansk",
    1300: "destination_within1300km_ofGdansk",
}


def filter_data(
    df: pd.DataFrame,
    year_min: int | None = None,
    year_max: int | None = None,
    radius_km: int | None = None,
    destination_in_radius: bool | None = None,
    departure_region: str | list[str] | None = None,
    destination_region: str | list[str] | None = None,
    destination_plague: bool | None = None,
    min_passages: int | None = None,
) -> pd.DataFrame:
    """
    Filter Sound Toll data.

    Parameters
    ----------
    df : pd.DataFrame
        Loaded Sound Toll data.
    year_min : int | None
        Minimum year (inclusive).
    year_max : int | None
        Maximum year (inclusive).
    radius_km : int | None
        One of 200, 500, 700, 1300. Filter by destination within this radius of Gdansk.
    destination_in_radius : bool | None
        If radius_km is set: True = only destinations within radius, False = only outside.
    departure_region : str | list[str] | None
        Filter by departure_Region (e.g. "West", "East").
    destination_region : str | list[str] | None
        Filter by Destination_Region.
    destination_plague : bool | None
        If True, only rows where destination_plague_10 == 1 (or similar).
    min_passages : int | None
        Exclude routes with num_passages < min_passages.

    Returns
    -------
    pd.DataFrame
        Filtered data.
    """
    out = df.copy()

    if year_min is not None:
        out = out[out["Year"] >= year_min]
    if year_max is not None:
        out = out[out["Year"] <= year_max]

    if radius_km is not None:
        col = RADII_COLUMNS.get(radius_km)
        if col is None:
            raise ValueError(f"radius_km must be one of {list(RADII_COLUMNS)}")
        if col not in out.columns:
            raise ValueError(f"Column {col} not in data. Load with full radii columns.")
        if destination_in_radius is True:
            out = out[out[col] == 1]
        elif destination_in_radius is False:
            out = out[out[col] == 0]

    if departure_region is not None:
        regions = [departure_region] if isinstance(departure_region, str) else departure_region
        out = out[out["departure_Region"].isin(regions)]

    if destination_region is not None:
        regions = [destination_region] if isinstance(destination_region, str) else destination_region
        out = out[out["Destination_Region"].isin(regions)]

    if destination_plague is True:
        if "destination_plague_10" in out.columns:
            out = out[out["destination_plague_10"] == 1]
        else:
            raise ValueError("destination_plague_10 not in data.")

    if min_passages is not None:
        out = out[out["num_passages"] >= min_passages]

    return out.reset_index(drop=True)
