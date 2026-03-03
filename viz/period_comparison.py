"""
Professional multipanel figure: pre- vs post-plague network statistics.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# Professional color palette
COLOR_PRE = "#1a365d"   # Dark blue
COLOR_POST = "#9b2c2c"  # Dark red
COLORS = [COLOR_PRE, COLOR_POST]
FONT = "sans-serif"
TITLE_FONTSIZE = 12
LABEL_FONTSIZE = 11


def plot_period_comparison(
    period_metrics: list[dict],
    output_path: str | None = None,
    figsize: tuple[float, float] = (14, 10),
) -> None:
    """
    Create a professional multipanel figure comparing network stats across periods.

    Parameters
    ----------
    period_metrics : list[dict]
        Each dict has: period, n_nodes, n_edges, density, total_passages,
        pct_passages, avg_clustering, avg_betweenness, top_ports, etc.
    output_path : str | None
        Save path.
    figsize : tuple
        Figure size.
    """
    plt.rcParams["font.family"] = FONT
    plt.rcParams["font.size"] = 10

    fig = plt.figure(figsize=figsize, facecolor="white")
    periods = [p["period"] for p in period_metrics]
    x = np.arange(len(periods))
    width = 0.5

    # 2x4 grid: 4 bars top, 2 bars + table bottom
    gs = fig.add_gridspec(2, 4, hspace=0.4, wspace=0.35, left=0.06, right=0.96, top=0.90, bottom=0.08)

    # Row 1: Structural metrics
    ax1 = fig.add_subplot(gs[0, 0])
    bars1 = ax1.bar(x, [p["n_nodes"] for p in period_metrics], width, color=COLORS, edgecolor="white", linewidth=1.2)
    ax1.set_ylabel("Count", fontsize=LABEL_FONTSIZE)
    ax1.set_title("Ports (nodes)", fontsize=TITLE_FONTSIZE, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(periods, fontsize=10)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    for b in bars1:
        ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{int(b.get_height())}", ha="center", va="bottom", fontsize=10)

    ax2 = fig.add_subplot(gs[0, 1])
    bars2 = ax2.bar(x, [p["n_edges"] for p in period_metrics], width, color=COLORS, edgecolor="white", linewidth=1.2)
    ax2.set_ylabel("Count", fontsize=LABEL_FONTSIZE)
    ax2.set_title("Routes (edges)", fontsize=TITLE_FONTSIZE, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(periods, fontsize=10)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    for b in bars2:
        ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + 2, f"{int(b.get_height())}", ha="center", va="bottom", fontsize=10)

    ax3 = fig.add_subplot(gs[0, 2])
    bars3 = ax3.bar(x, [p["total_passages"] for p in period_metrics], width, color=COLORS, edgecolor="white", linewidth=1.2)
    ax3.set_ylabel("Passages", fontsize=LABEL_FONTSIZE)
    ax3.set_title("Total traffic", fontsize=TITLE_FONTSIZE, fontweight="bold")
    ax3.set_xticks(x)
    ax3.set_xticklabels(periods, fontsize=10)
    ax3.spines["top"].set_visible(False)
    ax3.spines["right"].set_visible(False)
    for b in bars3:
        ax3.text(b.get_x() + b.get_width() / 2, b.get_height() + 50, f"{int(b.get_height()):,}", ha="center", va="bottom", fontsize=10)

    ax4 = fig.add_subplot(gs[0, 3])
    bars4 = ax4.bar(x, [p["density"] for p in period_metrics], width, color=COLORS, edgecolor="white", linewidth=1.2)
    ax4.set_ylabel("Density", fontsize=LABEL_FONTSIZE)
    ax4.set_title("Network density", fontsize=TITLE_FONTSIZE, fontweight="bold")
    ax4.set_xticks(x)
    ax4.set_xticklabels(periods, fontsize=10)
    ax4.spines["top"].set_visible(False)
    ax4.spines["right"].set_visible(False)
    for b in bars4:
        ax4.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.001, f"{b.get_height():.3f}", ha="center", va="bottom", fontsize=10)

    # Row 2: Reciprocity, Betweenness, Summary table
    ax5 = fig.add_subplot(gs[1, 0])
    reciprocity = [p.get("reciprocity", 0) or 0 for p in period_metrics]
    bars5 = ax5.bar(x, reciprocity, width, color=COLORS, edgecolor="white", linewidth=1.2)
    ax5.set_ylabel("Reciprocity", fontsize=LABEL_FONTSIZE)
    ax5.set_title("Reciprocity (bidirectional routes)", fontsize=TITLE_FONTSIZE, fontweight="bold")
    ax5.set_xticks(x)
    ax5.set_xticklabels(periods, fontsize=10)
    ax5.spines["top"].set_visible(False)
    ax5.spines["right"].set_visible(False)
    for b in bars5:
        val = b.get_height()
        ax5.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01, f"{val:.3f}", ha="center", va="bottom", fontsize=10)

    ax6 = fig.add_subplot(gs[1, 1])
    avg_betw = [p.get("avg_betweenness", 0) or 0 for p in period_metrics]
    bars6 = ax6.bar(x, avg_betw, width, color=COLORS, edgecolor="white", linewidth=1.2)
    ax6.set_ylabel("Betweenness", fontsize=LABEL_FONTSIZE)
    ax6.set_title("Avg. betweenness centrality", fontsize=TITLE_FONTSIZE, fontweight="bold")
    ax6.set_xticks(x)
    ax6.set_xticklabels(periods, fontsize=10)
    ax6.spines["top"].set_visible(False)
    ax6.spines["right"].set_visible(False)
    for b in bars6:
        val = b.get_height()
        lbl = f"{val:.4f}" if val >= 0.0001 else f"{val:.2e}"
        ax6.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.002, lbl, ha="center", va="bottom", fontsize=10)

    # Summary table (spans 2 cols)
    ax7 = fig.add_subplot(gs[1, 2:])
    ax7.axis("off")
    cell_text = []
    for p in period_metrics:
        row = [
            p["period"],
            str(p["n_nodes"]),
            str(p["n_edges"]),
            f"{p['total_passages']:,.0f}",
            f"{p['pct_passages']:.1f}%",
            f"{p['density']:.4f}",
            f"{p.get('reciprocity', 0) or 0:.3f}",
            f"{p.get('avg_betweenness', 0) or 0:.4f}",
        ]
        cell_text.append(row)
    col_labels = ["Period", "Nodes", "Edges", "Passages", "% total", "Density", "Recip.", "Between."]
    table = ax7.table(
        cellText=cell_text,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
        colColours=["#e2e8f0"] * 8,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.15, 2.4)
    ax7.set_title("Summary", fontsize=TITLE_FONTSIZE, fontweight="bold", pad=10)

    # Legend and main title
    legend_patches = [
        mpatches.Patch(facecolor=COLOR_PRE, edgecolor="white", label="Pre-plague (1705–1708)"),
        mpatches.Patch(facecolor=COLOR_POST, edgecolor="white", label="Post-plague (1710–1713)"),
    ]
    fig.legend(handles=legend_patches, loc="upper center", ncol=2, frameon=False, fontsize=11, bbox_to_anchor=(0.5, 0.97))

    fig.suptitle("Sound Toll Network: Pre- vs Post-Plague (1709) Comparison", fontsize=15, fontweight="bold", y=0.995)

    if output_path:
        plt.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close()
    else:
        plt.show()
