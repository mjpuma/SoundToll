# SoundToll Network Analysis

Network analyses on the [Sound Toll Registers Online (STRO)](https://www.soundtoll.nl/)—the toll which the kings of Denmark levied on shipping through the Sound, the main connection between the North Sea and the Baltic Sea.

## Research Context

This project complements regression-based work (e.g., 4OCEANS) by focusing on **graph-theoretic network characteristics**: centrality, clustering, connectivity, reciprocity, and their evolution over time. A key research question: **did the 1709 Baltic plague affect shipping routes and network structure?**

We compare pre-plague (1705–1708) and post-plague (1710–1713) periods using directed graphs, multi-year windows, and cross-period normalization so visualizations are directly comparable (apples to apples).

## Data

The analysis uses `2602_soundtoll_with_radii.csv` (~300+ MB), which includes:

- **Network**: departure, destination, route, num_passages
- **Geography**: lat/lon, distance from Gdansk, radii flags (200/500/700/1300 km)
- **Time**: Year (1565–1857), Season_Num
- **Context**: plague indicators, climate variables, regions

The data file is not on GitHub due to size; place it in the project root locally.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

## Outputs

| Output | Description |
|--------|--------------|
| `soundtoll_map_zoom.png`, `soundtoll_map_wide.png` | Full-period maps (1700–1720) |
| `soundtoll_map_{period}_zoom.png`, `soundtoll_map_{period}_wide.png` | Period-specific maps (1705–1708, 1710–1713) |
| `soundtoll_network.png` | Abstract network diagram |
| `period_comparison.png`, `period_comparison.csv` | Network-level before/after stats |
| `port_network_stats.csv` | Port-level metrics (degree, betweenness, passages) |
| `top_ports_comparison.png` | Bar plots: top 10 ports by degree, betweenness, traffic |

---

## Figure Captions and Computation Details

### Map figures (`*_zoom.png`, `*_wide.png`)

**Scaling and range:**
- **Node size**: Proportional to total passages (in + out) through each port. Linear scale: `size = size_min + (p - min_p) / (max_p - min_p) * (size_max - size_min)` with `size_min=8`, `size_max=28` (points). For period maps, `min_p` and `max_p` are computed across both periods (cross-period normalization).
- **Edge width**: Proportional to route traffic (passages per route). Formula: `width = max(0.4, w / max_weight * 3 * edge_width_scale)` with `edge_width_scale=0.35`.
- **Legend**: Node and edge scales in the legend use the **visible** range only (ports within the map extent). Legend circle sizes match the map markers via the same scaling formula.
- **Extents**: Zoomed `(-2, 26, 52, 64)` lon/lat (North Sea–Baltic); wide `(-15, 40, 35, 70)` (includes Spanish ports). Ports outside the extent are excluded from the map.
- **Filtering**: Routes with fewer than 5 passages excluded; directed graph.

**Caption:** Sound Toll shipping network. Directed port-to-port routes through the Danish Sound. Node size ∝ total passages; edge width ∝ route traffic. Lambert Conformal projection (central lon 12°, lat 57°); geodesic (great-circle) paths. Gdansk highlighted. Top 40 ports by passages labeled. Data: STRO.

---

### Period comparison (`period_comparison.png`)

**Computation:**
- **Nodes**: Count of unique ports.
- **Edges**: Count of unique routes (departure–destination pairs).
- **Total passages**: Sum of `num_passages` over all edges.
- **Density**: `m / (n*(n-1))` for directed graphs.
- **Reciprocity**: Fraction of edges that have a reverse edge (bidirectional routes). `nx.reciprocity(G)`.
- **Avg. betweenness**: Mean of `nx.betweenness_centrality(G, weight="weight")` over nodes.

**Caption:** Pre-plague (1705–1708) vs post-plague (1710–1713) network comparison. Panels: ports, routes, total passages, density, reciprocity, betweenness centrality. Summary table includes % of total passages. Data: STRO.

---

### Top ports comparison (`top_ports_comparison.png`)

**Computation:**
- Ports ranked by pre-plague metric; bars show pre vs post values.
- **Degree centrality**: `nx.degree_centrality(G)` (fraction of possible connections).
- **Betweenness centrality**: `nx.betweenness_centrality(G, weight="weight")`.
- **Passages**: Sum of edge weights for edges incident to each port.

**Caption:** Top 10 ports by degree, betweenness, and traffic (pre-plague rank). Grouped bars: pre-plague (1705–1708) vs post-plague (1710–1713). Data: STRO.

---

### Port network stats (`port_network_stats.csv`)

**Columns:** `port`, `degree_{period}`, `betweenness_{period}`, `passages_{period}` for each period. Ports in either period included; missing values as NaN.

---

## Programmatic Usage

```python
from data.loader import load_soundtoll
from filters.filter import filter_data
from network.analysis import build_graph, compute_metrics, build_graphs_by_period
from viz.map import plot_map, EXTENT_ZOOMED, EXTENT_WIDE

df = load_soundtoll("2602_soundtoll_with_radii.csv")
df_filtered = filter_data(df, year_min=1700, year_max=1720)
G = build_graph(df_filtered, directed=True, min_passages=5)
metrics = compute_metrics(G)

# Period comparison with cross-period normalization
periods = [(1705, 1708), (1710, 1713)]
graphs = build_graphs_by_period(df_filtered, periods=periods, directed=True, min_passages=5)
plot_map(graphs["1705-1708"], output_path="pre.png", extent=EXTENT_ZOOMED,
         scale_from_graphs=list(graphs.values()))
plot_map(graphs["1710-1713"], output_path="post.png", extent=EXTENT_ZOOMED,
         scale_from_graphs=list(graphs.values()))
```

## Project Structure

```
SoundToll/
├── data/loader.py           # Load CSV with selected columns
├── filters/filter.py        # Year, radii, region filters
├── network/analysis.py      # Graph build, centrality, reciprocity
├── viz/map.py               # Cartopy map (Lambert Conformal, geodesic paths)
├── viz/network_plot.py      # Abstract network diagrams
├── viz/period_comparison.py # Multipanel before/after stats
├── viz/port_metrics.py      # Port-level table and bar plots
├── main.py                  # Orchestration script
├── OUTPUTS.md               # Extended captions
└── outputs/                 # Figures and tables (generated)
```

## License

MIT
