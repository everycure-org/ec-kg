# Shared matplotlib style for EC-KG paper figures.

import warnings

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ── rcParams ─────────────────────────────────────────────────────────────────
RCPARAMS = {
    "font.family":       "Helvetica",
    "pdf.fonttype":      42,   # keep text editable/searchable in Illustrator
    "ps.fonttype":       42,
    "font.size":         7,
    "axes.linewidth":    0.5,
    "xtick.major.width": 0.4,
    "ytick.major.width": 0.4,
    "xtick.major.size":  2.0,
    "ytick.major.size":  2.0,
}


def apply_style() -> None:
    """Call once at the top of a figure-building function, before plt.subplots()."""
    plt.rcParams.update(RCPARAMS)


# ── Page-size constraints ───────────────────────────────────────────────────
# Single- and double-column widths in inches, matching the dimensions Nature/
# Scientific Data actually typeset at (~89mm / ~183mm). COLUMN_WIDTH_IN
# already matches what distribution.py and the CoreEntities sankeys use —
# treat it as the default for any bar/line/scatter figure; reach for
# PAGE_WIDTH_IN only when a figure has enough panels or label density to need
# the full page.
COLUMN_WIDTH_IN = 3.5
PAGE_WIDTH_IN   = 7.2

# Max figure height in inches — a full US Letter page (11in) minus margins
# and caption room. Figures taller than this can't fit on one page.
MAX_HEIGHT_IN = 9.5


def figsize(width: float, height: float) -> tuple:
    """
    (width, height) for plt.subplots()/plt.figure(), with a soft check
    against page-size drift. Warns (does not raise) so an intentional
    one-off doesn't get blocked — but the warning is the point: it forces a
    conscious choice instead of a copy-pasted number that silently grows.
    """
    if width not in (COLUMN_WIDTH_IN, PAGE_WIDTH_IN):
        warnings.warn(
            f"figsize width {width}in matches neither COLUMN_WIDTH_IN "
            f"({COLUMN_WIDTH_IN}) nor PAGE_WIDTH_IN ({PAGE_WIDTH_IN}) — "
            "confirm this is intentional.",
            stacklevel=2,
        )
    if height > MAX_HEIGHT_IN:
        warnings.warn(
            f"figsize height {height}in exceeds MAX_HEIGHT_IN ({MAX_HEIGHT_IN}) — "
            "won't fit on one page; consider splitting into panels or "
            "reducing label density instead of just growing the canvas.",
            stacklevel=2,
        )
    return (width, height)


# Gap reserved between adjacent panels in a multi-panel plt.subplots() grid,
# in inches — used by panel_size() below to compute how much room each
# individual panel gets once those gaps are accounted for.
BUFFER_IN = 0.2


def grid_figsize(nrows: int, ncols: int) -> tuple:
    """
    Total figsize for any plt.subplots(nrows, ncols, ...) grid of more than
    one panel. Always (PAGE_WIDTH_IN, MAX_HEIGHT_IN) — a grid with ncols=1
    is still a full-width montage of stacked panels, not a narrow
    single-column chart, so it gets the full page width regardless of
    column count. Use plain figsize(COLUMN_WIDTH_IN, height) instead for a
    genuine single-panel (1x1) figure that should read as narrow.
    """
    return figsize(PAGE_WIDTH_IN, MAX_HEIGHT_IN)


def panel_size(nrows: int, ncols: int, buffer: float = BUFFER_IN) -> tuple:
    """
    Approximate (width, height) of one panel inside a grid_figsize(nrows,
    ncols) canvas, after reserving `buffer` inches for each inter-panel gap
    — (ncols - 1) gaps across, (nrows - 1) gaps down. Informational only
    (for sizing per-panel fonts/markers or sanity-checking a grid isn't too
    cramped) — plt.subplots() handles actual spacing via hspace/wspace.
    """
    panel_w = (PAGE_WIDTH_IN - buffer * (ncols - 1)) / ncols
    panel_h = (MAX_HEIGHT_IN - buffer * (nrows - 1)) / nrows
    return (panel_w, panel_h)


# ── Font size scale ─────────────────────────────────────────────────────────
# Defaults for a typical single-column figure. Tick-label size in particular
# is content-driven (a 60-category axis needs smaller labels than a 5-bar
# one) — override it explicitly when you do, rather than picking a new
# arbitrary number that drifts from everything else.
TITLE_SIZE      = 9
AXIS_LABEL_SIZE = 8
TICK_LABEL_SIZE = 6.0
LEGEND_SIZE     = 6.0
ANNOTATION_SIZE = 4.5


def style_title(ax, text: str, fontsize: float = TITLE_SIZE) -> None:
    ax.set_title(text, fontsize=fontsize, fontweight="bold", loc="left", pad=5)


# ── Legend defaults ──────────────────────────────────────────────────────────
LEGEND_KWARGS = dict(
    fontsize=LEGEND_SIZE,
    frameon=True,
    framealpha=0.9,
    edgecolor="#cccccc",
    handlelength=1.0,
    handleheight=0.9,
    borderpad=0.5,
    labelspacing=0.3,
)


# ── Axis helpers ─────────────────────────────────────────────────────────────

def clean_spines(ax, keep: tuple = ("bottom", "left")) -> None:
    """Hide all spines except `keep` — the top/right removal repeated in every script."""
    for sp in ax.spines:
        ax.spines[sp].set_visible(sp in keep)


def count_formatter(m_decimals: int = 1, k_decimals: int = 0) -> mticker.FuncFormatter:
    """Axis formatter for raw counts as '1.2M' / '340k' / '85' — used on every count axis."""
    def _fmt(x, _pos):
        if x >= 1e6:
            return f"{x/1e6:.{m_decimals}f}M"
        if x >= 1e3:
            return f"{x/1e3:.{k_decimals}f}k"
        return f"{x:,.0f}"
    return mticker.FuncFormatter(_fmt)


def grid_x(ax, color: str = "#e0e0e0", lw: float = 0.4) -> None:
    ax.grid(axis="x", which="major", color=color, lw=lw, zorder=0)
    ax.set_axisbelow(True)


def grid_y(ax, color: str = "#e0e0e0", lw: float = 0.4) -> None:
    ax.grid(axis="y", which="major", color=color, lw=lw, zorder=0)
    ax.set_axisbelow(True)


# ── Save ─────────────────────────────────────────────────────────────────────
# 400 rather than the more common 300 — some journals require it for raster
# elements even inside a vector PDF. Bump this one constant if a target
# journal's requirement changes; nothing else in this module depends on it.
SAVE_DPI = 400


def savefig(fig, path: str, tight: bool = True) -> None:
    """
    All figures save as PDF @ SAVE_DPI. `tight=False` for the CoreEntities
    sankey figures — bbox_inches='tight' would perturb their exact landscape
    dimensions (see CLAUDE.md).
    """
    fig.savefig(path, dpi=SAVE_DPI, bbox_inches="tight" if tight else None)
    print(f"Saved → {path}")
