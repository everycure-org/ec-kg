# CLAUDE.md

## Project overview

This repository contains complementary analysis code to the Every Cure KG publication: technical
validation analyses (`technical_validation/`, `data_record/`) and figure generation scripts
(`sankey/`, `distribution/`, `CoreEntities_sankey/`, `UpstreamData_Venn/`) that produce matplotlib
PDFs for the paper. The `eckg` package must be installed (`pip install -e .`) for the figure
scripts' `eckg` imports to resolve.

## Shared colors

`eckg/colors.py` is the single source of truth for:
- `CATEGORY_COLORS` — biolink category → hex color (60+ entries)
- `_FALLBACK_COLOR` — gray fallback for unknown categories
- `GROUPS` — 8 biolink category group labels and colors
- `NODE_TO_GROUP` — maps every biolink category to one of the 8 groups
- `UPSTREAM_SOURCE_COLORS` — ROBOKOP, RTX-KG2, PrimeKG colors
- `UPSTREAM_REGION_COLORS` — 7 Venn diagram region colors

Do not define these locally in scripts — import from `eckg.colors`.

## Shared style

`eckg/style.py` is the single source of truth for matplotlib styling:
- `RCPARAMS` / `apply_style()` — font, tick, and spine-width rcParams
- `COLUMN_WIDTH_IN` (3.5"), `PAGE_WIDTH_IN` (7.2"), `MAX_HEIGHT_IN` (9.5") — page-size bounds
- `figsize(width, height)` — builds a `(w, h)` tuple, warns if it drifts from the page-size bounds above
- `grid_figsize(nrows, ncols)` — total figsize for a multi-panel `plt.subplots()` grid; always
  `(PAGE_WIDTH_IN, MAX_HEIGHT_IN)` regardless of grid shape, since a grid with `ncols=1` is still a
  full-width montage of stacked panels, not a narrow single-column chart
- `panel_size(nrows, ncols)` — informational per-panel `(width, height)` inside a `grid_figsize()`
  canvas after reserving `BUFFER_IN` (0.2") for each inter-panel gap
- `TITLE_SIZE`, `AXIS_LABEL_SIZE`, `TICK_LABEL_SIZE`, `LEGEND_SIZE`, `ANNOTATION_SIZE` — font-size scale
- `style_title()`, `LEGEND_KWARGS`, `clean_spines()`, `count_formatter()`, `grid_x()`/`grid_y()` — small
  helpers for boilerplate (title styling, legend box, spine removal, k/M axis labels, gridlines) that
  was previously copy-pasted per script and had drifted (tick sizes of 2.0 vs 2.5, title fontsize
  9 vs 10 vs 11, one figure sized 10x12in — taller than a US Letter page)
- `SAVE_DPI` (400) / `savefig(fig, path, tight=True)` — PDF save at `SAVE_DPI`; pass `tight=False` for
  the CoreEntities sankey figures (see below)

Do not define rcParams or figsize numbers locally in scripts — import from `eckg.style`.
`sankey/sankey.py` and the CoreEntities sankey scripts are the exception: their figure geometry is
already dialed in and does not need to move to this module.

## Shared layout

`eckg/grouping.py` provides `group_sorted()`, used by `sankey/sankey.py` and the "full" variant of
`CoreEntities_sankey/{drug,disease}_sankey.py` to order source/target categories so members of the
same `NODE_TO_GROUP` group (e.g. Gene/Protein, SmallMolecule/Drug) sit adjacent to each other,
rather than being interleaved purely by count.

## BigQuery

- Project: `mtrx-hub-dev-3of`
- Dataset: `release_v0_15_19`
- Auth: application default credentials (`gcloud auth application-default login`)
- All figure scripts cache results locally on first run. Delete cache files to re-query.

## Caching locations

| Cache | Written by |
|---|---|
| `sankey/sankey_agg.csv`, `sankey/category_counts.json` | `sankey/sankey.py` |
| `distribution/upstream_cache/*.csv` | `distribution/upstream_distribution.py` (also read by `distribution/upstream_stacked_bar.py`) |
| `UpstreamData_Venn/node_id_venn_counts.csv` | `UpstreamData_Venn/upstream_venn.py` (also read by `UpstreamData_Venn/upstream_upset.py`) |
| `UpstreamData_Venn/edge_triple_venn_counts.csv` | `UpstreamData_Venn/upstream_venn.py` (also read by `UpstreamData_Venn/upstream_upset.py`) |
| `CoreEntities_sankey/drug_sankey_left/right.csv` | `CoreEntities_sankey/drug_sankey.py` |
| `CoreEntities_sankey/disease_sankey_left/right.csv` | `CoreEntities_sankey/disease_sankey.py` |

## Figure conventions

- All figures saved as PDF at `eckg.style.SAVE_DPI` (400) via `eckg.style.savefig()`
- Log-scale x-axis for all distribution bar charts
- `biolink:` prefix stripped from all display labels (`infores:` for PKS)
- Font: Helvetica (`font.family`), with `pdf.fonttype`/`ps.fonttype` set to 42 so text stays editable/searchable in Illustrator instead of being outlined — set via `eckg.style.apply_style()`
- Figure width is `eckg.style.COLUMN_WIDTH_IN` (single-column) or `PAGE_WIDTH_IN` (full-width); height stays under `MAX_HEIGHT_IN` so a figure fits on one page
- `bbox_inches='tight'` omitted (`savefig(..., tight=False)`) for the CoreEntities sankey figures (preserves exact landscape dimensions)

## Illustrator finalization

The PDFs these scripts produce are not the final paper figures — they're assembled and polished in
Adobe Illustrator (panel layout, annotations, final labeling) before submission. The `.ai` source
files for that step are tracked outside this repo for now and will be added in a follow-up
(`IllustratorFigures/`). Because `pdf.fonttype`/`ps.fonttype` are set to 42 (see above), text in the
generated PDFs imports into Illustrator as editable/searchable text rather than outlined paths.
