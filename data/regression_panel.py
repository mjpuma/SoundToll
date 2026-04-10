"""
Build regression-ready panel datasets for fixed effects analysis.

Exports port-year, port-year-season, and route-year panels with network stats.
Also exports network-level time series (year and year×season) for SEA-style analyses.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx

from network.analysis import (
    build_graph,
    build_graphs_by_period,
    build_graphs_by_season,
    compute_metrics,
    port_degree_metrics,
)


SEASON_NAMES = {1: "Winter", 2: "Spring", 3: "Summer", 4: "Autumn"}


def _timeseries_metrics_from_graph(g: nx.DiGraph | nx.Graph) -> dict:
    """
    Network-level scalars for one graph (one year or one year×season).

    Means/std/max of node metrics are unweighted over nodes (each port counts once).
    """
    m = compute_metrics(g)
    n = m["n_nodes"]
    m_e = m["n_edges"]
    dc = list(m["degree_centrality"].values())
    bc = list(m["betweenness_centrality"].values())
    cl = list(m["clustering"].values())
    # Undirected view: triangle clustering is often identically 0 for shipping graphs
    # (no three ports with all three pairwise routes); square clustering can still vary.
    Gu = nx.Graph(g) if g.is_directed() else g
    sq = list(nx.square_clustering(Gu).values())
    # Square clustering first: it varies; triangle clustering is often all zeros in this network.
    return {
        "network_n_nodes": n,
        "network_n_edges": m_e,
        "network_total_passages": m["total_passages"],
        "network_density": m["density"],
        "network_reciprocity": m["reciprocity"],
        "mean_degree_centrality": float(np.mean(dc)) if dc else np.nan,
        "mean_betweenness_centrality": float(np.mean(bc)) if bc else np.nan,
        "std_betweenness_centrality": float(np.std(bc, ddof=0)) if bc else np.nan,
        "max_betweenness_centrality": float(np.max(bc)) if bc else np.nan,
        "mean_square_clustering": float(np.mean(sq)) if sq else np.nan,
        "mean_triangle_clustering": float(np.mean(cl)) if cl else np.nan,
        "edges_per_node": (m_e / n) if n > 0 else np.nan,
    }


def build_network_year_timeseries(
    df: pd.DataFrame,
    year_min: int | None = None,
    year_max: int | None = None,
    min_passages: int = 5,
) -> pd.DataFrame:
    """
    One row per calendar year: global network statistics (for SEA / time-series work).

    Graphs are directed; each year's graph includes only rows with Year in that year.
    """
    if year_min is not None:
        df = df[df["Year"] >= year_min]
    if year_max is not None:
        df = df[df["Year"] <= year_max]

    if df.empty:
        return pd.DataFrame()

    year_min_actual = int(df["Year"].min())
    year_max_actual = int(df["Year"].max())
    periods = [(y, y) for y in range(year_min_actual, year_max_actual + 1)]
    graphs = build_graphs_by_period(
        df, period_col="Year", periods=periods, directed=True, min_passages=min_passages
    )

    rows = []
    for key in sorted(graphs.keys(), key=lambda k: int(k.split("-")[0])):
        year = int(key.split("-")[0])
        g = graphs[key]
        row = {"year": year, **_timeseries_metrics_from_graph(g)}
        rows.append(row)
    return pd.DataFrame(rows)


def build_network_year_season_timeseries(
    df: pd.DataFrame,
    year_min: int | None = None,
    year_max: int | None = None,
    min_passages: int = 1,
) -> pd.DataFrame:
    """
    One row per (year, season): same columns as build_network_year_timeseries plus season keys.
    """
    df = df.dropna(subset=["Year", "Season_Num"])
    if year_min is not None:
        df = df[df["Year"] >= year_min]
    if year_max is not None:
        df = df[df["Year"] <= year_max]

    graphs = build_graphs_by_season(
        df, min_passages=min_passages, year_min=year_min, year_max=year_max
    )

    rows = []
    for key in sorted(
        graphs.keys(),
        key=lambda k: (int(k.split("-")[0]), int(k.split("-")[1].replace("S", ""))),
    ):
        year = int(key.split("-")[0])
        season = int(key.split("-")[1].replace("S", ""))
        g = graphs[key]
        row = {
            "year": year,
            "season": season,
            "season_name": SEASON_NAMES.get(season, f"S{season}"),
            **_timeseries_metrics_from_graph(g),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def export_sea_network_timeseries_csvs(
    df: pd.DataFrame,
    output_dir: str | Path,
    year_min: int | None = None,
    year_max: int | None = None,
    min_passages_year: int = 5,
    min_passages_season: int = 1,
) -> tuple[Path, Path]:
    """
    Write all-goods-aggregate time series CSVs under output_dir (not commodity-disaggregated).

    Filenames: network_timeseries_year_all_goods.csv, network_timeseries_year_season_all_goods.csv

    output_dir is created if missing (e.g. outputs/sea).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts_y = build_network_year_timeseries(
        df, year_min=year_min, year_max=year_max, min_passages=min_passages_year
    )
    ts_ys = build_network_year_season_timeseries(
        df, year_min=year_min, year_max=year_max, min_passages=min_passages_season
    )

    path_y = output_dir / "network_timeseries_year_all_goods.csv"
    path_ys = output_dir / "network_timeseries_year_season_all_goods.csv"
    ts_y.to_csv(path_y, index=False)
    ts_ys.to_csv(path_ys, index=False)
    return path_y, path_ys


def build_port_year_panel(
    df: pd.DataFrame,
    year_min: int | None = None,
    year_max: int | None = None,
    min_passages: int = 5,
) -> pd.DataFrame:
    """
    Port-year panel: one row per (port, year) with network stats.

    Columns: port, year, throughput, in_degree, out_degree, degree_centrality,
    betweenness_centrality, clustering, network_density, network_reciprocity,
    network_total_passages, network_n_nodes, network_n_edges.
    """
    if year_min is not None:
        df = df[df["Year"] >= year_min]
    if year_max is not None:
        df = df[df["Year"] <= year_max]

    year_min_actual = int(df["Year"].min())
    year_max_actual = int(df["Year"].max())
    periods = [(y, y) for y in range(year_min_actual, year_max_actual + 1)]
    graphs = build_graphs_by_period(
        df, period_col="Year", periods=periods, directed=True, min_passages=min_passages
    )

    rows = []
    for key, g in graphs.items():
        year = int(key.split("-")[0])
        m = compute_metrics(g)
        deg = port_degree_metrics(g)
        for port in g.nodes():
            rows.append({
                "port": port,
                "year": year,
                "throughput": deg["throughput"][port],
                "in_degree": deg["in_degree"][port],
                "out_degree": deg["out_degree"][port],
                "degree_centrality": m["degree_centrality"].get(port, np.nan),
                "betweenness_centrality": m["betweenness_centrality"].get(port, np.nan),
                "network_density": m["density"],
                "network_reciprocity": m["reciprocity"],
                "network_total_passages": m["total_passages"],
                "network_n_nodes": m["n_nodes"],
                "network_n_edges": m["n_edges"],
            })
    return pd.DataFrame(rows)


def build_port_year_season_panel(
    df: pd.DataFrame,
    year_min: int | None = None,
    year_max: int | None = None,
    min_passages: int = 1,
) -> pd.DataFrame:
    """
    Port-year-season panel: one row per (port, year, season).

    Same columns as port-year plus: season, season_name.
    """
    df = df.dropna(subset=["Year", "Season_Num"])
    if year_min is not None:
        df = df[df["Year"] >= year_min]
    if year_max is not None:
        df = df[df["Year"] <= year_max]

    graphs = build_graphs_by_season(
        df, min_passages=min_passages, year_min=year_min, year_max=year_max
    )

    rows = []
    for key, g in graphs.items():
        year, season = int(key.split("-")[0]), int(key.split("-")[1].replace("S", ""))
        m = compute_metrics(g)
        deg = port_degree_metrics(g)
        for port in g.nodes():
            rows.append({
                "port": port,
                "year": year,
                "season": season,
                "season_name": SEASON_NAMES.get(season, f"S{season}"),
                "throughput": deg["throughput"][port],
                "in_degree": deg["in_degree"][port],
                "out_degree": deg["out_degree"][port],
                "degree_centrality": m["degree_centrality"].get(port, np.nan),
                "betweenness_centrality": m["betweenness_centrality"].get(port, np.nan),
                "network_density": m["density"],
                "network_reciprocity": m["reciprocity"],
                "network_total_passages": m["total_passages"],
                "network_n_nodes": m["n_nodes"],
                "network_n_edges": m["n_edges"],
            })
    return pd.DataFrame(rows)


def build_route_year_panel(
    df: pd.DataFrame,
    year_min: int | None = None,
    year_max: int | None = None,
    min_passages: int = 1,
) -> pd.DataFrame:
    """
    Route-year panel: one row per (departure, destination, year).

    Columns: departure, destination, year, route_passages, origin_degree_centrality,
    destination_degree_centrality, origin_betweenness, destination_betweenness,
    origin_throughput, destination_throughput, network_density, network_reciprocity.
    """
    if year_min is not None:
        df = df[df["Year"] >= year_min]
    if year_max is not None:
        df = df[df["Year"] <= year_max]

    year_min_actual = int(df["Year"].min())
    year_max_actual = int(df["Year"].max())
    periods = [(y, y) for y in range(year_min_actual, year_max_actual + 1)]
    graphs = build_graphs_by_period(
        df, period_col="Year", periods=periods, directed=True, min_passages=min_passages
    )

    rows = []
    for key, g in graphs.items():
        year = int(key.split("-")[0])
        m = compute_metrics(g)
        deg = port_degree_metrics(g)
        rev_edges = {(v, u) for u, v in g.edges()}
        for u, v, data in g.edges(data=True):
            w = data.get("weight", 1)
            has_reverse = (v, u) in rev_edges
            rows.append({
                "departure": u,
                "destination": v,
                "year": year,
                "route_passages": w,
                "route_reciprocal": 1 if has_reverse else 0,
                "origin_degree_centrality": m["degree_centrality"].get(u, np.nan),
                "destination_degree_centrality": m["degree_centrality"].get(v, np.nan),
                "origin_betweenness": m["betweenness_centrality"].get(u, np.nan),
                "destination_betweenness": m["betweenness_centrality"].get(v, np.nan),
                "origin_throughput": deg["throughput"].get(u, 0),
                "destination_throughput": deg["throughput"].get(v, 0),
                "network_density": m["density"],
                "network_reciprocity": m["reciprocity"],
            })
    return pd.DataFrame(rows)


def build_network_year_season_summary(
    df: pd.DataFrame,
    year_min: int | None = None,
    year_max: int | None = None,
    min_passages: int = 1,
) -> pd.DataFrame:
    """
    Network-level summary by year×season (same table as build_network_year_season_timeseries).

    Superset of the old density/reciprocity columns; regression plots use a subset of columns.
    """
    return build_network_year_season_timeseries(
        df, year_min=year_min, year_max=year_max, min_passages=min_passages
    )
