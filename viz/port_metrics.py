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
    from network.analysis import compute_metrics

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
            row[f"degree_{label}"] = m["degree_centrality"].get(port, np.nan)
            row[f"betweenness_{label}"] = m["betweenness_centrality"].get(port, np.nan)
            # Passages through port (in + out)
            passages = 0
            for u, v, data in g.edges(data=True):
                w = data.get("weight", 1)
                if u == port or v == port:
                    passages += w
            row[f"passages_{label}"] = passages if port in g.nodes() else np.nan
        rows.append(row)

    return pd.DataFrame(rows)


def plot_top_ports_comparison(
    port_df: pd.DataFrame,
    graphs: dict,
    top_n: int = 10,
    output_path: str | None = None,
    figsize: tuple[float, float] = (12, 10),
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
    fig.suptitle("Top Ports: Pre- vs Post-Plague (1709) Network Metrics", fontsize=14, fontweight="bold", y=1.02)

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
