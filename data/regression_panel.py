"""
Build regression-ready panel datasets for fixed effects analysis.

Exports port-year, port-year-season, and route-year panels with network stats.
"""

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
    Network-level summary by year-season: density, reciprocity, total passages, etc.
    For use as contextual variables or separate analysis.
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
        rows.append({
            "year": year,
            "season": season,
            "season_name": SEASON_NAMES.get(season, f"S{season}"),
            "network_density": m["density"],
            "network_reciprocity": m["reciprocity"],
            "network_total_passages": m["total_passages"],
            "network_n_nodes": m["n_nodes"],
            "network_n_edges": m["n_edges"],
        })
    return pd.DataFrame(rows)
