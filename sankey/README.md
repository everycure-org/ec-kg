# sankey

Full EC-KG edge-flow Sankey diagram: source category → predicate → target category.

| Script | Figure |
|---|---|
| `sankey.py` | `sankey.pdf` — three-column Sankey (source categories, predicates, target categories), ribbon width proportional to edge count |

## What it shows

Every biolink category flows into a predicate column, which flows into a target category column.
Source/target categories are grouped adjacent to each other by biolink category group (see
`eckg.colors.NODE_TO_GROUP`, e.g. Gene next to Protein) rather than sorted purely by count, with a
legend for the 8 groups at the bottom of the figure. Categories that contribute less than 0.5% of
edges as both a source and a target — plus anything already classified as Miscellaneous — are
folded into a single "Miscellaneous" bar so the diagram stays readable; a category significant in
either role keeps its own bar.

## Data

Reads `nodes_unified` / `edges_unified` from `mtrx-hub-dev-3of.release_v0_15_19` on BigQuery, cached
locally as `sankey_agg.csv` (aggregated source/predicate/target triples) and `category_counts.json`
(per-category node counts). `distribution/distribution.py` and `distribution/predicate_distribution.py`
also read these two cache files, so run this script first if starting from scratch. Delete the cache
files to force a re-query.

## Run

```bash
python sankey/sankey.py
```

## Example

```
$ python sankey/sankey.py
Loading cached data...
  13,047 triples, 58 categories
  Folding 29 additional categories into Miscellaneous (< 0.5% of edges as both source AND target):
    ...
  20 src | 91 pred | 20 tgt
Saved sankey/sankey.pdf
```
