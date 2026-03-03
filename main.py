#!/usr/bin/env python3
"""
Sound Toll Network Analysis - orchestration script.

Loads data, filters by year/radii, builds graphs, computes metrics, and produces visualizations.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd

# Use non-interactive backend for headless/script execution
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data.loader import load_soundtoll
from filters.filter import filter_data
from network.analysis import build_graph, compute_metrics, build_graphs_by_period
from viz.map import plot_map, EXTENT_ZOOMED, EXTENT_WIDE
from viz.network_plot import plot_network
from viz.period_comparison import plot_period_comparison
from viz.port_metrics import build_port_metrics_table, plot_top_ports_comparison


def main():
    # Paths
    base = Path(__file__).resolve().parent
    data_path = base / "2602_soundtoll_with_radii.csv"
    outputs_dir = base / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    if not data_path.exists():
        print(f"Data file not found: {data_path}")
        print("Place 2602_soundtoll_with_radii.csv in the project root.")
        return

    # Load
    print("Loading data...")
    df = load_soundtoll(data_path)
    print(f"  Loaded {len(df):,} rows")

    # Filter: plague window 1700-1720
    df_filtered = filter_data(df, year_min=1700, year_max=1720)
    print(f"  Filtered to {len(df_filtered):,} rows (1700-1720)")

    # Build graph (full period)
    G = build_graph(df_filtered, directed=True, min_passages=5)
    print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # Metrics
    metrics = compute_metrics(G)
    print(f"  Density: {metrics['density']:.4f}")
    print(f"  Total passages: {metrics['total_passages']:,.0f}")

    # Top ports by degree centrality
    deg = metrics["degree_centrality"]
    top_deg = sorted(deg.items(), key=lambda x: x[1], reverse=True)[:5]
    print("  Top 5 by degree centrality:", [p[0] for p in top_deg])

    # Pre vs post 1709
    periods = [(1705, 1708), (1710, 1713)]
    graphs = build_graphs_by_period(df_filtered, periods=periods, directed=True, min_passages=5)

    # Comparison table (apples-to-apples: same scale across periods)
    period_metrics = []
    total_all = sum(compute_metrics(g)["total_passages"] for g in graphs.values())
    for label, g in graphs.items():
        m = compute_metrics(g)
        top_deg = sorted(m["degree_centrality"].items(), key=lambda x: x[1], reverse=True)[:3]
        max_edge = max((g.edges[e].get("weight", 1) for e in g.edges()), default=0)
        avg_between = np.mean(list(m["betweenness_centrality"].values())) if m["betweenness_centrality"] else 0.0
        reciprocity = m.get("reciprocity", 0.0)
        period_metrics.append({
            "period": label,
            "n_nodes": m["n_nodes"],
            "n_edges": m["n_edges"],
            "density": m["density"],
            "total_passages": m["total_passages"],
            "pct_passages": 100 * m["total_passages"] / total_all if total_all else 0,
            "max_route_passages": max_edge,
            "reciprocity": reciprocity,
            "avg_betweenness": avg_between,
            "top_ports": ", ".join(p[0] for p in top_deg),
        })
        print(f"  {label}: {m['n_nodes']} nodes, {m['n_edges']} edges, density={m['density']:.4f}")

    metrics_df = pd.DataFrame(period_metrics)
    metrics_csv = outputs_dir / "period_comparison.csv"
    metrics_df.to_csv(metrics_csv, index=False)
    print(f"  Comparison table saved to {metrics_csv}")

    # Professional multipanel period comparison
    plot_period_comparison(
        period_metrics,
        output_path=str(outputs_dir / "period_comparison.png"),
    )
    print("  Period comparison plot saved to outputs/period_comparison.png")

    # Port-level stats table and bar plots
    port_df = build_port_metrics_table(graphs)
    port_df.to_csv(outputs_dir / "port_network_stats.csv", index=False)
    print(f"  Port stats table saved to outputs/port_network_stats.csv ({len(port_df)} ports)")

    plot_top_ports_comparison(
        port_df,
        graphs,
        top_n=10,
        output_path=str(outputs_dir / "top_ports_comparison.png"),
    )
    print("  Top ports comparison plot saved to outputs/top_ports_comparison.png")

    # Period-specific maps: zoomed-in and zoomed-out (cross-period scale)
    period_graphs = list(graphs.values())
    for label, g in graphs.items():
        plot_map(
            g,
            output_path=str(outputs_dir / f"soundtoll_map_{label}_zoom.png"),
            extent=EXTENT_ZOOMED,
            highlight_ports=["Gdansk"],
            title=f"Sound Toll Shipping Network ({label})",
            scale_from_graphs=period_graphs,
        )
        plot_map(
            g,
            output_path=str(outputs_dir / f"soundtoll_map_{label}_wide.png"),
            extent=EXTENT_WIDE,
            highlight_ports=["Gdansk"],
            title=f"Sound Toll Shipping Network ({label})",
            scale_from_graphs=period_graphs,
        )
    print("  Period-specific maps saved (zoom + wide)")

    # Map (full period): zoomed-in and zoomed-out
    print("Generating maps...")
    plot_map(
        G,
        output_path=str(outputs_dir / "soundtoll_map_zoom.png"),
        extent=EXTENT_ZOOMED,
        highlight_ports=["Gdansk"],
    )
    plot_map(
        G,
        output_path=str(outputs_dir / "soundtoll_map_wide.png"),
        extent=EXTENT_WIDE,
        highlight_ports=["Gdansk"],
    )

    # Network diagram
    print("Generating network diagram...")
    plot_network(
        G,
        output_path=str(outputs_dir / "soundtoll_network.png"),
        layout="geographic",
        highlight_ports=["Gdansk"],
        max_nodes=80,
    )

    print(f"Outputs saved to {outputs_dir}")


if __name__ == "__main__":
    main()
