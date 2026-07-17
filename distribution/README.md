# distribution

Bar-chart and tree figures showing how nodes, edges, and predicates are distributed across EC-KG
and its three upstream sources (ROBOKOP, RTX-KG2, PrimeKG).

| Script | Figure(s) | Shows |
|---|---|---|
| `distribution.py` | `distribution_nodes.pdf`, `distribution_edges.pdf` | Node-type and predicate counts across all of EC-KG, one horizontal bar per category/predicate, log-scale x-axis |
| `node_distribution.py` | `node_distribution.pdf` | Node-type counts only — an earlier, wider-format version of the node half of `distribution.py`; kept for reference, `distribution.py` is the current version used in the paper |
| `predicate_distribution.py` | `predicate_distribution.pdf` | Predicate counts laid out against the biolink predicate hierarchy (tree panel + bar panel sharing a y-axis) |
| `upstream_distribution.py` | `upstream_nodes.pdf`, `upstream_edges.pdf`, `upstream_pks.pdf` | Node type / predicate / primary-knowledge-source counts, grouped bar per upstream source |
| `upstream_stacked_bar.py` | `upstream_stacked_bar.pdf` | Same three breakdowns as `upstream_distribution.py`, redrawn as one stacked bar per item (top 15) segmented by upstream source, instead of one grouped bar per source — makes the total and the per-source split both readable at once |

## Data

`distribution.py` and `predicate_distribution.py` read `sankey/category_counts.json` and
`sankey/sankey_agg.csv` — run `sankey/sankey.py` first if those don't exist yet.

`upstream_distribution.py` and `upstream_stacked_bar.py` query `mtrx-hub-dev-3of.release_v0_15_19` on
BigQuery directly, caching each source/table combination under `upstream_cache/*.csv`. Delete a
cache file to force a re-query of just that source/table.

## Run

```bash
python distribution/distribution.py
python distribution/predicate_distribution.py
python distribution/upstream_distribution.py
python distribution/upstream_stacked_bar.py # reuses upstream_distribution.py's cache
```

## Example

```
$ python distribution/upstream_distribution.py
Loading data...
  [cache] ROBOKOP nodes
  ...
Building node type figure...
Saved → distribution/upstream_nodes.pdf
Building predicate figure...
Saved → distribution/upstream_edges.pdf
Building primary knowledge source figure...
Saved → distribution/upstream_pks.pdf
```
