"""
Commodity comparison visualizations.
"""

import matplotlib.pyplot as plt
import pandas as pd


def plot_top_commodities_by_passages(
    commodity_stats: pd.DataFrame,
    output_path: str | None = None,
    top_n: int = 15,
) -> None:
    """
    Bar chart: top commodities by total passages.

    Parameters
    ----------
    commodity_stats : pd.DataFrame
        Must have columns: commodity, total_passages (or period-specific).
        If multiple periods, aggregate or use first period.
    output_path : str | None
        Save figure path.
    top_n : int
        Number of commodities to show.
    """
    if "total_passages" in commodity_stats.columns:
        agg = commodity_stats.groupby("commodity", as_index=False)["total_passages"].sum()
    else:
        # Use first numeric column that looks like passages
        cols = [c for c in commodity_stats.columns if "passage" in c.lower()]
        if cols:
            agg = commodity_stats.groupby("commodity", as_index=False)[cols[0]].sum()
            agg = agg.rename(columns={cols[0]: "total_passages"})
        else:
            raise ValueError("commodity_stats needs total_passages or similar column")

    agg = agg.sort_values("total_passages", ascending=False).head(top_n)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(range(len(agg)), agg["total_passages"], color="#2c5282", alpha=0.8)
    ax.set_yticks(range(len(agg)))
    ax.set_yticklabels(agg["commodity"], fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Total passages", fontsize=12)
    ax.set_title("Top commodities by shipping volume", fontsize=14, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
    else:
        plt.show()
