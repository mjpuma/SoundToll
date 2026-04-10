#!/usr/bin/env python3
"""
Sound Toll Network Analysis - orchestration script.

Loads data, filters by year/radii, builds graphs, computes metrics, and produces visualizations.

Use --commodity to also run commodity-by-commodity network analysis
(requires data/ladingen.csv from STRO 2.0 Figshare).
"""

import argparse
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

# Use non-interactive backend for headless/script execution
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data.loader import load_soundtoll, load_soundtoll_with_cargo
from data.regression_panel import (
    build_network_year_season_summary,
    build_port_year_panel,
    build_port_year_season_panel,
    build_route_year_panel,
    export_sea_network_timeseries_csvs,
)
from filters.filter import filter_data
from network.analysis import (
    build_graph,
    build_backbone_graph,
    build_graphs_by_period,
    compute_metrics,
)
from viz.map import plot_map, EXTENT_ZOOMED, EXTENT_WIDE
from viz.network_plot import plot_network
from viz.period_comparison import plot_period_comparison
from viz.port_metrics import (
    build_port_metrics_table,
    plot_top_ports_comparison,
    plot_top_ports_by_decade,
    plot_port_in_out_degree,
    plot_port_hub_bridge_scatter,
)
from viz.port_timeseries import select_key_ports, build_port_timeseries, plot_port_timeseries
from viz.regression_plots import plot_all_regression_outputs
from viz.commodity_comparison import plot_top_commodities_by_passages


def run_commodity_analysis(base: Path, outputs_dir: Path, force: bool = False) -> None:
    """
    Commodity-by-commodity network analysis.

    Requires data/ladingen.csv from https://doi.org/10.6084/m9.figshare.27221169.v2
    Saves per-commodity outputs to outputs/commodity_maps/{safe_commodity_name}/.

    Figures are produced before geographic maps: top_commodities_by_passages.png (overall),
    then per commodity: top_ports_metrics_*.png, network_metrics_*.png, port_hub_bridge_*.png,
    then period and backbone maps. Raw-string unmatched diagnostics run last.
    """
    from data.cargo_lookup import (
        commodity_unmatched_frequency,
        expand_passages_to_commodities,
        get_cargo_lookup,
        get_port_mapping,
        standardize_ports,
    )
    from network.analysis import (
        build_backbone_graph,
        build_graph_by_commodity,
        build_graphs_by_period,
        compute_metrics,
        port_degree_metrics,
    )

    data_path = base / "2602_soundtoll_with_radii.csv"
    mappings_path = base / "Fixed Port City & Cargo Mappings.xlsx"
    ladingen_path = base / "data" / "ladingen.csv"
    cargoes_regs_path = base / "data" / "cargoes_regs.csv"
    commodity_master_path = base / "data" / "commodity_master.csv"

    if not ladingen_path.exists() and not cargoes_regs_path.exists():
        print(f"  Skipping commodity analysis: need ladingen.csv or cargoes_regs.csv in data/")
        print("  Download cargoes_regs.csv from https://figshare.com/articles/dataset/STRO_2_0_-_Re-engineered_data_from_Sound_Toll_Registers_Online/27176202")
        return

    print("Commodity analysis...")
    df = load_soundtoll_with_cargo(data_path)
    df = filter_data(df, year_min=1668, year_max=1800)
    df = df[df["cargo_ids"].astype(str).str.len() > 4]  # non-empty cargo
    print(f"  Rows with cargo: {len(df):,}")

    cargo_lookup = get_cargo_lookup(
        ladingen_path=ladingen_path,
        cargoes_regs_path=cargoes_regs_path,
        mappings_path=mappings_path,
        commodity_master_path=commodity_master_path,
    )
    port_mapping = get_port_mapping(mappings_path)
    df_expanded = expand_passages_to_commodities(
        df,
        cargo_lookup=cargo_lookup,
        cargoes_regs_path=cargoes_regs_path,
        mappings_path=mappings_path,
        commodity_master_path=commodity_master_path,
    )
    df_expanded = standardize_ports(df_expanded, port_mapping=port_mapping)
    print(f"  Expanded to {len(df_expanded):,} passage-commodity rows")

    # Top 15 commodities by passage count (exclude "Unknown" from -/missing cargo)
    top_commodities = (
        df_expanded[df_expanded["commodity"] != "Unknown"]
        .groupby("commodity")["num_passages"]
        .sum()
        .sort_values(ascending=False)
        .head(15)
    )
    commodities = top_commodities.index.tolist()
    print(f"  Top commodities: {commodities[:5]}...")

    # Figures first: overall commodity volume (before per-commodity maps / refinement stats)
    top_comm_agg = (
        df_expanded[df_expanded["commodity"] != "Unknown"]
        .groupby("commodity", as_index=False)["num_passages"]
        .sum()
        .rename(columns={"num_passages": "total_passages"})
        .sort_values("total_passages", ascending=False)
    )
    plot_top_commodities_by_passages(
        top_comm_agg.head(15),
        output_path=str(outputs_dir / "top_commodities_by_passages.png"),
        top_n=15,
    )
    print("  Saved outputs/top_commodities_by_passages.png")

    periods = [(1705, 1708), (1710, 1713)]
    backbone_periods = [(y, y) for y in range(1705, 1721)]

    commodity_maps_dir = outputs_dir / "commodity_maps"
    commodity_maps_dir.mkdir(exist_ok=True)

    all_stats_rows = []

    for commodity in commodities:
        sub = df_expanded[df_expanded["commodity"] == commodity]
        total_pass = sub["num_passages"].sum()
        if total_pass < 10:
            continue

        safe_name = re.sub(r"[^\w\-]", "_", commodity)
        commodity_dir = commodity_maps_dir / safe_name
        metrics_marker = commodity_dir / f"top_ports_metrics_{safe_name}.png"
        if commodity_dir.exists() and not force and metrics_marker.exists():
            print(f"  Skipping {commodity} (outputs exist, use --force to overwrite)")
            continue
        if commodity_dir.exists() and not force and not metrics_marker.exists():
            print(f"  {commodity}: adding metric figures (existing dir, missing top_ports_metrics_*.png)")

        commodity_dir.mkdir(parents=True, exist_ok=True)

        G = build_graph_by_commodity(df_expanded, commodity, directed=True, min_passages=3)
        if G.number_of_nodes() == 0:
            continue

        m = compute_metrics(G)
        n, edge_count = m["n_nodes"], m["n_edges"]
        avg_degree = 2 * edge_count / n if n > 0 else 0
        print(f"  {commodity}: n_nodes={n}, n_edges={edge_count}, total_passages={m['total_passages']:,.0f}")

        # 1. Per-period stats and top ports (maps use stricter edge threshold)
        period_graphs = build_graphs_by_period(sub, periods=periods, directed=True, min_passages=3)
        # Looser threshold so pre/post metric plots exist for sparse commodities
        period_graphs_metrics = build_graphs_by_period(
            sub, periods=periods, directed=True, min_passages=1
        )
        period_stats = []
        top_ports_rows = []

        for label, g in period_graphs.items():
            if g.number_of_nodes() == 0:
                continue
            pm = compute_metrics(g)
            n_p = pm["n_nodes"]
            m_p = pm["n_edges"]
            avg_deg_p = 2 * m_p / n_p if n_p > 0 else 0
            period_stats.append({
                "period": label,
                "n_nodes": n_p,
                "n_edges": m_p,
                "total_passages": pm["total_passages"],
                "density": pm["density"],
                "avg_degree": avg_deg_p,
            })
            deg_m = port_degree_metrics(g)
            in_d = deg_m["in_degree"]
            top10 = sorted(in_d.items(), key=lambda x: -x[1])[:10]
            for rank, (port, w) in enumerate(top10, 1):
                top_ports_rows.append({"period": label, "rank": rank, "port": port, "weighted_in_degree": w})

        # Add full-period and backbone to stats
        period_stats.append({
            "period": "1705-1720",
            "n_nodes": n,
            "n_edges": edge_count,
            "total_passages": m["total_passages"],
            "density": m["density"],
            "avg_degree": avg_degree,
        })
        all_stats_rows.extend([{**r, "commodity": commodity} for r in period_stats])

        pd.DataFrame(period_stats).to_csv(
            commodity_dir / f"commodity_network_stats_{safe_name}.csv",
            index=False,
        )
        pd.DataFrame(top_ports_rows).to_csv(
            commodity_dir / f"top_ports_{safe_name}.csv",
            index=False,
        )

        # 2. Metric figures first (same style as main pipeline), then geographic maps
        g_pre = period_graphs_metrics.get("1705-1708")
        g_post = period_graphs_metrics.get("1710-1713")
        if (
            g_pre is not None
            and g_post is not None
            and g_pre.number_of_nodes() > 0
            and g_post.number_of_nodes() > 0
        ):
            period_graphs_2 = {"1705-1708": g_pre, "1710-1713": g_post}
            port_df_c = build_port_metrics_table(period_graphs_2)
            plot_top_ports_comparison(
                port_df_c,
                period_graphs_2,
                top_n=10,
                output_path=str(commodity_dir / f"top_ports_metrics_{safe_name}.png"),
                suptitle=f"{commodity}: top ports (pre vs post 1709)",
            )
            total_both = sum(
                compute_metrics(g)["total_passages"] for g in period_graphs_2.values()
            )
            period_metrics_c = []
            for label, g in period_graphs_2.items():
                m = compute_metrics(g)
                top_deg = sorted(m["degree_centrality"].items(), key=lambda x: x[1], reverse=True)[
                    :3
                ]
                max_edge = max((g.edges[e].get("weight", 1) for e in g.edges()), default=0)
                avg_between = (
                    np.mean(list(m["betweenness_centrality"].values()))
                    if m["betweenness_centrality"]
                    else 0.0
                )
                reciprocity = m.get("reciprocity", 0.0)
                period_metrics_c.append(
                    {
                        "period": label,
                        "n_nodes": m["n_nodes"],
                        "n_edges": m["n_edges"],
                        "density": m["density"],
                        "total_passages": m["total_passages"],
                        "pct_passages": 100 * m["total_passages"] / total_both if total_both else 0,
                        "max_route_passages": max_edge,
                        "reciprocity": reciprocity,
                        "avg_betweenness": avg_between,
                        "top_ports": ", ".join(p[0] for p in top_deg),
                    }
                )
            plot_period_comparison(
                period_metrics_c,
                output_path=str(commodity_dir / f"network_metrics_{safe_name}.png"),
                suptitle=f"{commodity}: network metrics (pre vs post 1709)",
            )
            plot_port_hub_bridge_scatter(
                port_df_c,
                period_label=["1705-1708", "1710-1713"],
                top_n=15,
                output_path=str(commodity_dir / f"port_hub_bridge_{safe_name}.png"),
                suptitle=f"{commodity}: hub vs bridge (pre vs post 1709)",
            )

        # 3. Period maps
        period_graph_list = list(period_graphs.values())
        for label, g in period_graphs.items():
            if g.number_of_nodes() == 0:
                continue
            plot_map(
                g,
                output_path=str(commodity_dir / f"soundtoll_map_{label}_zoom.png"),
                extent=EXTENT_WIDE,
                highlight_ports=["Gdansk"],
                title=f"{commodity} ({label})",
                scale_from_graphs=period_graph_list,
            )

        # 4. Backbone maps (0.5 and 0.75)
        year_graphs = build_graphs_by_period(sub, periods=backbone_periods, directed=True, min_passages=3)
        for min_frac in (0.5, 0.75):
            backbone_G = build_backbone_graph(year_graphs, min_years_present=min_frac)
            if backbone_G.number_of_edges() == 0:
                continue
            plot_map(
                backbone_G,
                output_path=str(commodity_dir / f"soundtoll_backbone_{min_frac}_zoom.png"),
                extent=EXTENT_WIDE,
                highlight_ports=["Gdansk"],
                title=f"{commodity} backbone (≥{min_frac:.0%} of years)",
            )

    if all_stats_rows:
        stats_all_df = pd.DataFrame(all_stats_rows)
        stats_all_df.to_csv(outputs_dir / "commodity_network_stats_all.csv", index=False)
        print(f"  Summary saved to commodity_network_stats_all.csv ({len(stats_all_df)} rows)")

    # Refinement diagnostics last (full scan of cargoes_regs; not needed to review figures)
    if cargoes_regs_path.exists():
        u_df, n_uniq_unmatched = commodity_unmatched_frequency(
            cargoes_regs_path=cargoes_regs_path,
            mappings_path=mappings_path,
        )
        print(
            f"  [Refinement] Unique raw commodity strings with no Excel/Latin-ASCII/regex match: {n_uniq_unmatched:,}"
        )
        print("  Top 20 still-unmatched by row frequency:")
        print(u_df.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="Sound Toll Network Analysis")
    parser.add_argument("--commodity", action="store_true", help="Run commodity-by-commodity analysis")
    parser.add_argument(
        "--commodity-only",
        action="store_true",
        help="Skip the full main pipeline; run only commodity-by-commodity analysis",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run all commodity outputs even if top_ports_metrics_*.png already exists",
    )
    args = parser.parse_args()

    # Paths
    base = Path(__file__).resolve().parent
    data_path = base / "2602_soundtoll_with_radii.csv"
    outputs_dir = base / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    if not data_path.exists():
        print(f"Data file not found: {data_path}")
        print("Place 2602_soundtoll_with_radii.csv in the project root.")
        return

    if args.commodity_only:
        print("Commodity-only mode (skipping full pipeline)...")
        run_commodity_analysis(base, outputs_dir, force=args.force)
        print(f"Done. Outputs under {outputs_dir / 'commodity_maps'}")
        return

    # Load
    print("Loading data...")
    df = load_soundtoll(data_path)
    print(f"  Loaded {len(df):,} rows")

    # Filter: 1668-1800 (sustained high volume from 1668)
    year_min, year_max = 1668, 1800
    df_filtered = filter_data(df, year_min=year_min, year_max=year_max)
    print(f"  Filtered to {len(df_filtered):,} rows ({year_min}-{year_max})")

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

    # Multi-decade port comparison (1680s, 1710s, 1750s, 1780s)
    decade_periods = [(1680, 1690), (1710, 1720), (1750, 1760), (1780, 1790)]
    decade_graphs = build_graphs_by_period(
        df_filtered, periods=decade_periods, directed=True, min_passages=5
    )
    port_df_decade = build_port_metrics_table(decade_graphs)
    plot_top_ports_by_decade(
        port_df_decade,
        decade_graphs,
        decades=decade_periods,
        top_n=10,
        output_path=str(outputs_dir / "top_ports_by_decade.png"),
    )
    print("  Top ports by decade saved to outputs/top_ports_by_decade.png")

    # In-degree vs out-degree (full period): importers vs exporters
    full_graph = {"1668-1800": G}
    port_df_full = build_port_metrics_table(full_graph)
    plot_port_in_out_degree(
        port_df_full,
        period_label="1668-1800",
        top_n=12,
        output_path=str(outputs_dir / "port_in_out_degree.png"),
    )
    print("  Port in/out degree saved to outputs/port_in_out_degree.png")

    # Hub vs bridge: degree vs betweenness scatter (pre/post 1709)
    plot_port_hub_bridge_scatter(
        port_df,
        period_label=["1705-1708", "1710-1713"],
        top_n=25,
        output_path=str(outputs_dir / "port_hub_bridge_scatter.png"),
    )
    print("  Port hub vs bridge scatter saved to outputs/port_hub_bridge_scatter.png")

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

    # Backbone network 1705-1720: persistent routes + stable port markers
    backbone_periods = [(y, y) for y in range(1705, 1721)]
    backbone_graphs = build_graphs_by_period(
        df_filtered,
        periods=backbone_periods,
        directed=True,
        min_passages=5,
    )
    stable_ports = select_key_ports(
        backbone_graphs,
        top_n=15,
        metric="throughput",
        max_ports=25,
        min_years_in_top=10,
    )
    pd.DataFrame({"port": stable_ports}).to_csv(
        outputs_dir / "stable_ports_1705_1720.csv", index=False
    )
    print(f"  Stable ports (1705-1720): {stable_ports}")

    for min_frac in (0.5, 0.75):
        backbone_G = build_backbone_graph(backbone_graphs, min_years_present=min_frac)
        print(f"  Backbone ({min_frac:.0%}): {backbone_G.number_of_nodes()} nodes, {backbone_G.number_of_edges()} edges")
        plot_map(
            backbone_G,
            output_path=str(outputs_dir / f"soundtoll_backbone_1705_1720_{min_frac}_zoom.png"),
            extent=EXTENT_ZOOMED,
            highlight_ports=["Gdansk"],
            stable_ports=stable_ports,
            title=f"Sound Toll Backbone Network (1705–1720, ≥{min_frac:.0%} of years)",
        )
        plot_map(
            backbone_G,
            output_path=str(outputs_dir / f"soundtoll_backbone_1705_1720_{min_frac}_wide.png"),
            extent=EXTENT_WIDE,
            highlight_ports=["Gdansk"],
            stable_ports=stable_ports,
            title=f"Sound Toll Backbone Network (1705–1720, ≥{min_frac:.0%} of years)",
        )
    print("  Backbone maps with stable port markers saved (0.5 and 0.75)")

    # Year-by-year maps (1668-1800)
    year_periods = [(y, y) for y in range(year_min, year_max + 1)]
    year_graphs = build_graphs_by_period(
        df_filtered,
        periods=year_periods,
        directed=True,
        min_passages=5,
    )
    maps_by_year_dir = outputs_dir / "maps_by_year"
    maps_by_year_dir.mkdir(exist_ok=True)
    year_graph_list = list(year_graphs.values())
    for label, g in year_graphs.items():
        if g.number_of_nodes() == 0:
            print(f"  Skipping {label} (no data)")
            continue
        plot_map(
            g,
            output_path=str(maps_by_year_dir / f"soundtoll_map_{label}.png"),
            extent=EXTENT_ZOOMED,
            highlight_ports=["Gdansk"],
            title=f"Sound Toll Shipping Network ({label})",
            scale_from_graphs=year_graph_list,
        )
    print(f"  Year-by-year maps saved to {maps_by_year_dir} ({len(year_graphs)} years)")

    # Key port timeseries: ports ever in top 10 by throughput, in top 10 for ≥15 years, max 10
    key_ports = select_key_ports(
        year_graphs,
        top_n=10,
        metric="throughput",
        max_ports=10,
        min_years_in_top=15,
    )
    print(f"  Key ports (ever top 10 by throughput): {key_ports}")
    port_ts_df = build_port_timeseries(year_graphs, key_ports)
    port_ts_df.to_csv(outputs_dir / "port_timeseries.csv", index=False)
    plot_port_timeseries(
        port_ts_df,
        output_dir=outputs_dir,
        base_name="port_importance_timeseries",
    )
    print("  Port importance timeseries saved to outputs/port_importance_timeseries_*.png")

    # Regression-ready panels and seasonal analysis
    print("Building regression panels and seasonal stats...")
    port_year_df = build_port_year_panel(
        df_filtered, year_min=year_min, year_max=year_max, min_passages=5
    )
    port_year_df.to_csv(outputs_dir / "regression_port_year.csv", index=False)
    print(f"  Port-year panel: {len(port_year_df):,} rows -> regression_port_year.csv")

    port_season_df = build_port_year_season_panel(
        df_filtered, year_min=year_min, year_max=year_max, min_passages=1
    )
    port_season_df.to_csv(outputs_dir / "regression_port_year_season.csv", index=False)
    print(f"  Port-year-season panel: {len(port_season_df):,} rows -> regression_port_year_season.csv")

    route_year_df = build_route_year_panel(
        df_filtered, year_min=year_min, year_max=year_max, min_passages=1
    )
    route_year_df.to_csv(outputs_dir / "regression_route_year.csv", index=False)
    print(f"  Route-year panel: {len(route_year_df):,} rows -> regression_route_year.csv")

    network_summary = build_network_year_season_summary(
        df_filtered, year_min=year_min, year_max=year_max, min_passages=1
    )
    network_summary.to_csv(outputs_dir / "regression_network_year_season.csv", index=False)
    print(f"  Network year-season summary: {len(network_summary):,} rows -> regression_network_year_season.csv")

    sea_dir = outputs_dir / "sea"
    sea_y, sea_ys = export_sea_network_timeseries_csvs(
        df_filtered,
        sea_dir,
        year_min=year_min,
        year_max=year_max,
        min_passages_year=5,
        min_passages_season=1,
    )
    print(f"  SEA time series: {sea_y.name}, {sea_ys.name} -> {sea_dir}")
    defs_doc = base / "NETWORK_METRICS_DEFINITIONS.md"
    if defs_doc.exists():
        shutil.copy2(defs_doc, sea_dir / defs_doc.name)
        print(f"  Copied {defs_doc.name} to {sea_dir}")

    plot_all_regression_outputs(
        outputs_dir,
        port_year_df=port_year_df,
        port_season_df=port_season_df,
        network_summary=network_summary,
        top_ports=key_ports,
        year_min=year_min,
    )
    print("  Regression plots saved to outputs/regression_*.png")

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

    if args.commodity:
        run_commodity_analysis(base, outputs_dir, force=args.force)


if __name__ == "__main__":
    main()
