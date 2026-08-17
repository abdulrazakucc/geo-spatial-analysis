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
# Teal marks a result below 1 (less capacity), rust a result above 1 (more),
# with the open grey marker for "not significant" sitting between them: the pair
# is read as a diverging scale, so both poles need enough chroma to register as
# poles rather than as muted greys.
#
# These values are computed, not chosen by eye. Both clear the chroma floor
# (>= 0.10 OKLCH), are separated by OKLab dE 16.5 under protanopia and 19.8
# under deuteranopia against a floor of 8, by 24.9 in normal vision against a
# floor of 15, and each holds better than 4:1 contrast on white. The previous
# teal (#16606b) failed the chroma floor at 0.071.
TEAL = "#00869e"
RUST = "#c0562c"
INK = "#16202b"
MUTE = "#6b7885"
RULE = "#c9d2da"
FAINT = "#eef1f4"

#: Sequential ramp for the choropleths, single hue, light to dark. Zero capacity
#: is a neutral grey so "none" reads as categorically different from "a little".
#:
#: The ramp starts well clear of white on purpose. In the previous version the
#: zero-capacity grey and the palest data bin were OKLab dE 2.0 apart, which is
#: indistinguishable, and both sat about 8 from white. On this map that is the
#: worst place to lose a distinction: the great majority of counties have no
#: accredited capacity at all, and that is the finding. The palest step is now
#: dE 16.7 from the zero fill, above the floor of 15, holds 2.1:1 contrast on
#: white, and every adjacent pair differs by at least 0.06 in OKLCH lightness.
ZERO_FILL = "#e1e5e8"
SEQ = ["#97b6bc", "#76a3ab", "#53909a", "#2a7d8a", "#006977", "#00535f"]
BIN_EDGES = [0.5, 1, 2, 4, 8]
BIN_LABELS = ["0", "≤0.5", "0.5–1", "1–2", "2–4", "4–8", ">8"]

#: Counties with too few adults for a rate are hatched rather than left plain
#: white. White alone is only dE 8.1 from the zero-capacity grey, so on a page
#: that distinction was carried by almost nothing; a pattern does not depend on
#: hue, print fidelity, or colour vision.
# Kept deliberately quiet: only 106 counties are excluded and they are not the
# point of the map, so the pattern has to be findable without competing with the
# data it sits beside.
EXCLUDED_FILL = "#ffffff"
EXCLUDED_HATCH = "//"
EXCLUDED_EDGE = "#ccd5dd"

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


def excluded_key(fig, x, y, w=0.021, h=0.019):
    """Hatched swatch plus its label, matching the map's excluded counties."""
    ax = fig.add_axes([x, y, w, h])
    ax.set_axis_off()
    ax.add_patch(mpl.patches.Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                                       facecolor=EXCLUDED_FILL,
                                       hatch=EXCLUDED_HATCH,
                                       edgecolor=EXCLUDED_EDGE, linewidth=0.6))
    fig.text(x + w * 1.6, y + h * 0.5,
             "County excluded from the rate calculation "
             "(<1,000 adults aged ≥45 years)",
             ha="left", va="center", fontsize=9, color=MUTE)
    return ax


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
