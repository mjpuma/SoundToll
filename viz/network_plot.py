"""
Network diagram visualization (non-geographic layout).
"""

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np


def plot_network(
    G: nx.DiGraph | nx.Graph,
    output_path: str | None = None,
    layout: str = "geographic",
    node_size_scale: float = 500,
    edge_width_scale: float = 0.5,
    highlight_ports: list[str] | None = None,
    max_nodes: int | None = 100,
    figsize: tuple[float, float] = (14, 10),
) -> None:
    """
    Plot network with node size by degree, edge width by weight.

    Parameters
    ----------
    G : nx.DiGraph | nx.Graph
        Port network.
    output_path : str | None
        Save figure path.
    layout : str
        "geographic" (use lat/lon), "spring", or "kamada_kawai".
    node_size_scale : float
        Scale for node sizes (by degree).
    edge_width_scale : float
        Scale for edge widths (by weight).
    highlight_ports : list[str] | None
        Ports to highlight (e.g. Gdansk, 500km radius ports).
    max_nodes : int | None
        If set, keep only top max_nodes by degree (for readability).
    figsize : tuple
        Figure size.
    """
    if max_nodes is not None and G.number_of_nodes() > max_nodes:
        degrees = dict(G.degree())
        top = sorted(degrees, key=degrees.get, reverse=True)[:max_nodes]
        G = G.subgraph(top).copy()

    pos = _get_layout(G, layout)

    fig, ax = plt.subplots(figsize=figsize)

    degrees = dict(G.degree(weight="weight"))
    max_deg = max(degrees.values()) or 1
    node_sizes = [node_size_scale * (degrees.get(n, 0) / max_deg + 0.2) for n in G.nodes()]

    highlight = set(highlight_ports or [])
    node_colors = ["red" if n in highlight else "steelblue" for n in G.nodes()]

    max_weight = max((G.edges[e].get("weight", 1) for e in G.edges()), default=1)
    widths = [max(0.3, G.edges[u, v].get("weight", 1) / max_weight * 3 * edge_width_scale) for u, v in G.edges()]

    nx.draw_networkx_edges(
        G,
        pos,
        width=widths,
        alpha=0.4,
        edge_color="gray",
        ax=ax,
        arrows=G.is_directed(),
        arrowsize=10,
    )
    nx.draw_networkx_nodes(
        G,
        pos,
        node_size=node_sizes,
        node_color=node_colors,
        alpha=0.8,
        ax=ax,
    )

    # Labels only for highlighted or high-degree nodes
    label_nodes = highlight or [n for n in G.nodes() if degrees.get(n, 0) >= np.percentile(list(degrees.values()), 90)]
    labels = {n: n for n in label_nodes if n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=8, ax=ax)

    ax.set_title("Sound Toll Shipping Network")
    ax.axis("off")
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
    else:
        plt.show()


def _get_layout(G: nx.DiGraph | nx.Graph, layout: str) -> dict:
    """Compute node positions."""
    if layout == "geographic":
        pos = {}
        for n in G.nodes():
            lat = G.nodes[n].get("lat")
            lon = G.nodes[n].get("lon")
            if lat is not None and lon is not None and not (np.isnan(lat) or np.isnan(lon)):
                pos[n] = (lon, lat)
            else:
                pos[n] = (0, 0)
        if len(pos) < G.number_of_nodes():
            fallback = nx.spring_layout(G, k=2, seed=42)
            for n in G.nodes():
                if n not in pos:
                    pos[n] = fallback[n]
        return pos
    elif layout == "spring":
        return nx.spring_layout(G, k=2, seed=42)
    elif layout == "kamada_kawai":
        return nx.kamada_kawai_layout(G)
    else:
        return nx.spring_layout(G, k=2, seed=42)
