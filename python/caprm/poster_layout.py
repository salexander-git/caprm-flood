"""CAPRM-Flood poster geometry, in inches on a 36 x 24 canvas.

One module so that the grid render, every panel and the final assembly read the
same numbers. Changing a dimension here changes it everywhere; nothing below
re-derives a coordinate by hand.

Origin is bottom-left, matching matplotlib figure coordinates.
"""
from __future__ import annotations

# --- canvas -----------------------------------------------------------------
W = 36.0
H = 24.0

MARGIN_X = 1.25
MARGIN_BOTTOM = 0.45

# --- header -----------------------------------------------------------------
HEADER_H = 3.95           # 16.5% of height, well under the 25% ceiling
HEADER_RULE_H = 0.09      # dark rule closing the header
HEADER_Y = H - HEADER_H

# --- vertical budget --------------------------------------------------------
GAP_HEADER = 0.45
GAP_BAND = 0.42
PANEL_GAP_Y = 0.55

TRACE_H = 5.40            # full-width band, panel 7
FOOTER_H = 0.95           # provenance strip inside the band's footprint

COLS_TOP = HEADER_Y - GAP_HEADER
COLS_BOTTOM = MARGIN_BOTTOM + FOOTER_H + TRACE_H + GAP_BAND
COLS_H = COLS_TOP - COLS_BOTTOM
PANEL_H = (COLS_H - PANEL_GAP_Y) / 2.0

# --- horizontal budget ------------------------------------------------------
USABLE_W = W - 2 * MARGIN_X
GUTTER_X = 0.60
COL_W = (USABLE_W - 2 * GUTTER_X) / 3.0

TRACE_Y = MARGIN_BOTTOM + FOOTER_H
FOOTER_Y = MARGIN_BOTTOM


def col_x(i: int) -> float:
    """Left edge of column i (0, 1, 2)."""
    return MARGIN_X + i * (COL_W + GUTTER_X)


def panel_rect(col: int, row: int) -> tuple[float, float, float, float]:
    """(x, y, w, h) in inches for a column panel. row 0 is the upper panel."""
    y = COLS_TOP - PANEL_H if row == 0 else COLS_BOTTOM
    return (col_x(col), y, COL_W, PANEL_H)


def to_fig(rect: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Inches -> figure fraction, for fig.add_axes."""
    x, y, w, h = rect
    return (x / W, y / H, w / W, h / H)


# --- type scale, points -----------------------------------------------------
PT_TITLE = 96          # measured: 29.83 in for the 36-character title
PT_SUBTITLE = 40
PT_BYLINE = 26
PT_PANEL_HEAD = 38
PT_BODY = 24
PT_CAPTION = 20
PT_TRACE_HEAD = 26
PT_TRACE_BODY = 20
PT_TRACE_MONO = 16
PT_FOOTER = 17

# --- palette, from python/caprm/chart_style.py ------------------------------
INK = "#1a1a1a"
PRIMARY = "#2d4a32"
ACCENT = "#c1704f"
NEUTRAL = "#7a8b80"
GRID = "#dcdcdc"
BACKGROUND = "#ffffff"
PALE = "#b9c6bd"
RIT_ORANGE = "#f76902"


def rc():
    return {
        "figure.facecolor": BACKGROUND,
        "axes.facecolor": BACKGROUND,
        "savefig.facecolor": BACKGROUND,
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans"],
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.edgecolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": INK,
        "ytick.color": INK,
        "legend.frameon": False,
    }


if __name__ == "__main__":
    print(f"panel        {COL_W:.3f} x {PANEL_H:.3f} in   aspect {COL_W/PANEL_H:.2f}")
    print(f"trace band   {USABLE_W:.3f} x {TRACE_H:.3f} in   aspect {USABLE_W/TRACE_H:.2f}")
    print(f"columns      top {COLS_TOP:.2f}  bottom {COLS_BOTTOM:.2f}  height {COLS_H:.2f}")
    print(f"header       {HEADER_H:.2f} in = {100*HEADER_H/H:.1f}% of poster height")