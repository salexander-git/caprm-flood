"""The presentation chart house style, recovered from the existing slides.

PROVENANCE, stated because it is unusual. The five charts in
``presentation_assets/charts/`` (slide07 … slide11) have no generating script
anywhere in the repository. This module does not reconstruct that script — it
does not exist to be reconstructed — it records the style MEASURED out of
``slide07_index_distribution.svg`` and its PNG so that new figures match the
existing ones instead of drifting.

What was measured, and how:

    dpi 300                 PNG pHYs chunk, 11811 px/m
    DejaVu Sans             glyph path ids in the SVG (matplotlib default)
    tick labels 11 pt       SVG glyph transform scale(0.11 -0.11)
    axis labels 12 pt       SVG glyph transform scale(0.12 -0.12)
    annotations 11 pt bold  DejaVuSans-Bold glyph ids present at scale 0.11
    ink      #1a1a1a        29 fills, 16 strokes
    primary  #2d4a32 @ .9   120 bar fills with opacity 0.9
    accent   #c1704f        the median marker and its label
    grid     #dcdcdc, 0.8   9 strokes, horizontal only
    dashes   lw 1.8, 6.66,2.88   matplotlib "--" at linewidth 1.8
    canvas   442.09 x 492.27 pt = 6.14 x 6.84 in, portrait
    axes box 0.820 x 0.901 of the canvas
    facecolor white         figure patch fill #ffffff

The canvas size is a TIGHT-CROPPED result, not the declared ``figsize``: the
non-round dimensions are what ``bbox_inches="tight"`` leaves behind, so the
original ``figsize`` is not recoverable from the file. ``FIGSIZE_PORTRAIT``
below is chosen to crop to approximately the same canvas under the same
setting, which is the closest honest reconstruction available. If the original
script ever turns up, prefer it and delete this note.

The white figure background is also what the RIT poster guidance requires — the
poster background must be a light colour over at least 75 percent of the page —
so a figure on a dark panel would fail the format check regardless of taste.
"""

from __future__ import annotations

from typing import Any

INK = "#1a1a1a"
PRIMARY = "#2d4a32"
PRIMARY_ALPHA = 0.9
ACCENT = "#c1704f"
GRID = "#dcdcdc"
BACKGROUND = "#ffffff"

#: A third series is needed by C3 (blocked against random against a reference)
#: and slide07 carries only two, so this one is NOT recovered. It is a mid
#: neutral chosen to sit between the primary and the accent without competing
#: with either, and it is flagged as an addition rather than presented as
#: house style.
NEUTRAL = "#7a8b80"

FONT_FAMILY = "DejaVu Sans"
SIZE_TICK = 11
SIZE_AXIS_LABEL = 12
SIZE_ANNOTATION = 11
SIZE_PANEL_TITLE = 12

DPI = 300
LINEWIDTH_DASHED = 1.8
LINEWIDTH_GRID = 0.8
DASHES = (6.66, 2.88)

#: Crops to 442 x 493 pt under bbox_inches="tight" with the three-panel C3
#: layout, against slide07's measured 442.09 x 492.27; see the
#: module docstring on why this is a reconstruction and not the original value.
FIGSIZE_PORTRAIT = (6.3, 7.0)

SAVE_KWARGS: dict[str, Any] = {
    "dpi": DPI,
    "bbox_inches": "tight",
    "facecolor": BACKGROUND,
}


def rc_params() -> dict[str, Any]:
    """The measured style as matplotlib rcParams.

    Returned rather than applied at import: a module that mutates global
    matplotlib state on import is hidden global state, and the project's code
    standard rules that out.
    """
    return {
        "figure.facecolor": BACKGROUND,
        "axes.facecolor": BACKGROUND,
        "savefig.facecolor": BACKGROUND,
        "font.family": "sans-serif",
        "font.sans-serif": [FONT_FAMILY],
        "font.size": SIZE_TICK,
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.labelsize": SIZE_AXIS_LABEL,
        "axes.edgecolor": INK,
        "axes.titlesize": SIZE_PANEL_TITLE,
        "axes.titlecolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": LINEWIDTH_GRID,
        "xtick.color": INK,
        "ytick.color": INK,
        "xtick.labelsize": SIZE_TICK,
        "ytick.labelsize": SIZE_TICK,
        "legend.frameon": False,
        "legend.fontsize": SIZE_ANNOTATION,
        "savefig.dpi": DPI,
    }


def thousands(value: float, _position: int = 0) -> str:
    """Slide07's y-axis formatting: 6,000 rather than 6000."""
    return f"{value:,.0f}"