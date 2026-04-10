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


def build_graph_by_commodity(
    df: pd.DataFrame,
    commodity: str,
    directed: bool = True,
    aggregate_by_year: bool = True,
    min_passages: int | None = None,
    include_node_attrs: bool = True,
) -> nx.DiGraph | nx.Graph:
    """
    Build port network for a single commodity.

    Filters df by commodity column, then calls build_graph.

    Parameters
    ----------
    df : pd.DataFrame
        Data with commodity column (from expand_passages_to_commodities).
    commodity : str
        Commodity name to filter.
    directed, aggregate_by_year, min_passages, include_node_attrs
        Passed to build_graph.

    Returns
    -------
    nx.DiGraph | nx.Graph
        Port network for this commodity.
    """
    if "commodity" not in df.columns:
        raise ValueError("DataFrame must have 'commodity' column")
    sub = df[df["commodity"] == commodity]
    return build_graph(
        sub,
        directed=directed,
        aggregate_by_year=aggregate_by_year,
        min_passages=min_passages,
        include_node_attrs=include_node_attrs,
    )


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

    reciprocity = nx.reciprocity(G) if is_directed and m > 0 else 0.0

    return {
        "density": density,
        "n_nodes": n,
        "n_edges": m,
        "total_passages": total_passages,
        "degree_centrality": degree_cent,
        "betweenness_centrality": betweenness,
        "clustering": clustering,
        "reciprocity": reciprocity,
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


def build_graphs_by_season(
    df: pd.DataFrame,
    year_col: str = "Year",
    season_col: str = "Season_Num",
    directed: bool = True,
    min_passages: int | None = 1,
    year_min: int | None = None,
    year_max: int | None = None,
) -> dict[str, nx.DiGraph]:
    """
    Build separate graphs for each (year, season) period.

    Parameters
    ----------
    df : pd.DataFrame
        Filtered data with Year, Season_Num.
    year_col, season_col : str
        Column names.
    directed : bool
        Directed graph.
    min_passages : int | None
        Edge threshold. Use 1 or 0 for sparse seasonal data.
    year_min, year_max : int | None
        Optional year range to limit output.

    Returns
    -------
    dict[str, nx.DiGraph]
        Keys like "1700-S1", "1700-S2", ... (S1=season 1, etc.). Values are graphs.
    """
    if year_min is not None:
        df = df[df[year_col] >= year_min]
    if year_max is not None:
        df = df[df[year_col] <= year_max]

    result = {}
    for (year, season), sub in df.groupby([year_col, season_col]):
        if sub["num_passages"].sum() == 0:
            continue
        key = f"{int(year)}-S{int(season)}"
        result[key] = build_graph(sub, directed=directed, min_passages=min_passages)
    return result


def build_backbone_graph(
    graphs: dict[str, nx.DiGraph | nx.Graph],
    min_years_present: float = 0.5,
    directed: bool = True,
) -> nx.DiGraph | nx.Graph:
    """
    Build backbone network: edges that appear in ≥ min_years_present fraction of years.

    Parameters
    ----------
    graphs : dict
        Year-period label -> graph (e.g. from build_graphs_by_period).
    min_years_present : float
        Fraction of years an edge must appear in (0.5 = 50%).
    directed : bool
        Match input graph type.

    Returns
    -------
    nx.DiGraph | nx.Graph
        Backbone graph with persistent edges. Edge weight = sum of passages across years.
    """
    non_empty = [g for g in graphs.values() if g.number_of_edges() > 0]
    n_years = len(non_empty) if non_empty else 0
    threshold = max(1, int(n_years * min_years_present))

    edge_counts: dict[tuple, int] = {}
    edge_weights: dict[tuple, float] = {}
    for g in graphs.values():
        for u, v, data in g.edges(data=True):
            key = (u, v)
            edge_counts[key] = edge_counts.get(key, 0) + 1
            edge_weights[key] = edge_weights.get(key, 0) + data.get("weight", 1)

    G = nx.DiGraph() if directed else nx.Graph()
    for (u, v), count in edge_counts.items():
        if count >= threshold:
            G.add_edge(u, v, weight=edge_weights[(u, v)])

    # Copy node attrs (lat, lon) from graphs (some nodes may only appear in later years)
    if non_empty:
        for n in G.nodes():
            for g in non_empty:
                if n in g.nodes() and "lat" in g.nodes[n]:
                    G.nodes[n].update(g.nodes[n])
                    break

    return G


def port_degree_metrics(G: nx.DiGraph) -> dict[str, dict[str, float]]:
    """
    Compute in_degree, out_degree, throughput per port (weighted by passages).

    Returns
    -------
    dict
        {"in_degree": {port: float}, "out_degree": {...}, "throughput": {...}}
    """
    in_d = {n: 0.0 for n in G.nodes()}
    out_d = {n: 0.0 for n in G.nodes()}
    for u, v, data in G.edges(data=True):
        w = data.get("weight", 1)
        out_d[u] += w
        in_d[v] += w
    throughput = {n: in_d[n] + out_d[n] for n in G.nodes()}
    return {"in_degree": in_d, "out_degree": out_d, "throughput": throughput}
