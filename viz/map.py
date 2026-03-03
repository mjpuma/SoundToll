"""
Cartopy map of Sound Toll ports and routes.

Uses Lambert Conformal projection for the North Sea–Baltic region to minimize
geographical distortion. Ocean and land styling ensures routes appear over water
(FlowingData-style: https://flowingdata.com/2012/05/14/global-shipping-network/).
"""

import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from matplotlib.patches import Circle
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import networkx as nx
import numpy as np


# Standard extents: zoomed-in (North Sea–Baltic only) and zoomed-out (includes Spain)
EXTENT_ZOOMED = (-2, 26, 52, 64)   # North Sea–Baltic only (excludes Spain, UK south)
EXTENT_WIDE = (-15, 40, 35, 70)    # Atlantic to Baltic, includes Spanish ports


def _compute_scale_from_graphs(graphs: list) -> tuple[float, float, float]:
    """
    Compute (node_min, node_max, edge_max) across graphs for cross-period normalization.
    """
    all_node_passages = {}
    edge_max = 0.0
    for G in graphs:
        for u, v, data in G.edges(data=True):
            w = data.get("weight", 1)
            edge_max = max(edge_max, w)
            all_node_passages[u] = all_node_passages.get(u, 0) + w
            all_node_passages[v] = all_node_passages.get(v, 0) + w
    min_p = min(all_node_passages.values()) if all_node_passages else 0
    max_p = max(all_node_passages.values()) if all_node_passages else 1
    return min_p, max_p, edge_max


def plot_map(
    G: nx.DiGraph | nx.Graph,
    output_path: str | None = None,
    extent: tuple[float, float, float, float] = EXTENT_WIDE,
    node_size_scale: float = 1.0,
    edge_alpha: float = 0.5,
    edge_width_scale: float = 0.35,
    geodesic_edges: bool = True,
    highlight_ports: list[str] | None = None,
    label_ports: int | list[str] | None = 40,
    scale_from_graphs: list | None = None,
    show_scale: bool = True,
    figsize: tuple[float, float] = (14, 10),
    title: str = "Sound Toll Shipping Network",
) -> None:
    """
    Plot ports and routes on a North Sea–Baltic map.

    Uses Lambert Conformal projection (centered on Baltic) to reduce distortion
    at high latitudes. Ocean is blue, land is light gray so routes appear over
    water. Edges use geodesic (great-circle) paths for realistic shipping routes.
    Node size is proportional to total passages (in + out) through each port.

    Parameters
    ----------
    G : nx.DiGraph | nx.Graph
        Port network with node attrs 'lat', 'lon' (from build_graph).
    output_path : str | None
        Save figure to this path.
    extent : tuple
        (lon_min, lon_max, lat_min, lat_max). Default: wider North Sea–Baltic–Atlantic.
    node_size_scale : float
        Scale factor for node sizes (applied after passage-based scaling).
    edge_alpha : float
        Transparency of route lines.
    edge_width_scale : float
        Scale factor for edge width (by weight).
    geodesic_edges : bool
        If True, edges follow great-circle paths (over water). If False, straight
        lines in projection (cleaner when zoomed out, less geographically accurate).
    highlight_ports : list[str] | None
        Port names to highlight (e.g. ["Gdansk"]).
    label_ports : int | list[str] | None
        If int: label top N ports by passages. If list: label these ports.
        If None: no labels except highlighted. Default 15.
    scale_from_graphs : list | None
        If provided (e.g. list of period graphs), use combined min/max for node
        and edge scaling so period maps are directly comparable (apples to apples).
    show_scale : bool
        If True, add a legend showing node size and edge width scales.
    figsize : tuple
        Figure size.
    title : str
        Map title.
    """
    # Lambert Conformal Conic: minimizes distortion for North Sea–Baltic
    # Central lon 12, lat 57; standard parallels 52 and 62 cover the region
    projection = ccrs.LambertConformal(
        central_longitude=12,
        central_latitude=57,
        standard_parallels=(52, 62),
    )
    fig, ax = plt.subplots(figsize=figsize, subplot_kw={"projection": projection})

    # Ocean and land first so routes appear over water (FlowingData style)
    ax.add_feature(cfeature.OCEAN, facecolor="#b8d4e8", zorder=0)
    ax.add_feature(cfeature.LAND, facecolor="#e8e4dc", zorder=1)
    ax.coastlines(resolution="50m")
    ax.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.5, zorder=2)
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    lon_min, lon_max, lat_min, lat_max = extent

    # Node positions (filter to extent so zoomed view excludes distant ports)
    pos = {}
    for n in G.nodes():
        lat = G.nodes[n].get("lat")
        lon = G.nodes[n].get("lon")
        if lat is not None and lon is not None and not (np.isnan(lat) or np.isnan(lon)):
            if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
                pos[n] = (lon, lat)

    highlight = set(highlight_ports or [])

    # Passages per node (total flow through port) for size scaling
    node_passages = {n: 0 for n in G.nodes()}
    for u, v, data in G.edges(data=True):
        w = data.get("weight", 1)
        node_passages[u] += w
        node_passages[v] += w

    # Cross-period normalization: use same scale when comparing periods
    if scale_from_graphs:
        ref_min_p, ref_max_p, ref_edge_max = _compute_scale_from_graphs(scale_from_graphs)
        min_p, max_p = ref_min_p, ref_max_p
        max_weight = max(ref_edge_max, 1.0)
    else:
        min_p = min(node_passages.values()) if node_passages else 0
        max_p = max(node_passages.values()) if node_passages else 1
        max_weight = max((G.edges[e].get("weight", 1) for e in G.edges()), default=1)

    size_min, size_max = 8, 28  # larger markers for visibility

    def _node_size(n):
        if max_p <= min_p:
            return (size_min + size_max) / 2
        p = node_passages.get(n, 0)
        return size_min + (p - min_p) / (max_p - min_p) * (size_max - size_min)

    # Which ports to label
    if isinstance(label_ports, int):
        to_label = set(
            p for p, _ in sorted(node_passages.items(), key=lambda x: -x[1])[:label_ports]
        )
    elif isinstance(label_ports, list):
        to_label = set(label_ports)
    else:
        to_label = set()

    # Edges: geodesic (great-circle) paths so routes follow actual shipping paths over water
    for u, v, data in G.edges(data=True):
        if u in pos and v in pos:
            w = data.get("weight", 1)
            width = max(0.4, w / max_weight * 3 * edge_width_scale)
            edge_crs = ccrs.Geodetic() if geodesic_edges else ccrs.PlateCarree()
            ax.plot(
                [pos[u][0], pos[v][0]],
                [pos[u][1], pos[v][1]],
                transform=edge_crs,
                color="#2c5282",
                alpha=edge_alpha,
                linewidth=width,
                zorder=3,
            )

    # Nodes: size proportional to passages, white outline for visibility over water
    for n, (lon, lat) in pos.items():
        is_highlight = n in highlight
        color = "#c53030" if is_highlight else "#2d3748"
        size = _node_size(n) * node_size_scale
        size = size * 1.2 if is_highlight else size
        ax.plot(
            lon, lat, "o",
            color=color,
            markersize=size,
            markeredgecolor="white",
            markeredgewidth=1,
            transform=ccrs.PlateCarree(),
            zorder=5,
        )
        if is_highlight or n in to_label:
            txt = ax.text(
                lon, lat, f"  {n}",
                fontsize=10 if not is_highlight else 11,
                fontweight="bold" if is_highlight else "normal",
                ha="left",
                va="center",
                transform=ccrs.PlateCarree(),
                zorder=10,  # above edges (3) and nodes (5) so labels stay readable
            )
            # White stroke makes text readable over edges without blocking data
            txt.set_path_effects([
                path_effects.Stroke(linewidth=2, foreground="white"),
                path_effects.Normal(),
            ])

    ax.set_title(title, fontsize=16)

    # Scale legend: use VISIBLE nodes only so legend matches what's on the map
    if show_scale:
        visible_passages = [node_passages[n] for n in pos if n in node_passages]
        leg_min_p = min(visible_passages) if visible_passages else min_p
        leg_max_p = max(visible_passages) if visible_passages else max_p

        legend_ax = ax.inset_axes([0.02, 0.72, 0.2, 0.2])  # square for equal aspect
        legend_ax.set_facecolor("white")
        legend_ax.patch.set_alpha(1.0)
        legend_ax.patch.set_edgecolor("#cccccc")
        legend_ax.patch.set_linewidth(1)
        legend_ax.set_aspect("equal")
        legend_ax.set_xlim(0, 1)
        legend_ax.set_ylim(0, 1)
        legend_ax.axis("off")

        # Node scale: values from visible range; sizes match map (same _node_size formula)
        node_vals = [int(leg_min_p), int((leg_min_p + leg_max_p) / 2), int(leg_max_p)] if leg_max_p > leg_min_p else [int(leg_min_p)] * 3
        if max_p > min_p:
            legend_sizes = [
                size_min + (leg_min_p - min_p) / (max_p - min_p) * (size_max - size_min),
                size_min + ((leg_min_p + leg_max_p) / 2 - min_p) / (max_p - min_p) * (size_max - size_min),
                size_min + (leg_max_p - min_p) / (max_p - min_p) * (size_max - size_min),
            ]
        else:
            legend_sizes = [(size_min + size_max) / 2] * 3
        for i, (val, sz) in enumerate(zip(node_vals, legend_sizes)):
            legend_ax.scatter(0.12, 0.88 - i * 0.28, s=sz**2, c="#2d3748", ec="white", linewidths=1,
                             transform=legend_ax.transAxes, zorder=10)
            legend_ax.text(0.34, 0.88 - i * 0.28, f"{val:,}", fontsize=10, va="center", transform=legend_ax.transAxes)
        legend_ax.text(0.14, 1.02, "Node size (port traffic)", fontsize=11, fontweight="bold", transform=legend_ax.transAxes)

        # Edge scale: thinner lines
        edge_vals = [10, max(10, int(max_weight * 0.4)), int(max_weight)]
        edge_lws = [1, 2.5, 4]
        for i, (val, lw) in enumerate(zip(edge_vals, edge_lws)):
            legend_ax.plot([0.55, 0.92], [0.5 - i * 0.28, 0.5 - i * 0.28], color="#2c5282", lw=lw, alpha=0.9, solid_capstyle="round", transform=legend_ax.transAxes)
            legend_ax.text(0.94, 0.5 - i * 0.28, f"{val:,}", fontsize=10, va="center", ha="left", transform=legend_ax.transAxes)
        legend_ax.text(0.73, 0.78, "Route traffic", fontsize=11, fontweight="bold", ha="center", transform=legend_ax.transAxes)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
    else:
        plt.show()


def plot_map_from_df(
    df,
    output_path: str | None = None,
    extent: tuple[float, float, float, float] = (-5, 30, 50, 65),
) -> None:
    """
    Convenience: build graph from DataFrame and plot map.
    """
    from network.analysis import build_graph

    G = build_graph(df, directed=True, include_node_attrs=True)
    plot_map(G, output_path=output_path, extent=extent, highlight_ports=["Gdansk"])
