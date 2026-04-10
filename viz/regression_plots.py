"""
Compelling visualizations for regression-ready panel data and seasonal network stats.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path


# Color palette: professional, distinct
COLORS = {
    "primary": "#1a365d",
    "secondary": "#2c5282",
    "accent": "#c53030",
    "muted": "#718096",
    "bg": "#f7fafc",
}
SEASON_COLORS = ["#2b6cb0", "#38a169", "#d69e2e", "#c53030"]  # Winter, Spring, Summer, Autumn


def plot_seasonal_network_heatmap(
    network_summary: pd.DataFrame,
    metric: str = "network_density",
    output_path: str | None = None,
    figsize: tuple[float, float] = (20, 10),
    year_min: int | None = None,
) -> None:
    """
    Heatmap: year × season for a network-level metric (density, reciprocity, etc.).
    """
    df = network_summary.copy()
    if year_min is not None:
        df = df[df["year"] >= year_min]
    pivot = df.pivot(index="year", columns="season", values=metric)
    pivot = pivot.sort_index()

    fig, ax = plt.subplots(figsize=figsize, facecolor="white")
    im = ax.imshow(
        pivot.values.T,
        aspect="auto",
        cmap="YlOrRd",
        origin="lower",
        extent=[pivot.index.min() - 0.5, pivot.index.max() + 0.5, 0.5, 4.5],
    )
    ax.set_yticks([1, 2, 3, 4])
    ax.set_yticklabels(["Winter", "Spring", "Summer", "Autumn"])
    ax.set_xlabel("Year")
    ax.set_ylabel("Season")
    ax.set_title(f"Network {metric.replace('network_', '')} by Year and Season", fontsize=14, fontweight="bold")
    plt.colorbar(im, ax=ax, label=metric)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
    else:
        plt.show()


def plot_seasonal_port_throughput(
    port_season_df: pd.DataFrame,
    top_ports: list[str],
    output_path: str | None = None,
    figsize: tuple[float, float] = (24, 12),
) -> None:
    """
    Four panels (one per season): throughput over years for top ports.
    Each panel shows how much traffic each port had in that season across years.
    """
    df = port_season_df[port_season_df["port"].isin(top_ports[:10])].copy()
    season_names = {1: "Winter", 2: "Spring", 3: "Summer", 4: "Autumn"}

    fig, axes = plt.subplots(2, 2, figsize=figsize, facecolor="white", sharex=True, sharey=True)
    axes = axes.flatten()

    for ax, (season, name) in zip(axes, season_names.items()):
        sub = df[df["season"] == season]
        years = sorted(sub["year"].unique())
        for port in top_ports[:10]:
            port_sub = sub[sub["port"] == port]
            by_year = port_sub.groupby("year")["throughput"].sum().reindex(years).fillna(0)
            ax.plot(years, by_year.values, "o-", label=port, linewidth=1.5, markersize=2, alpha=0.9)
        ax.set_title(name, fontsize=12, fontweight="bold")
        ax.set_ylabel("Throughput (passages)")
        ax.legend(loc="upper right", fontsize=8, ncol=1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, alpha=0.3)
    axes[2].set_xlabel("Year")
    axes[3].set_xlabel("Year")
    fig.suptitle(
        "Port Throughput by Season: How much traffic did each top port have in each season over time?",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
    else:
        plt.show()


def plot_seasonal_pattern_radar(
    network_summary: pd.DataFrame,
    output_path: str | None = None,
    figsize: tuple[float, float] = (10, 10),
    year_min: int | None = None,
) -> None:
    """
    Radar/spider: average network metrics by season (averaged across years).
    """
    df = network_summary.copy()
    if year_min is not None:
        df = df[df["year"] >= year_min]
    by_season = df.groupby("season").agg({
        "network_density": "mean",
        "network_reciprocity": "mean",
        "network_total_passages": "mean",
        "network_n_nodes": "mean",
    }).reset_index()

    metrics = ["network_density", "network_reciprocity", "network_n_nodes"]
    labels = ["Density", "Reciprocity", "Nodes (norm)"]
    n_metrics = len(metrics)
    angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=figsize, subplot_kw=dict(projection="polar"), facecolor="white")
    for i, (_, row) in enumerate(by_season.iterrows()):
        vals = [row[m] for m in metrics]
        # Normalize n_nodes to 0-1 for comparability
        vals[2] = (vals[2] - by_season["network_n_nodes"].min()) / (
            by_season["network_n_nodes"].max() - by_season["network_n_nodes"].min() + 1e-9
        )
        vals += vals[:1]
        season_name = ["Winter", "Spring", "Summer", "Autumn"][int(row["season"]) - 1]
        ax.plot(angles, vals, "o-", linewidth=2, label=season_name, color=SEASON_COLORS[i])
        ax.fill(angles, vals, alpha=0.15, color=SEASON_COLORS[i])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_title("Average Network Structure by Season", fontsize=14, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.0))
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
    else:
        plt.show()


def plot_regression_variable_correlation(
    panel_df: pd.DataFrame,
    numeric_cols: list[str] | None = None,
    output_path: str | None = None,
    figsize: tuple[float, float] = (12, 10),
) -> None:
    """
    Correlation heatmap of key regression variables.
    """
    if numeric_cols is None:
        numeric_cols = [
            "throughput", "in_degree", "out_degree",
            "degree_centrality", "betweenness_centrality",
            "network_density", "network_reciprocity",
        ]
    available = [c for c in numeric_cols if c in panel_df.columns]
    df = panel_df[available].dropna(how="all")
    corr = df.corr()

    fig, ax = plt.subplots(figsize=figsize, facecolor="white")
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(available)))
    ax.set_yticks(range(len(available)))
    ax.set_xticklabels(available, rotation=45, ha="right")
    ax.set_yticklabels(available)
    for i in range(len(available)):
        for j in range(len(available)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=9)
    ax.set_title("Correlation of Regression Variables (port-year panel)", fontsize=14, fontweight="bold")
    plt.colorbar(im, ax=ax, label="Correlation")
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
    else:
        plt.show()


def plot_network_seasonal_evolution(
    network_summary: pd.DataFrame,
    output_path: str | None = None,
    figsize: tuple[float, float] = (24, 12),
    year_min: int | None = None,
) -> None:
    """
    One plot per row: density, reciprocity, total passages by year with seasonal breakdown.
    """
    df = network_summary.copy()
    if year_min is not None:
        df = df[df["year"] >= year_min]
    years = sorted(df["year"].unique())
    seasons = [1, 2, 3, 4]
    season_names = ["Winter", "Spring", "Summer", "Autumn"]

    fig, axes = plt.subplots(3, 1, figsize=figsize, facecolor="white", sharex=True)

    for ax, (metric, title) in zip(axes, [
        ("network_density", "Network Density"),
        ("network_reciprocity", "Reciprocity"),
        ("network_total_passages", "Total Passages"),
    ]):
        for s, name in zip(seasons, season_names):
            sub = df[df["season"] == s]
            by_year = sub.groupby("year")[metric].mean().reindex(years)
            ax.plot(years, by_year.values, "o-", label=name, color=SEASON_COLORS[s - 1], linewidth=1.5, markersize=3)
        ax.set_ylabel(metric.replace("network_", ""))
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.legend(loc="upper right", fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlabel("Year")
    year_range = f"{years[0]}–{years[-1]}" if years else ""
    fig.suptitle(f"Seasonal Evolution of Network Structure ({year_range})", fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
    else:
        plt.show()


def plot_port_centrality_distribution(
    port_year_df: pd.DataFrame,
    port_season_df: pd.DataFrame | None = None,
    output_path: str | None = None,
    figsize: tuple[float, float] = (20, 12),
) -> None:
    """
    Distribution of degree centrality and betweenness across port-years.
    Top row: overall (port-year). Bottom row: separated by season (port-year-season).
    """
    season_names = {1: "Winter", 2: "Spring", 3: "Summer", 4: "Autumn"}

    if port_season_df is not None and "season" in port_season_df.columns:
        # 2 rows: degree_centrality, betweenness_centrality. 5 cols: All + 4 seasons
        fig, axes = plt.subplots(2, 5, figsize=figsize, facecolor="white", sharey="row")
        metrics = [
            ("degree_centrality", "Degree Centrality"),
            ("betweenness_centrality", "Betweenness Centrality"),
        ]
        for row, (col, title) in enumerate(metrics):
            # Col 0: All (from port_year)
            vals = port_year_df[col].dropna()
            vals = vals[vals > 0]
            axes[row, 0].hist(vals, bins=40, color=COLORS["primary"], alpha=0.7, edgecolor="white")
            axes[row, 0].set_title("All (port-year)", fontsize=10, fontweight="bold")
            axes[row, 0].set_ylabel("Count")
            axes[row, 0].spines["top"].set_visible(False)
            axes[row, 0].spines["right"].set_visible(False)
            # Cols 1-4: By season
            for col_idx, (season, name) in enumerate(season_names.items(), start=1):
                sub = port_season_df[port_season_df["season"] == season]
                vals = sub[col].dropna()
                vals = vals[vals > 0]
                axes[row, col_idx].hist(
                    vals, bins=40, color=SEASON_COLORS[season - 1], alpha=0.7, edgecolor="white"
                )
                axes[row, col_idx].set_title(name, fontsize=10, fontweight="bold")
                axes[row, col_idx].spines["top"].set_visible(False)
                axes[row, col_idx].spines["right"].set_visible(False)
            axes[row, 0].set_ylabel(title, fontsize=10)
        for col_idx in range(5):
            axes[1, col_idx].set_xlabel("Value")
        fig.suptitle(
            "Port-Level Centrality Distribution by Season (port-year-season panel)",
            fontsize=14,
            fontweight="bold",
            y=1.02,
        )
    else:
        # Fallback: original 1x2 layout
        fig, axes = plt.subplots(1, 2, figsize=(16, 6), facecolor="white")
        for ax, (col, title) in zip(
            axes,
            [("degree_centrality", "Degree Centrality"), ("betweenness_centrality", "Betweenness Centrality")],
        ):
            vals = port_year_df[col].dropna()
            vals = vals[vals > 0]
            ax.hist(vals, bins=50, color=COLORS["primary"], alpha=0.7, edgecolor="white")
            ax.set_xlabel(col.replace("_", " ").title())
            ax.set_ylabel("Count")
            ax.set_title(f"Distribution of {title}", fontsize=12, fontweight="bold")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
        fig.suptitle("Port-Level Centrality Distribution (port-year panel)", fontsize=14, fontweight="bold", y=1.02)

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
    else:
        plt.show()


# Default start year for regression plots (sustained high volume from 1668)
REGRESSION_PLOT_YEAR_MIN = 1668


def plot_all_regression_outputs(
    outputs_dir: Path,
    port_year_df: pd.DataFrame,
    port_season_df: pd.DataFrame,
    network_summary: pd.DataFrame,
    top_ports: list[str],
    year_min: int | None = REGRESSION_PLOT_YEAR_MIN,
) -> None:
    """Generate all regression-related plots and save to outputs_dir."""
    outputs_dir = Path(outputs_dir)
    outputs_dir.mkdir(exist_ok=True)

    plot_seasonal_network_heatmap(
        network_summary,
        metric="network_density",
        output_path=str(outputs_dir / "regression_seasonal_density_heatmap.png"),
        year_min=year_min,
    )
    plot_seasonal_network_heatmap(
        network_summary,
        metric="network_reciprocity",
        output_path=str(outputs_dir / "regression_seasonal_reciprocity_heatmap.png"),
        year_min=year_min,
    )
    plot_network_seasonal_evolution(
        network_summary,
        output_path=str(outputs_dir / "regression_seasonal_evolution.png"),
        year_min=year_min,
    )
    plot_seasonal_pattern_radar(
        network_summary,
        output_path=str(outputs_dir / "regression_seasonal_radar.png"),
        year_min=year_min,
    )
    plot_regression_variable_correlation(
        port_year_df,
        output_path=str(outputs_dir / "regression_correlation_heatmap.png"),
    )
    plot_port_centrality_distribution(
        port_year_df,
        port_season_df=port_season_df,
        output_path=str(outputs_dir / "regression_centrality_distribution.png"),
    )
    plot_seasonal_port_throughput(
        port_season_df,
        top_ports=top_ports,
        output_path=str(outputs_dir / "regression_port_seasonal_throughput.png"),
    )
