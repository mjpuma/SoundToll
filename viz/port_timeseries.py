"""
Port importance over time: multipanel plot tracking key ports across metrics.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import networkx as nx


def _port_throughput(G: nx.DiGraph, port: str) -> float:
    """Total passages through port (in + out)."""
    total = 0.0
    for u, v, data in G.edges(data=True):
        w = data.get("weight", 1)
        if u == port or v == port:
            total += w
    return total


def _port_in_out_degree(G: nx.DiGraph, port: str) -> tuple[float, float]:
    """Weighted in-degree and out-degree (passages)."""
    in_deg, out_deg = 0.0, 0.0
    for u, v, data in G.edges(data=True):
        w = data.get("weight", 1)
        if v == port:
            in_deg += w
        if u == port:
            out_deg += w
    return in_deg, out_deg


def select_key_ports(
    graphs: dict[str, nx.DiGraph],
    top_n: int = 10,
    metric: str = "throughput",
    max_ports: int | None = 12,
    min_years_in_top: int | None = None,
) -> list[str]:
    """
    Select ports that were in top N by metric at some point during the period.

    Parameters
    ----------
    graphs : dict
        Year label -> graph (e.g. "1700-1700", "1701-1701", ...).
    top_n : int
        Top N ports per year to consider.
    metric : str
        "throughput", "degree_centrality", or "betweenness_centrality".
    max_ports : int | None
        If set, cap the result to this many ports. When the union exceeds this,
        ranks by mean throughput across years and keeps top max_ports.
    min_years_in_top : int | None
        If set, require port to be in top N in at least this many years.
        Eliminates sporadic "one-hit wonder" ports.

    Returns
    -------
    list[str]
        Sorted list of key port names.
    """
    from network.analysis import compute_metrics

    key_ports = set()
    port_year_scores: dict[str, list[float]] = {}  # for ranking when capping

    for g in graphs.values():
        if g.number_of_nodes() == 0:
            continue
        m = compute_metrics(g)
        if metric == "throughput":
            passages = {n: _port_throughput(g, n) for n in g.nodes()}
            top = sorted(passages.items(), key=lambda x: -x[1])[:top_n]
        elif metric == "degree_centrality":
            top = sorted(m["degree_centrality"].items(), key=lambda x: -x[1])[:top_n]
        elif metric == "betweenness_centrality":
            top = sorted(m["betweenness_centrality"].items(), key=lambda x: -x[1])[:top_n]
        else:
            raise ValueError(f"Unknown metric: {metric}")
        for port, score in top:
            key_ports.add(port)
            if port not in port_year_scores:
                port_year_scores[port] = []
            port_year_scores[port].append(score)

    # Optional: require minimum years in top N
    if min_years_in_top is not None:
        key_ports = {p for p in key_ports if len(port_year_scores[p]) >= min_years_in_top}

    # Optional: cap at max_ports by mean throughput (or mean of chosen metric)
    if max_ports is not None and len(key_ports) > max_ports:
        # Rank by mean score (throughput-like: higher = more important)
        port_means = {
            p: np.nanmean(port_year_scores[p]) if port_year_scores[p] else 0
            for p in key_ports
        }
        ranked = sorted(port_means.items(), key=lambda x: -x[1])[:max_ports]
        key_ports = [p for p, _ in ranked]

    return sorted(key_ports)


def build_port_timeseries(
    graphs: dict[str, nx.DiGraph],
    ports: list[str],
) -> pd.DataFrame:
    """
    Build time series of port metrics across years.

    Parameters
    ----------
    graphs : dict
        Year label -> graph. Keys should sort chronologically (e.g. "1700-1700", ...).
    ports : list[str]
        Ports to track.

    Returns
    -------
    pd.DataFrame
        Columns: year, port, in_degree, out_degree, throughput, degree_centrality,
        betweenness_centrality. Rows for each (year, port) with data.
    """
    from network.analysis import compute_metrics

    rows = []
    sorted_labels = sorted(graphs.keys(), key=lambda x: int(x.split("-")[0]))
    for label in sorted_labels:
        g = graphs[label]
        year = int(label.split("-")[0])
        m = compute_metrics(g)
        deg_cent = m["degree_centrality"]
        bet_cent = m["betweenness_centrality"]
        for port in ports:
            if port not in g.nodes():
                rows.append({
                    "year": year,
                    "port": port,
                    "in_degree": np.nan,
                    "out_degree": np.nan,
                    "throughput": np.nan,
                    "degree_centrality": np.nan,
                    "betweenness_centrality": np.nan,
                })
                continue
            in_d, out_d = _port_in_out_degree(g, port)
            rows.append({
                "year": year,
                "port": port,
                "in_degree": in_d,
                "out_degree": out_d,
                "throughput": in_d + out_d,
                "degree_centrality": deg_cent.get(port, np.nan),
                "betweenness_centrality": bet_cent.get(port, np.nan),
            })
    return pd.DataFrame(rows)


def plot_port_timeseries(
    ts_df: pd.DataFrame,
    output_dir: str | None = None,
    base_name: str = "port_timeseries",
    fig_width: float = 24,
    height_per_row: float = 5,
    max_rows_per_figure: int = 3,
) -> None:
    """
    Multiple figures: key port metrics over time.

    One plot per row, max 3 rows per figure. Splits across multiple figures.
    Panels: In-degree, Out-degree, Throughput, Degree centrality, Betweenness centrality.
    """
    from pathlib import Path

    ports = ts_df["port"].unique().tolist()
    n_ports = len(ports)

    # Distinct colors for ports
    if n_ports <= 10:
        cmap = plt.cm.tab10
        colors = [cmap(i / 10) for i in range(n_ports)]
    else:
        cmap = plt.cm.tab20
        colors = [cmap(i / min(n_ports, 20)) for i in range(n_ports)]
    port_color = {p: colors[i] for i, p in enumerate(ports)}

    panels = [
        ("in_degree", "In-degree (passages)", "Passages in"),
        ("out_degree", "Out-degree (passages)", "Passages out"),
        ("throughput", "Throughput (total passages)", "Passages"),
        ("degree_centrality", "Degree centrality", "Centrality"),
        ("betweenness_centrality", "Betweenness centrality", "Centrality"),
    ]

    # Split into figures: max 3 rows each
    figure_batches = []
    for i in range(0, len(panels), max_rows_per_figure):
        batch = panels[i : i + max_rows_per_figure]
        figure_batches.append(batch)

    def _plot_one(ax, col, title, ylabel):
        for port in ports:
            sub = ts_df[ts_df["port"] == port].sort_values("year")
            if sub[col].notna().any():
                ax.plot(
                    sub["year"],
                    sub[col],
                    label=port,
                    color=port_color[port],
                    linewidth=1.5,
                    alpha=0.9,
                )
        ax.set_xlabel("Year")
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(loc="upper right", fontsize=9, ncol=1)

    for batch_idx, batch in enumerate(figure_batches):
        n_rows = len(batch)
        fig, axes = plt.subplots(
            n_rows,
            1,
            figsize=(fig_width, height_per_row * n_rows),
            facecolor="white",
            squeeze=False,
        )
        axes = axes.flatten()
        for ax, (col, title, ylabel) in zip(axes, batch):
            _plot_one(ax, col, title, ylabel)

        fig.suptitle(
            "Key Port Importance Over Time (top ports by throughput)",
            fontsize=14,
            fontweight="bold",
            y=1.02,
        )
        plt.tight_layout()

        if output_dir:
            suffix = "_".join(p[0] for p in batch)
            path = Path(output_dir) / f"{base_name}_{suffix}.png"
            plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
            plt.close()
        else:
            plt.show()
