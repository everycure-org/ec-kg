# UpstreamData_Venn

Overlap figures across the three upstream sources (ROBOKOP, RTX-KG2, PrimeKG): which node types,
primary knowledge sources, node IDs, and edge triples are shared vs. source-specific.

| Script | Figures | Form |
|---|---|---|
| `upstream_venn.py` | `upstream_venn_nodes.pdf`, `upstream_venn_pks.pdf`, `upstream_venn_node_ids.pdf`, `upstream_venn_edge_triples.pdf` | Classic 3-circle Venn diagrams |
| `upstream_upset.py` | `upstream_upset.pdf` | UpSet-style replacement for the same four diagrams (3-panel figure: bar per source-combination + membership matrix below) — used where a Venn's overlapping regions get too cramped to label |

## What they show

- **Node types** / **primary knowledge sources**: set overlap — does ROBOKOP's node type vocabulary
  overlap with RTX-KG2's, etc. Small regions (≤14 items) list the item names directly; larger
  regions show just a count.
- **Node IDs** / **edge triples**: count overlap — of all node IDs (or unique subject-predicate-object
  triples) across the three sources, how many are unique to one source vs. shared.

Region colors (`eckg.colors.UPSTREAM_REGION_COLORS`) are consistent between the Venn and UpSet
versions, and match each source's own color elsewhere in the paper.

## Data

- Node type / PKS sets are read from `distribution/upstream_cache/*.csv` — run
  `distribution/upstream_distribution.py` first if those don't exist yet.
- Node ID / edge triple counts require a dedicated BigQuery membership query (`LOGICAL_OR` over each
  source's ID/triple sets), cached here as `node_id_venn_counts.csv` and
  `edge_triple_venn_counts.csv`. These queries scan the full node/edge tables and can take several
  minutes on a cache miss.
- `upstream_upset.py` reuses `upstream_venn.py`'s cache and loaders directly — run either script
  first, or just run `upstream_upset.py` on its own.

## Run

```bash
python UpstreamData_Venn/upstream_venn.py
python UpstreamData_Venn/upstream_upset.py
```

## Example

```
$ python UpstreamData_Venn/upstream_venn.py
Node types:
  ROBOKOP: 30 nodes
  RTX-KG2: 59 nodes
  PrimeKG: 10 nodes
Saved → upstream_venn_nodes.pdf
...
Node IDs:
  [cache] node ID venn counts
  ROBOKOP only: 2,536,891
  ...
Saved → upstream_venn_node_ids.pdf
```
