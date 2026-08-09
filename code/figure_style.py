#!/usr/bin/env python3
"""
figure_style.py
===============
Shared look for the publication figures: palette, typography, and the
Albers-with-insets projection used by the choropleths.

Every figure reads its values from the generated results at plot time, so a
figure cannot disagree with the table it accompanies.
"""

from __future__ import annotations

import matplotlib as mpl
import numpy as np

# --- palette -----------------------------------------------------------------
# Teal marks a result below 1 (less capacity), rust a result above 1 (more).
# Both are dark enough for print and distinguishable in greyscale.
TEAL = "#16606b"
RUST = "#c0562c"
INK = "#16202b"
MUTE = "#6b7885"
RULE = "#c9d2da"
FAINT = "#eef1f4"

#: Sequential ramp for the choropleths, light to dark. Index 0 is the
#: zero-capacity colour and is deliberately a neutral grey, not the palest
#: teal, so "none" reads as categorically different from "a little".
ZERO_FILL = "#e2e6e9"
SEQ = ["#d3e8e7", "#a8d2d1", "#71b3b5", "#43919a", "#256e7c", "#0d4a5c"]
BIN_EDGES = [0.5, 1, 2, 4, 8]
BIN_LABELS = ["0", "≤0.5", "0.5–1", "1–2", "2–4", "4–8", ">8"]

DPI = 600


def apply():
    """Global rcParams. Called once per figure script."""
    mpl.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": DPI,
        "savefig.bbox": "tight",
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Helvetica Neue", "Arial"],
        "text.color": INK,
        "axes.edgecolor": RULE,
        "axes.labelcolor": INK,
        "xtick.color": MUTE,
        "ytick.color": MUTE,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,          # editable text in the vector output
        "ps.fonttype": 42,
    })


def bin_index(value):
    """Which colour bin a rate falls in. 0 means no capacity."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if value <= 0:
        return 0
    return int(np.searchsorted(BIN_EDGES, value, side="left")) + 1


def fill_for(value, rate_excluded=False):
    """Colour for one county."""
    if rate_excluded:
        return "white"           # excluded from rate calculation
    idx = bin_index(value)
    if idx is None:
        return "white"
    return ZERO_FILL if idx == 0 else SEQ[idx - 1]


def title_block(fig, title, subtitle=None, right=None, y=0.985):
    """Bold title, muted subtitle, optional right-aligned summary."""
    fig.text(0.008, y, title, ha="left", va="top", fontsize=16.5,
             fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.008, y - 0.042, subtitle, ha="left", va="top",
                 fontsize=10.5, color=MUTE)
    if right:
        fig.text(0.992, y, right, ha="right", va="top", fontsize=12,
                 fontweight="bold", color=INK)


def split_for_insets(gdf):
    """Return (lower48, alaska, hawaii), each projected for its own axes.

    Translating Alaska into the main frame is unreliable: the Aleutian chain
    crosses the antimeridian, so its bounding box spans most of the globe and
    any placement computed from that box lands in the wrong place. Drawing each
    region in its own axes avoids the problem entirely and gives exact control
    over inset size and position.
    """
    lower48 = gdf[~gdf.state_abbr.isin(["AK", "HI"])].to_crs(epsg=5070)
    ak = gdf[gdf.state_abbr == "AK"]
    hi = gdf[gdf.state_abbr == "HI"]
    if len(ak):
        # Drop the far-western Aleutians so the frame is not mostly ocean.
        ak = ak.to_crs(epsg=4326)
        ak = ak[ak.geometry.centroid.x > -170]
        ak = ak.to_crs(epsg=3338)
    if len(hi):
        # Keep the main islands; Midway and the far northwest chain are empty.
        hi = hi.to_crs(epsg=4326)
        hi = hi[hi.geometry.centroid.x > -161]
        hi = hi.to_crs(epsg=3563)
    return lower48, ak, hi


def bin_legend(fig, ax_rect, title="Accredited facilities per 100,000 adults aged ≥45 years"):
    """Discrete swatch legend beneath a map."""
    ax = fig.add_axes(ax_rect)
    ax.set_axis_off()
    colours = [ZERO_FILL] + SEQ
    n = len(colours)
    for i, c in enumerate(colours):
        ax.add_patch(mpl.patches.Rectangle((i / n, 0.34), 1 / n * 0.92, 0.34,
                                           facecolor=c, edgecolor="none",
                                           transform=ax.transAxes))
        ax.text(i / n + 1 / n * 0.46, 0.16, BIN_LABELS[i], ha="center",
                va="top", fontsize=10, color=MUTE, transform=ax.transAxes)
    ax.text(0, 0.86, title, ha="left", va="bottom", fontsize=10.2, color=INK,
            transform=ax.transAxes)
    return ax
