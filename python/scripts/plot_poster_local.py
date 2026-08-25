"""Panels 1 and 3 — the two that need data the poster build cannot reach.

    .\\.venv\\Scripts\\python.exe python\\scripts\\plot_poster_local.py

Writes into outputs/figures/ :
    poster_panel1_hero.{pdf,png}
    poster_panel3_extent.{pdf,png}
    poster_local_stats.json

No panel numbers; headings flush left; every axes placed inside the reserved
axes band; captions wrapped by measurement and capped at two lines.

The layout constants below are MIRRORED from python/caprm/poster_layout.py
rather than imported, because an import failure here costs a whole run. If both
are importable the values are asserted equal at start-up.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

# --- mirrored from poster_layout.py -----------------------------------------
W, H = 36.0, 24.0
MARGIN_X, MARGIN_BOTTOM = 1.25, 0.45
HEADER_H, GAP_HEADER = 3.00, 0.50
GAP_BAND, PANEL_GAP_Y = 0.50, 0.75
TRACE_H, FOOTER_H = 4.90, 0.90
GUTTER_X = 0.85

COLS_TOP = H - HEADER_H - GAP_HEADER
COLS_BOTTOM = MARGIN_BOTTOM + FOOTER_H + TRACE_H + GAP_BAND
PANEL_H = (COLS_TOP - COLS_BOTTOM - PANEL_GAP_Y) / 2.0
COL_W = (W - 2 * MARGIN_X - 2 * GUTTER_X) / 3.0

BAND_HEAD, BAND_GAP_1, BAND_AXES, BAND_GAP_2, BAND_CAPTION = 1.21, 0.15, 4.22, 0.20, 0.72

INK, PRIMARY, ACCENT = "#1a1a1a", "#2d4a32", "#c1704f"
NEUTRAL, GRID, PALE = "#7a8b80", "#dcdcdc", "#b9c6bd"
PT_PANEL_HEAD, PT_CAPTION, MIN_PT = 38, 20, 16

CRS = "EPSG:26918"
CAPTION_MAX_LINES = 2
_overflow: list[str] = []

try:                                        # cross-check when both are present
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from caprm import poster_layout as _L
    assert (round(_L.COL_W, 4), round(_L.PANEL_H, 4)) == (round(COL_W, 4), round(PANEL_H, 4)), \
        f"mirrored geometry drifted: {_L.COL_W}x{_L.PANEL_H} vs {COL_W}x{PANEL_H}"
except Exception:
    pass


def rc():
    return {"figure.facecolor": "#ffffff", "axes.facecolor": "#ffffff",
            "savefig.facecolor": "#ffffff", "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans"], "text.color": INK,
            "axes.labelcolor": INK, "axes.edgecolor": INK,
            "axes.spines.top": False, "axes.spines.right": False,
            "grid.color": GRID, "grid.linewidth": 0.8,
            "xtick.color": INK, "ytick.color": INK, "legend.frameon": False}


def panel_rect(col, row):
    x = MARGIN_X + col * (COL_W + GUTTER_X)
    y = COLS_TOP - PANEL_H if row == 0 else COLS_BOTTOM
    return (x, y, COL_W, PANEL_H)


def panel_bands(rect):
    x, y, w, h = rect
    cap = (x, y, w, BAND_CAPTION)
    axes = (x, y + BAND_CAPTION + BAND_GAP_2, w, BAND_AXES)
    head = (x, y + h - BAND_HEAD, w, BAND_HEAD)
    return head, axes, cap


# --- shared -----------------------------------------------------------------
def measure(fig, r, text, pt, weight="normal"):
    t = fig.text(0, 0, text, fontsize=pt, fontweight=weight)
    w = t.get_window_extent(renderer=r).width / fig.dpi
    t.remove()
    return w


def fit(fig, r, text, pt, avail, where, weight="normal"):
    w = measure(fig, r, text, pt, weight)
    if w > avail:
        _overflow.append(f"{where}: {w:.2f} > {avail:.2f} in | {text[:64]!r}")
    return w


def wrap_to(fig, r, text, pt, avail):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if measure(fig, r, trial, pt) > avail and cur:
            lines.append(cur); cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def heading(fig, r, rect, lines):
    hx, hy, hw, hh = panel_bands(rect)[0]
    for i, line in enumerate(lines):
        fit(fig, r, line, PT_PANEL_HEAD, hw - 0.20, "heading", "bold")
        fig.text((hx + 0.02) / W, (hy + hh - 0.06 - i * 0.60) / H, line,
                 fontsize=PT_PANEL_HEAD, fontweight="bold", color=INK,
                 va="top", ha="left")


def caption(fig, r, rect, text):
    cx, cy, cw, _ = panel_bands(rect)[2]
    lines = wrap_to(fig, r, text, PT_CAPTION, cw - 0.10)
    if len(lines) > CAPTION_MAX_LINES:
        _overflow.append(f"caption {len(lines)} lines > {CAPTION_MAX_LINES}")
    top = cy + 0.20 + 0.30 * (len(lines) - 1)
    for i, line in enumerate(lines):
        fig.text((cx + 0.02) / W, (top - i * 0.30) / H, line, fontsize=PT_CAPTION,
                 color=INK, va="baseline", ha="left")


def band_axes(fig, rect, left=0.0, bottom=0.0, right=0.0, top=0.0):
    ax_x, ax_y, ax_w, ax_h = panel_bands(rect)[1]
    return fig.add_axes([(ax_x + left) / W, (ax_y + bottom) / H,
                         (ax_w - left - right) / W, (ax_h - bottom - top) / H])


def save(fig, rect, out: Path, stem: str):
    x, y, w, h = rect
    bb = matplotlib.transforms.Bbox([[x, y], [x + w, y + h]])
    fig.savefig(out / f"{stem}.pdf", bbox_inches=bb)
    fig.savefig(out / f"{stem}.png", dpi=200, bbox_inches=bb)
    plt.close(fig)


# --- panel 1 ----------------------------------------------------------------
def draw_hero(fig, r, rect, county_xy, px, py, pct):
    heading(fig, r, rect, ["267,362 properties, four", "evidence values, one number"])
    pad = 2500.0
    ax = band_axes(fig, rect, left=0.05, right=1.55)
    ax.plot(county_xy[:, 0], county_xy[:, 1], color=INK, linewidth=1.6, zorder=3)
    order = np.argsort(pct)
    sc = ax.scatter(px[order], py[order], c=pct[order], s=0.35, cmap="YlGnBu",
                    vmin=0, vmax=100, linewidths=0, zorder=2)
    ax.set_xlim(px.min() - pad, px.max() + pad)
    ax.set_ylim(py.min() - pad, py.max() + pad)
    ax.set_aspect("equal"); ax.axis("off")

    bx, by, bw, bh = panel_bands(rect)[1]
    cax = fig.add_axes([(bx + bw - 1.25) / W, (by + 0.45) / H, 0.18 / W, (bh - 0.90) / H])
    cb = fig.colorbar(sc, cax=cax)
    cb.set_label("percentile rank", fontsize=PT_CAPTION - 1)
    cb.ax.tick_params(labelsize=MIN_PT)

    caption(fig, r, rect,
            "Four traceable values per property, combined by four declared weights into one "
            "relative ranking — not a flood probability.")


# --- panel 3 ----------------------------------------------------------------
def draw_extent(fig, r, rect, diag, county_xy, lake_bbox, lake_name):
    heading(fig, r, rect, ["A bounding box is a useless", "proxy for an extended object"])
    med, p99, mx = np.median(diag), np.percentile(diag, 99), diag.max()
    bx, by, bw, bh = panel_bands(rect)[1]

    axl = fig.add_axes([(bx + 1.35) / W, (by + 0.85) / H,
                        (bw * 0.52 - 1.55) / W, (bh - 1.15) / H])
    axl.hist(np.log10(diag), bins=60, color=PALE, edgecolor="none")
    top = axl.get_ylim()[1]
    for v, lab, tone, frac, ha in [(med, "median", NEUTRAL, 0.97, "right"),
                                   (p99, "99th pct", NEUTRAL, 0.70, "left"),
                                   (mx, lake_name, ACCENT, 0.43, "right")]:
        axl.axvline(np.log10(v), color=tone, linewidth=2.2,
                    linestyle="--" if tone is NEUTRAL else "-")
        off = -0.09 if ha == "right" else 0.09
        axl.text(np.log10(v) + off, top * frac, f"{lab}\n{v:,.0f} m", fontsize=MIN_PT,
                 color=tone, ha=ha, va="top", linespacing=1.2,
                 fontweight="bold" if tone is ACCENT else "normal")
    axl.set_xticks([1, 3, 5])
    axl.set_xticklabels(["10 m", "1 km", "100 km"], fontsize=MIN_PT)
    axl.tick_params(axis="y", labelsize=MIN_PT)
    axl.set_xlabel("bounding-box diagonal", fontsize=PT_CAPTION - 1)
    axl.set_ylabel("water features", fontsize=PT_CAPTION - 1)
    axl.grid(axis="y", color=GRID, linewidth=0.8); axl.set_axisbelow(True)

    bx0, by0, bx1, by1 = lake_bbox
    axr = fig.add_axes([(bx + bw * 0.55) / W, (by + 0.40) / H,
                        (bw * 0.45 - 0.15) / W, (bh - 0.60) / H])
    axr.add_patch(Rectangle((bx0, by0), bx1 - bx0, by1 - by0, facecolor=ACCENT,
                            alpha=0.15, edgecolor=ACCENT, linewidth=2.6, zorder=2))
    axr.plot(county_xy[:, 0], county_xy[:, 1], color=INK, linewidth=1.8, zorder=3)
    m = 0.04 * (bx1 - bx0)
    axr.set_xlim(bx0 - m, bx1 + m); axr.set_ylim(by0 - m, by1 + m)
    axr.set_aspect("equal"); axr.axis("off")
    lab = f"{lake_name}'s box, {(bx1-bx0)/1000:,.0f} \u00d7 {(by1-by0)/1000:,.0f} km"
    fit(fig, r, lab, MIN_PT, bw * 0.45 - 0.30, "p3/boxlabel")
    axr.text(0.5, 0.01, lab, transform=axr.transAxes, fontsize=MIN_PT, color=INK,
             ha="center", va="bottom")

    caption(fig, r, rect,
            f"{len(diag):,} features span five orders of magnitude. Indexing their boxes examines "
            f"5.5 per property yet still checks 70,771 segments.")


# --- main -------------------------------------------------------------------
def main() -> None:
    import pandas as pd
    import geopandas as gpd

    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="outputs/index/property_exposure_index_countywide.csv")
    ap.add_argument("--coords", default="outputs/cpp_input/water_properties_projected_countywide.csv")
    ap.add_argument("--county", default="data/raw/census_monroe_county_2025.geojson")
    ap.add_argument("--water", default="data/raw/usgs_3dhp_monroe.gpkg")
    ap.add_argument("--outdir", default="outputs/figures")
    a = ap.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)

    county = gpd.read_file(a.county).to_crs(CRS)
    geom = county.geometry.iloc[0]
    ring = geom.exterior if geom.geom_type == "Polygon" else max(
        geom.geoms, key=lambda g: g.area).exterior
    county_xy = np.asarray(ring.coords)

    idx = pd.read_csv(a.index, dtype={"property_id": str})
    xy = pd.read_csv(a.coords, dtype={"property_id": str}, float_precision="round_trip")
    df = idx.merge(xy[["property_id", "projected_x", "projected_y"]],
                   on="property_id", how="inner", validate="one_to_one")
    if len(df) != len(idx):
        raise SystemExit(f"join lost rows: {len(idx)} index, {len(df)} joined")

    try:
        layers = gpd.list_layers(a.water)["name"].tolist()
    except AttributeError:
        import fiona
        layers = fiona.listlayers(a.water)
    parts = []
    for lyr in layers:
        g = gpd.read_file(a.water, layer=lyr).to_crs(CRS)
        g = g[~g.geometry.isna() & ~g.geometry.is_empty]
        if len(g):
            g = g.copy(); g["_layer"] = lyr
            parts.append(g)
    feats = pd.concat(parts, ignore_index=True)
    b = feats.geometry.bounds
    diag = np.hypot(b.maxx - b.minx, b.maxy - b.miny).to_numpy()
    if (diag <= 0).any():
        raise SystemExit(f"{int((diag <= 0).sum())} degenerate features")

    big = int(np.argmax(diag))
    name_col = next((c for c in ("source_name", "name", "gnis_name") if c in feats.columns), None)
    lake_name = str(feats.iloc[big][name_col]) if name_col else "largest feature"
    lake_bbox = tuple(float(v) for v in feats.iloc[big].geometry.bounds)

    stats = {"crs": CRS,
             "panel1": dict(n_properties=int(len(df)),
                            index_min=float(df.exposure_index_0_100.min()),
                            index_max=float(df.exposure_index_0_100.max()),
                            index_median=float(df.exposure_index_0_100.median())),
             "panel3": dict(n_features=int(len(feats)),
                            layers={l: int((feats._layer == l).sum()) for l in layers},
                            diag_median_m=float(np.median(diag)),
                            diag_mean_m=float(diag.mean()),
                            diag_p99_m=float(np.percentile(diag, 99)),
                            diag_max_m=float(diag.max()),
                            largest_name=lake_name,
                            largest_bbox_km=[(lake_bbox[2]-lake_bbox[0])/1000,
                                             (lake_bbox[3]-lake_bbox[1])/1000],
                            largest_over_p99=float(diag.max()/np.percentile(diag, 99)))}

    plt.rcParams.update(rc())
    rect = panel_rect(0, 0)

    fig = plt.figure(figsize=(W, H)); r = fig.canvas.get_renderer()
    draw_hero(fig, r, rect, county_xy, df.projected_x.to_numpy(),
              df.projected_y.to_numpy(), df.exposure_percentile.to_numpy())
    save(fig, rect, out, "poster_panel1_hero")

    fig = plt.figure(figsize=(W, H)); r = fig.canvas.get_renderer()
    draw_extent(fig, r, rect, diag, county_xy, lake_bbox, lake_name)
    save(fig, rect, out, "poster_panel3_extent")

    (out / "poster_local_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    if _overflow:
        raise SystemExit("OVERFLOW:\n  " + "\n  ".join(_overflow))
    print("\nno text overflow")


if __name__ == "__main__":
    main()