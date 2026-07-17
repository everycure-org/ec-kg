
# eckg

Shared library imported by every figure script in this repo (`sankey/`, `distribution/`,
`CoreEntities_sankey/`, `UpstreamData_Venn/`). No figures are generated here directly — this
package only holds constants and helpers that would otherwise be copy-pasted (and drift) across
scripts. Install it in editable mode before running any figure script:

```bash
pip install -e .
```

## Modules

| Module | Provides |
|---|---|
| `colors.py` | `CATEGORY_COLORS` (biolink category → hex color), `GROUPS` (the 8 category-group labels/colors), `NODE_TO_GROUP` (category → group), `UPSTREAM_SOURCE_COLORS` (ROBOKOP/RTX-KG2/PrimeKG), `UPSTREAM_REGION_COLORS` (Venn region blends), `_FALLBACK_COLOR` (gray, for any category not yet classified) |
| `style.py` | `apply_style()` / `RCPARAMS` (fonts, tick/spine widths), `figsize()` / `grid_figsize()` / `panel_size()` (page-size-aware figure dimensions), the `TITLE_SIZE`/`AXIS_LABEL_SIZE`/`TICK_LABEL_SIZE`/`LEGEND_SIZE`/`ANNOTATION_SIZE` font scale, and small helpers (`style_title()`, `LEGEND_KWARGS`, `clean_spines()`, `count_formatter()`, `grid_x()`/`grid_y()`, `savefig()`) |
| `grouping.py` | `group_sorted()` and `group_gaps()` — order/space a list of categories so members of the same `NODE_TO_GROUP` group sit adjacent to each other, used by the sankey scripts |

## Example

```python
from eckg import style
from eckg.colors import CATEGORY_COLORS, _FALLBACK_COLOR

style.apply_style()
fig, ax = plt.subplots(figsize=style.figsize(style.COLUMN_WIDTH_IN, 5.0))
ax.barh(y, counts, color=[CATEGORY_COLORS.get(c, _FALLBACK_COLOR) for c in categories])
style.clean_spines(ax)
style.savefig(fig, "my_figure.pdf")
```

See `../CLAUDE.md` for the full conventions these modules encode (page-size bounds, DPI, font
handling for Illustrator, etc).
