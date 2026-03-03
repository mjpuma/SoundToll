# SoundToll Network Analysis

Network analyses on the [Sound Toll Registers Online (STRO)](https://www.soundtoll.nl/)—the toll which the kings of Denmark levied on shipping through the Sound, the main connection between the North Sea and the Baltic Sea.

## Research Context

This project complements regression-based work (e.g., 4OCEANS) by focusing on **graph-theoretic network characteristics**: centrality, clustering, connectivity, and their evolution over time. A key research question: **did the 1709 Baltic plague affect shipping routes and network structure?**

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

This generates:

- **Maps**: `outputs/soundtoll_map.png` (full period), `outputs/soundtoll_map_1705-1708.png`, `outputs/soundtoll_map_1710-1713.png`
- **Network diagram**: `outputs/soundtoll_network.png`
- **Period comparison**: `outputs/period_comparison.png`, `outputs/period_comparison.csv`

See [OUTPUTS.md](OUTPUTS.md) for detailed captions for each output.

## Output Captions

| Output | Caption |
|--------|---------|
| **soundtoll_map.png** | Sound Toll shipping network, 1700–1720. Directed port-to-port routes through the Danish Sound. Node size ∝ total passages; edge width ∝ route traffic. Lambert Conformal projection; geodesic paths. Gdansk highlighted. Routes with &lt;5 passages excluded. |
| **soundtoll_map_1705-1708.png** | Pre-plague network (1705–1708). Same node/edge scale as post-plague map for direct comparison. |
| **soundtoll_map_1710-1713.png** | Post-plague network (1710–1713). Same node/edge scale as pre-plague map for direct comparison. |
| **soundtoll_network.png** | Abstract network diagram, 1700–1720. Geographic layout; top ~80 ports. |
| **period_comparison.png** | Pre- vs post-plague: nodes, edges, total passages, network density. Post-plague shows fewer ports/routes but higher density. |
| **period_comparison.csv** | Period metrics: n_nodes, n_edges, density, total_passages, pct_passages, max_route_passages, top_ports. |

## Programmatic Usage

```python
from data.loader import load_soundtoll
from filters.filter import filter_data
from network.analysis import build_graph, compute_metrics, build_graphs_by_period
from viz.map import plot_map

df = load_soundtoll("2602_soundtoll_with_radii.csv")
df_filtered = filter_data(df, year_min=1700, year_max=1720)
G = build_graph(df_filtered, directed=True, min_passages=5)
metrics = compute_metrics(G)

# Period comparison with cross-period normalization
periods = [(1705, 1708), (1710, 1713)]
graphs = build_graphs_by_period(df_filtered, periods=periods, directed=True, min_passages=5)
plot_map(graphs["1705-1708"], output_path="pre.png", scale_from_graphs=list(graphs.values()))
plot_map(graphs["1710-1713"], output_path="post.png", scale_from_graphs=list(graphs.values()))
```

## Project Structure

```
SoundToll/
├── data/loader.py       # Load CSV with selected columns
├── filters/filter.py    # Year, radii, region filters
├── network/analysis.py  # Graph build, centrality, clustering
├── viz/map.py           # Cartopy map (Lambert Conformal, geodesic paths)
├── viz/network_plot.py  # Abstract network diagrams
├── main.py              # Orchestration script
├── OUTPUTS.md           # Detailed captions for each output
└── outputs/             # Figures and summary tables (generated)
```

## Mapping Details

- **Projection**: Lambert Conformal Conic (centered on North Sea–Baltic) to minimize distortion
- **Edges**: Geodesic (great-circle) paths by default; optional straight lines in projection
- **Node size**: Proportional to total passages
- **Edge width**: Proportional to route traffic
- **Cross-period normalization**: Period maps use the same scale for direct comparison

## License

MIT
