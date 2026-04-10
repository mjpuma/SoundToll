# Sound Toll network metrics — definitions for time-series CSVs

This document accompanies **`network_timeseries_year_all_goods.csv`** and **`network_timeseries_year_season_all_goods.csv`**.

**What is being measured?** Each row is one **shipping network** for a calendar year (or one year × one season). Ports are dots; directed routes between them are lines whose thickness in the data is the **number of voyages** recorded in the Sound Toll registers. Metrics describe how **big**, **dense**, **two-way**, and **central** that network is.

**Commodities:** These files are **commodity-aggregated**: all cargoes are lumped together. Each route’s weight is **total passages** across all goods. They are **not** split by commodity. Per-commodity networks require the separate commodity pipeline in this project.

**Software:** Python 3, `pandas`, `networkx` (see `requirements.txt`). Unless stated, definitions match NetworkX.

**Default export settings:** Years **1668–1800**. **Annual** graphs drop edges with **fewer than 5** total passages in that year; **year×season** graphs use **fewer than 1** (i.e. drop only empty routes).

---

## How to read this document

For each topic you get:

- **Plain language** — intuition in words.
- **Formal** — graph notation and formulas as implemented.

Notation: directed graph \(G=(V,E)\), \(n = |V|\), \(m = |E|\). Edge weight on \((u,v)\) is \(w_{uv} \ge 0\) (sum of `num_passages`). Undirected skeleton \(G_u\) ignores arrow direction (one undirected edge if either direction exists; see NetworkX `Graph(DiGraph)` for how parallel directions merge).

---

## 1. Graph definition (every row)

### Plain language

- A **node** is a **port** that appears at least once as departure or destination on a remaining edge after filtering.
- A **directed edge** \(u \to v\) means we observe traffic from port \(u\) to port \(v\) in that year (or year×season). The **weight** is how many voyages that represents—**all commodities added up**.
- **Filtering:** Very weak routes are dropped so noise does not dominate (thresholds above). If almost nothing is left, some summary columns can be missing (`NaN`).

### Formal

- \(G\) is a **simple directed graph** with at most one edge per ordered pair \((u,v)\); weight \(w_{uv}\) aggregates `num_passages`.
- **Annual file:** subgraph induced by rows with `Year = y`.
- **Year×season file:** subgraph induced by rows with `Year = y` and `Season_Num = s`.

---

## 2. Size and volume columns

| Column | Plain language | Formal |
|--------|----------------|--------|
| `year` | Which calendar year this row describes. | Integer year \(y\). |
| `season` | Which quarter of the sailing year (STRO coding 1–4). | Integer \(s \in \{1,2,3,4\}\); year×season file only. |
| `season_name` | Human label (Winter / Spring / Summer / Autumn). | Mapping from STRO season codes. |
| `network_n_nodes` | How many distinct ports show up in the network after filtering. | \(n = \|V\|\). |
| `network_n_edges` | How many directed routes remain after filtering. | \(m = \|E\|\) (count of directed edges with positive weight after aggregation). |
| `network_total_passages` | Total voyage count in the graph: sum of traffic on all routes. | \(\sum_{(u,v)\in E} w_{uv}\). |
| `edges_per_node` | Rough “how many routes per port” at a glance (not the same as graph-theoretic degree). | \(m / n\) for \(n>0\); else undefined (`NaN`). |

---

## 3. `network_density`

### Plain language

**Density** is “out of all possible port-to-port connections we could have written down, what fraction actually have at least one route this year?” Higher means the network fills more of the possible directed ties (still usually a **small** number for real oceans shipping).

### Formal (directed graph)

Let \(n \ge 2\). The maximum number of **ordered** pairs of distinct ports is \(n(n-1)\).  

\[
\text{density} = \frac{m}{n(n-1)}
\]

If \(n < 2\), density is \(0\) in the implementation. This matches **NetworkX**’s notion for directed graphs (possible edges in the denominator).

---

## 4. `network_reciprocity`

### Plain language

**Reciprocity** measures how much traffic runs **both ways** on a corridor: if many routes are one-way only, reciprocity is lower; if A→B and B→A both appear a lot, reciprocity is higher.

### Formal

Computed with **NetworkX** `nx.reciprocity(G)` on the **weighted directed** graph \(G\). NetworkX defines reciprocity as a property of how directed edges participate in **2-cycles** (mutual A⇄B pairs); see the NetworkX documentation for the exact fraction used with weighted graphs.

---

## 5. Centrality columns (mean, std, max)

### Plain language

- **Degree centrality (per port):** “How many distinct partners does this port touch, compared to everyone else?” A port that connects to many others scores high.
- **Betweenness centrality (per port):** “How often do shortest paths (by voyage weights) between other ports **pass through** this port?” A hub that lies on many shortest routes scores high.
- The CSV then **averages** degree and betweenness across all ports (**each port counts once**), and reports **standard deviation** and **maximum** of betweenness to show spread and bottlenecks.

### Formal

Let \(N = n\) be the number of nodes.

- **Degree centrality** (NetworkX, `nx.degree_centrality(G)`): for node \(v\),

  \[
  C_D(v) = \frac{d(v)}{N-1}
  \]

  where \(d(v)\) is the **total** degree in the directed graph (in-degree + out-degree) as NetworkX defines it for `DiGraph`.

- **Betweenness centrality** (NetworkX, `nx.betweenness_centrality(G, weight="weight")`): for node \(v\),

  \[
  C_B(v) = \sum_{s \neq v \neq t} \frac{\sigma_{st}(v)}{\sigma_{st}}
  \]

  where \(\sigma_{st}\) is the number of shortest paths (by **weighted** length) from \(s\) to \(t\), and \(\sigma_{st}(v)\) is how many of those pass through \(v\). (Convention for endpoints and normalization follows NetworkX.)

- **CSV aggregates** (unweighted over nodes):

  - `mean_degree_centrality` \(= \frac{1}{n} \sum_v C_D(v)\)
  - `mean_betweenness_centrality` \(= \frac{1}{n} \sum_v C_B(v)\)
  - `std_betweenness_centrality` — population std of \(\{C_B(v)\}\) (ddof \(=0\)).
  - `max_betweenness_centrality` \(= \max_v C_B(v)\).

---

## 6. Clustering columns (`mean_square_clustering`, `mean_triangle_clustering`)

Both are computed on the **undirected** skeleton \(G_u = \texttt{nx.Graph}(G)\) (arrows dropped; see NetworkX for merging opposite directions).

### Plain language — triangles (`mean_triangle_clustering`)

**Triangle clustering** asks: among ports A and B that both connect to C, how often is there also a direct tie between A and B? In this **aggregate** shipping network there are usually **no such triangles** (you rarely see all three legs A–B, B–C, A–C in the same slice), so this mean is often **0** for every year. That is a **structural** fact, not an error.

### Formal — triangles

Local clustering \(C_\triangle(v)\) is NetworkX `nx.clustering(G_u, weight="weight")` (see `network/analysis.py`).  

`mean_triangle_clustering` \(= \frac{1}{n}\sum_v C_\triangle(v)\).

### Plain language — squares (`mean_square_clustering`)

**Square clustering** measures a different kind of “clumpiness”: it looks at **four-node patterns** (shared neighbors / squares) and can be **positive** even when triangle clustering is all zeros. For shipping, it is usually the **more informative** cohesion column in these files.

### Formal — squares

`mean_square_clustering` \(= \frac{1}{n}\sum_v C_4(v)\) where \(C_4\) is NetworkX `nx.square_clustering(G_u)` (unweighted; see NetworkX for the precise local square coefficient).

---

## 7. Annual vs year×season files

| File | Plain language | Formal |
|------|----------------|--------|
| `network_timeseries_year_all_goods.csv` | One network per **year**; all goods. | One graph per \(y\) from rows with `Year = y`. |
| `network_timeseries_year_season_all_goods.csv` | One network per **year and season**; all goods. | One graph per \((y,s)\) from rows with `Year = y` and `Season_Num = s`. |

Use the annual file when your analysis is indexed by calendar year; use year×season if you care about within-year seasonality.

---

## 8. Superposed epoch analysis (SEA)

**Plain language:** SEA lines up your metric (e.g. density) in **windows** around chosen **event years** (wars, plague, climate events) and compares average behaviour before vs during vs after. The CSV does **not** choose events for you—it only supplies the **yearly** (or year×season) series.

**Formal:** Let \(x_y\) be any column and \(\mathcal{E}\) a set of event years. Analyst-defined windows (e.g. \(y \in \{e-5,\ldots,e+5\}\)) produce composites; implementation is in your statistics code (R, Python, etc.).

---

## 9. File checklist to share

- `network_timeseries_year_all_goods.csv`
- `network_timeseries_year_season_all_goods.csv`
- This file: `NETWORK_METRICS_DEFINITIONS.md`

Defaults: **1668–1800**, **&lt;5** passages threshold for annual edges, **&lt;1** for year×season (unless you override in the export script).
