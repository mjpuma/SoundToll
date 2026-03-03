"""
Build shipping network graphs and compute network metrics.
"""

import pandas as pd
import networkx as nx
def build_graph(
    df: pd.DataFrame,
    directed: bool = True,
    aggregate_by_year: bool = True,
    min_passages: int | None = None,
    include_node_attrs: bool = True,
) -> nx.DiGraph | nx.Graph:
    """
    Build a port network from Sound Toll data.

    Parameters
    ----------
    df : pd.DataFrame
        Filtered data with departure, destination, num_passages, Year.
    directed : bool
        If True, use DiGraph (A->B != B->A). Else undirected.
    aggregate_by_year : bool
        If True, aggregate num_passages over all years in df. If False, use year-level.
    min_passages : int | None
        Exclude edges with total passages < min_passages.
    include_node_attrs : bool
        Add lat/lon to nodes if available.

    Returns
    -------
    nx.DiGraph | nx.Graph
        Weighted graph. Edge weight = num_passages (summed).
    """
    if aggregate_by_year:
        agg = df.groupby(["departure", "destination"], as_index=False)["num_passages"].sum()
    else:
        agg = (
            df.groupby(["departure", "destination", "Year"], as_index=False)["num_passages"]
            .sum()
            .groupby(["departure", "destination"], as_index=False)["num_passages"]
            .sum()
        )

    if min_passages is not None:
        agg = agg[agg["num_passages"] >= min_passages]

    G = nx.DiGraph() if directed else nx.Graph()

    for _, row in agg.iterrows():
        G.add_edge(
            row["departure"],
            row["destination"],
            weight=float(row["num_passages"]),
        )

    if include_node_attrs and "departure_latitude" in df.columns:
        # Get unique node positions (departure or destination)
        nodes = set(G.nodes())
        pos_df = (
            df[["departure", "departure_latitude", "departure_longitude"]]
            .drop_duplicates("departure")
            .rename(columns={"departure": "port", "departure_latitude": "lat", "departure_longitude": "lon"})
        )
        dest_df = (
            df[["destination", "destination_latitude", "destination_longitude"]]
            .drop_duplicates("destination")
            .rename(columns={"destination": "port", "destination_latitude": "lat", "destination_longitude": "lon"})
        )
        pos_combined = pd.concat([pos_df, dest_df]).drop_duplicates("port", keep="first")
        for _, r in pos_combined.iterrows():
            if r["port"] in nodes:
                G.nodes[r["port"]]["lat"] = r["lat"]
                G.nodes[r["port"]]["lon"] = r["lon"]

    return G


def compute_metrics(G: nx.DiGraph | nx.Graph) -> dict:
    """
    Compute network-level and node-level metrics.

    Parameters
    ----------
    G : nx.DiGraph | nx.Graph
        Port network from build_graph.

    Returns
    -------
    dict
        - "density": float
        - "n_nodes": int
        - "n_edges": int
        - "total_passages": float (sum of edge weights)
        - "degree_centrality": dict node -> float
        - "betweenness_centrality": dict node -> float
        - "clustering": dict node -> float (for undirected; avg for directed)
    """
    is_directed = G.is_directed()

    total_passages = sum(data.get("weight", 1) for _, _, data in G.edges(data=True))

    degree_cent = nx.degree_centrality(G)
    betweenness = nx.betweenness_centrality(G, weight="weight")

    if is_directed:
        clustering = nx.clustering(nx.Graph(G), weight="weight")
    else:
        clustering = nx.clustering(G, weight="weight")

    n = G.number_of_nodes()
    m = G.number_of_edges()
    max_edges = n * (n - 1) if is_directed else n * (n - 1) / 2
    density = m / max_edges if max_edges > 0 else 0.0

    return {
        "density": density,
        "n_nodes": n,
        "n_edges": m,
        "total_passages": total_passages,
        "degree_centrality": degree_cent,
        "betweenness_centrality": betweenness,
        "clustering": clustering,
    }


def build_graphs_by_period(
    df: pd.DataFrame,
    period_col: str = "Year",
    periods: list[tuple[int, int]] | None = None,
    directed: bool = True,
    min_passages: int | None = None,
) -> dict[str, nx.DiGraph | nx.Graph]:
    """
    Build separate graphs for each time period (e.g. pre/post 1709).

    Parameters
    ----------
    df : pd.DataFrame
        Filtered data.
    period_col : str
        Column for time (Year).
    periods : list[tuple[int, int]] | None
        List of (year_min, year_max). E.g. [(1705, 1708), (1710, 1713)].
        If None, uses single period from min to max year in df.
    directed : bool
        Directed graph.
    min_passages : int | None
        Edge threshold.

    Returns
    -------
    dict[str, nx.DiGraph | nx.Graph]
        Keys like "1705-1708", "1710-1713". Values are graphs.
    """
    if periods is None:
        ymin, ymax = df[period_col].min(), df[period_col].max()
        periods = [(int(ymin), int(ymax))]

    result = {}
    for ymin, ymax in periods:
        sub = df[(df[period_col] >= ymin) & (df[period_col] <= ymax)]
        key = f"{ymin}-{ymax}"
        result[key] = build_graph(sub, directed=directed, min_passages=min_passages)
    return result
