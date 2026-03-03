#!/usr/bin/env python3
"""
Sound Toll Network Analysis - orchestration script.

Loads data, filters by year/radii, builds graphs, computes metrics, and produces visualizations.
"""

import os
from pathlib import Path

import pandas as pd

# Use non-interactive backend for headless/script execution
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data.loader import load_soundtoll
from filters.filter import filter_data
from network.analysis import build_graph, compute_metrics, build_graphs_by_period
from viz.map import plot_map
from viz.network_plot import plot_network


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
        period_metrics.append({
            "period": label,
            "n_nodes": m["n_nodes"],
            "n_edges": m["n_edges"],
            "density": m["density"],
            "total_passages": m["total_passages"],
            "pct_passages": 100 * m["total_passages"] / total_all if total_all else 0,
            "max_route_passages": max_edge,
            "top_ports": ", ".join(p[0] for p in top_deg),
        })
        print(f"  {label}: {m['n_nodes']} nodes, {m['n_edges']} edges, density={m['density']:.4f}")

    metrics_df = pd.DataFrame(period_metrics)
    metrics_csv = outputs_dir / "period_comparison.csv"
    metrics_df.to_csv(metrics_csv, index=False)
    print(f"  Comparison table saved to {metrics_csv}")

    # Period comparison plot
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    periods_labels = [p["period"] for p in period_metrics]
    x = range(len(periods_labels))

    axes[0, 0].bar(x, [p["n_nodes"] for p in period_metrics], color=["#2e86ab", "#a23b72"])
    axes[0, 0].set_xticks(x)
    axes[0, 0].set_xticklabels(periods_labels)
    axes[0, 0].set_ylabel("Nodes")
    axes[0, 0].set_title("Number of ports")

    axes[0, 1].bar(x, [p["n_edges"] for p in period_metrics], color=["#2e86ab", "#a23b72"])
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(periods_labels)
    axes[0, 1].set_ylabel("Edges")
    axes[0, 1].set_title("Number of routes")

    axes[1, 0].bar(x, [p["total_passages"] for p in period_metrics], color=["#2e86ab", "#a23b72"])
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels(periods_labels)
    axes[1, 0].set_ylabel("Passages")
    axes[1, 0].set_title("Total passages")

    axes[1, 1].bar(x, [p["density"] for p in period_metrics], color=["#2e86ab", "#a23b72"])
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(periods_labels)
    axes[1, 1].set_ylabel("Density")
    axes[1, 1].set_title("Network density")

    fig.suptitle("Pre-plague (1705–1708) vs Post-plague (1710–1713)", fontsize=12)
    plt.tight_layout()
    plt.savefig(outputs_dir / "period_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Period comparison plot saved to outputs/period_comparison.png")

    # Period-specific maps (cross-period scale for apples-to-apples comparison)
    period_graphs = list(graphs.values())
    for label, g in graphs.items():
        plot_map(
            g,
            output_path=str(outputs_dir / f"soundtoll_map_{label}.png"),
            highlight_ports=["Gdansk"],
            title=f"Sound Toll Shipping Network ({label})",
            scale_from_graphs=period_graphs,
        )
    print("  Period-specific maps saved")

    # Map (full period)
    print("Generating map...")
    plot_map(
        G,
        output_path=str(outputs_dir / "soundtoll_map.png"),
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
