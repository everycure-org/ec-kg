# CoreEntities_sankey

Sankey diagrams centered on Every Cure's core drug and disease lists, showing what node types
connect to them on either side (as subject and as object).

| Script | Figures |
|---|---|
| `drug_sankey.py` | `drug_sankey_full.pdf` (one bar per node type), `drug_sankey_grouped.pdf` (node types collapsed into the 8 biolink category groups) |
| `disease_sankey.py` | `disease_sankey_full.pdf`, `disease_sankey_grouped.pdf` — same layout, for the disease list |

## What they show

A single center block ("EC Drug List" / "EC Disease List") with two ribbon columns: node types
that point to it (left) and node types it points to (right), each colored by
`eckg.colors.CATEGORY_COLORS` (or by category group in the `_grouped` variant). Ribbon width is
proportional to edge count, log-scaled opacity so dominant flows stand out. These are landscape
half-page panels (3.5 x 3.0 in) sized to sit side by side in the paper, not full-page figures.

## Data

Each script queries `mtrx-hub-dev-3of.release_v0_15_19` on BigQuery (`edges_unified` joined against
`drug_list_nodes_normalized` / `disease_list_nodes_normalized`), caching results as
`{drug,disease}_sankey_{left,right}.csv` (left = incoming edges, right = outgoing edges). Delete
those CSVs to force a re-query.

## Run

```bash
python CoreEntities_sankey/drug_sankey.py
python CoreEntities_sankey/disease_sankey.py
```

## Example

```
$ python CoreEntities_sankey/drug_sankey.py
Loading cached data...
  44 source types | EC Drug List | 47 target types
Saved CoreEntities_sankey/drug_sankey_full.pdf
  8 source groups | EC Drug List | 8 target groups
Saved CoreEntities_sankey/drug_sankey_grouped.pdf
```
