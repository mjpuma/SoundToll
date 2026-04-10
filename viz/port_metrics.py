"""
Port-level network stats table and before/after bar plots.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


COLOR_PRE = "#1a365d"
COLOR_POST = "#9b2c2c"


def build_port_metrics_table(
    graphs: dict,
    period_labels: list[str] | None = None,
) -> pd.DataFrame:
    """
    Build a table of network stats by port across periods.

    Parameters
    ----------
    graphs : dict
        Keys like "1705-1708", "1710-1713". Values are NetworkX graphs.
    period_labels : list[str] | None
        If provided, use these as column suffixes. Default: graph keys.

    Returns
    -------
    pd.DataFrame
        Columns: port, degree_{period}, betweenness_{period}, passages_{period}, ...
    """
    from network.analysis import compute_metrics, port_degree_metrics

    if period_labels is None:
        period_labels = list(graphs.keys())

    all_ports = set()
    for g in graphs.values():
        all_ports.update(g.nodes())

    rows = []
    for port in sorted(all_ports):
        row = {"port": port}
        for label, g in zip(period_labels, graphs.values()):
            m = compute_metrics(g)
            deg = port_degree_metrics(g)
            row[f"degree_{label}"] = m["degree_centrality"].get(port, np.nan)
            row[f"betweenness_{label}"] = m["betweenness_centrality"].get(port, np.nan)
            row[f"in_degree_{label}"] = deg["in_degree"].get(port, 0)
            row[f"out_degree_{label}"] = deg["out_degree"].get(port, 0)
            row[f"passages_{label}"] = deg["throughput"].get(port, 0) if port in g.nodes() else np.nan
        rows.append(row)

    return pd.DataFrame(rows)


def plot_top_ports_comparison(
    port_df: pd.DataFrame,
    graphs: dict,
    top_n: int = 10,
    output_path: str | None = None,
    figsize: tuple[float, float] = (12, 10),
    suptitle: str | None = None,
) -> None:
    """
    Bar plots: top ports before/after for degree, betweenness, and passages.

    Parameters
    ----------
    port_df : pd.DataFrame
        From build_port_metrics_table.
    graphs : dict
        Period name -> graph.
    top_n : int
        Number of top ports to show per metric.
    output_path : str | None
        Save path.
    figsize : tuple
        Figure size.
    """
    periods = list(graphs.keys())
    pre_label, post_label = periods[0], periods[1]

    deg_pre = f"degree_{pre_label}"
    deg_post = f"degree_{post_label}"
    bet_pre = f"betweenness_{pre_label}"
    bet_post = f"betweenness_{post_label}"
    pass_pre = f"passages_{pre_label}"
    pass_post = f"passages_{post_label}"

    # Top ports by pre-period metric (so we see change)
    top_by_deg = port_df.nlargest(top_n, deg_pre)
    top_by_bet = port_df.nlargest(top_n, bet_pre)
    top_by_pass = port_df.nlargest(top_n, pass_pre)

    fig, axes = plt.subplots(2, 2, figsize=figsize, facecolor="white")
    _st = suptitle or "Top Ports: Pre- vs Post-Plague (1709) Network Metrics"
    fig.suptitle(_st, fontsize=14, fontweight="bold", y=1.02)

    x = np.arange(top_n)
    width = 0.35

    # 1. Degree centrality
    ax = axes[0, 0]
    bars1 = ax.bar(x - width / 2, top_by_deg[deg_pre].values, width, label=pre_label, color=COLOR_PRE, edgecolor="white")
    bars2 = ax.bar(x + width / 2, top_by_deg[deg_post].values, width, label=post_label, color=COLOR_POST, edgecolor="white")
    ax.set_ylabel("Degree centrality")
    ax.set_title("Top 10 by degree: pre vs post")
    ax.set_xticks(x)
    ax.set_xticklabels(top_by_deg["port"].values, rotation=45, ha="right")
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # 2. Betweenness centrality
    ax = axes[0, 1]
    ax.bar(x - width / 2, top_by_bet[bet_pre].values, width, label=pre_label, color=COLOR_PRE, edgecolor="white")
    ax.bar(x + width / 2, top_by_bet[bet_post].values, width, label=post_label, color=COLOR_POST, edgecolor="white")
    ax.set_ylabel("Betweenness centrality")
    ax.set_title("Top 10 by betweenness: pre vs post")
    ax.set_xticks(x)
    ax.set_xticklabels(top_by_bet["port"].values, rotation=45, ha="right")
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # 3. Passages (total traffic)
    ax = axes[1, 0]
    ax.bar(x - width / 2, top_by_pass[pass_pre].values, width, label=pre_label, color=COLOR_PRE, edgecolor="white")
    ax.bar(x + width / 2, top_by_pass[pass_post].values, width, label=post_label, color=COLOR_POST, edgecolor="white")
    ax.set_ylabel("Total passages")
    ax.set_title("Top 10 by traffic: pre vs post")
    ax.set_xticks(x)
    ax.set_xticklabels(top_by_pass["port"].values, rotation=45, ha="right")
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # 4. Summary table of top 5
    ax = axes[1, 1]
    ax.axis("off")
    tbl_data = []
    for _, r in top_by_deg.head(5).iterrows():
        tbl_data.append([
            r["port"],
            f"{r[deg_pre]:.3f}",
            f"{r[deg_post]:.3f}",
            f"{r[pass_pre]:,.0f}",
            f"{r[pass_post]:,.0f}",
        ])
    table = ax.table(
        cellText=tbl_data,
        colLabels=["Port", f"Deg ({pre_label})", f"Deg ({post_label})", f"Pass ({pre_label})", f"Pass ({post_label})"],
        loc="center",
        cellLoc="center",
        colColours=["#e2e8f0"] * 5,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 2.2)
    ax.set_title("Top 5 ports (by pre-plague degree): pre vs post", fontsize=12, fontweight="bold", pad=10)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
    else:
        plt.show()


def plot_top_ports_by_decade(
    port_df: pd.DataFrame,
    graphs: dict,
    decades: list[tuple[int, int]] | None = None,
    top_n: int = 10,
    output_path: str | None = None,
    figsize: tuple[float, float] = (18, 12),
) -> None:
    """
    Multi-decade comparison: top ports by degree, betweenness, passages across 4 decades.
    Similar to top_ports_comparison but for longer periods (e.g. 1680s, 1710s, 1750s, 1780s).
    """
    if decades is None:
        decades = [(1680, 1690), (1710, 1720), (1750, 1760), (1780, 1790)]
    period_labels = [f"{a}-{b}" for a, b in decades]
    n_periods = len(period_labels)
    colors = plt.cm.viridis(np.linspace(0.2, 0.8, n_periods))

    # Use first period to rank ports (so we see change)
    first_label = period_labels[0]
    deg_col = f"degree_{first_label}"
    if deg_col not in port_df.columns:
        raise ValueError(f"port_df must have columns degree_{{period}}. Got: {list(port_df.columns)}")
    top_ports = port_df.nlargest(top_n, deg_col)["port"].tolist()
    port_df_top = port_df[port_df["port"].isin(top_ports)]

    fig, axes = plt.subplots(2, 2, figsize=figsize, facecolor="white")
    x = np.arange(top_n)
    width = 0.8 / n_periods

    # 1. Degree centrality across decades
    ax = axes[0, 0]
    for i, label in enumerate(period_labels):
        col = f"degree_{label}"
        if col in port_df_top.columns:
            vals = port_df_top.set_index("port").reindex(top_ports)[col].values
            ax.bar(x + i * width, vals, width, label=label, color=colors[i], edgecolor="white")
    ax.set_ylabel("Degree centrality")
    ax.set_title("Top 10 ports: degree centrality by decade")
    ax.set_xticks(x + width * (n_periods - 1) / 2)
    ax.set_xticklabels(top_ports, rotation=45, ha="right")
    ax.legend(loc="upper right", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # 2. Betweenness centrality across decades
    ax = axes[0, 1]
    for i, label in enumerate(period_labels):
        col = f"betweenness_{label}"
        if col in port_df_top.columns:
            vals = port_df_top.set_index("port").reindex(top_ports)[col].values
            ax.bar(x + i * width, vals, width, label=label, color=colors[i], edgecolor="white")
    ax.set_ylabel("Betweenness centrality")
    ax.set_title("Top 10 ports: betweenness by decade")
    ax.set_xticks(x + width * (n_periods - 1) / 2)
    ax.set_xticklabels(top_ports, rotation=45, ha="right")
    ax.legend(loc="upper right", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # 3. Passages (throughput) across decades
    ax = axes[1, 0]
    for i, label in enumerate(period_labels):
        col = f"passages_{label}"
        if col in port_df_top.columns:
            vals = port_df_top.set_index("port").reindex(top_ports)[col].values
            ax.bar(x + i * width, np.nan_to_num(vals), width, label=label, color=colors[i], edgecolor="white")
    ax.set_ylabel("Total passages")
    ax.set_title("Top 10 ports: traffic by decade")
    ax.set_xticks(x + width * (n_periods - 1) / 2)
    ax.set_xticklabels(top_ports, rotation=45, ha="right")
    ax.legend(loc="upper right", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # 4. Summary table: top 5 with all decades
    ax = axes[1, 1]
    ax.axis("off")
    tbl_data = []
    for port in top_ports[:5]:
        row = [port]
        for label in period_labels:
            col = f"passages_{label}"
            if col in port_df_top.columns:
                val = port_df_top[port_df_top["port"] == port][col].values
                row.append(f"{val[0]:,.0f}" if len(val) and not np.isnan(val[0]) else "-")
            else:
                row.append("-")
        tbl_data.append(row)
    col_labels = ["Port"] + [f"Pass ({l})" for l in period_labels]
    table = ax.table(
        cellText=tbl_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
        colColours=["#e2e8f0"] * len(col_labels),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.1, 2.0)
    ax.set_title("Top 5 ports: traffic across decades", fontsize=12, fontweight="bold", pad=10)

    fig.suptitle("Top Ports: Multi-Decade Comparison (1668-1800)", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
    else:
        plt.show()


def plot_port_in_out_degree(
    port_df: pd.DataFrame,
    period_label: str,
    top_n: int = 12,
    output_path: str | None = None,
    figsize: tuple[float, float] = (12, 8),
) -> None:
    """
    In-degree vs out-degree for top ports: are they importers or exporters?
    Grouped bar chart.
    """
    in_col = f"in_degree_{period_label}"
    out_col = f"out_degree_{period_label}"
    pass_col = f"passages_{period_label}"
    if in_col not in port_df.columns:
        in_col = "in_degree"
    if out_col not in port_df.columns:
        out_col = "out_degree"
    if pass_col not in port_df.columns:
        pass_col = next((c for c in port_df.columns if "passage" in c.lower()), "in_degree")
    rank_col = pass_col
    top = port_df.nlargest(top_n, rank_col)
    ports = top["port"].tolist()
    in_vals = top[in_col].values if in_col in top.columns else np.zeros(top_n)
    out_vals = top[out_col].values if out_col in top.columns else np.zeros(top_n)
    x = np.arange(len(ports))
    width = 0.35
    fig, ax = plt.subplots(figsize=figsize, facecolor="white")
    ax.bar(x - width / 2, in_vals, width, label="In (arrivals)", color="#2b6cb0", edgecolor="white")
    ax.bar(x + width / 2, out_vals, width, label="Out (departures)", color="#38a169", edgecolor="white")
    ax.set_ylabel("Passages")
    ax.set_title(f"In-degree vs Out-degree: Top {top_n} Ports by Traffic ({period_label})")
    ax.set_xticks(x)
    ax.set_xticklabels(ports, rotation=45, ha="right")
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
    else:
        plt.show()


def plot_port_hub_bridge_scatter(
    port_df: pd.DataFrame,
    period_label: str | list[str],
    top_n: int = 30,
    output_path: str | None = None,
    figsize: tuple[float, float] = (16, 7),
    suptitle: str | None = None,
) -> None:
    """
    Degree centrality vs betweenness: hub vs bridge characterization.
    - High degree + high betweenness = super hub (well-connected and on many paths)
    - High betweenness, lower degree = bridge (connects otherwise disconnected regions)
    - High degree, lower betweenness = local hub (many connections but not critical path)

    If period_label is a list of 2 (e.g. pre/post 1709), creates side-by-side panels.
    """
    period_labels = [period_label] if isinstance(period_label, str) else period_label
    n_panels = len(period_labels)
    fig, axes = plt.subplots(1, n_panels, figsize=figsize, facecolor="white", sharey=True, sharex=True)
    if n_panels == 1:
        axes = [axes]
    panel_titles = {"1705-1708": "Pre-plague (1705–1708)", "1710-1713": "Post-plague (1710–1713)"}

    for ax, plabel in zip(axes, period_labels):
        deg_col = f"degree_{plabel}"
        bet_col = f"betweenness_{plabel}"
        pass_col = f"passages_{plabel}"
        if deg_col not in port_df.columns:
            deg_col = "degree_centrality"
        if bet_col not in port_df.columns:
            bet_col = "betweenness_centrality"
        rank_col = pass_col if pass_col in port_df.columns else deg_col
        top = port_df.nlargest(top_n, rank_col)
        deg = top[deg_col].values
        bet = top[bet_col].values
        ports = top["port"].tolist()
        sizes = top[rank_col].values if rank_col in top.columns else np.ones(len(ports)) * 50
        sizes = np.clip(sizes / (sizes.max() or 1) * 200 + 30, 30, 150)
        ax.scatter(deg, bet, s=sizes, alpha=0.7, c=range(len(ports)), cmap="viridis", edgecolor="white")
        for i, p in enumerate(ports):
            ax.annotate(p, (deg[i], bet[i]), fontsize=7, ha="center", va="bottom")
        ax.set_xlabel("Degree centrality")
        ax.set_ylabel("Betweenness centrality")
        title = panel_titles.get(plabel, plabel)
        ax.set_title(f"{title}\nSize ∝ traffic")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.axhline(np.median(bet), color="gray", linestyle="--", alpha=0.5)
        ax.axvline(np.median(deg), color="gray", linestyle="--", alpha=0.5)
    _st = suptitle or "Port Hub vs Bridge: Pre- vs Post-Plague (1709)"
    fig.suptitle(_st, fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
    else:
        plt.show()
