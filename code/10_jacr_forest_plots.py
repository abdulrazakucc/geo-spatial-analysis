#!/usr/bin/env python3
"""
10_jacr_forest_plots.py
=======================
JACR revision figures. Reads output/jacr_revision/validated_index_results.json
(single source of truth, so numbers and plots can never drift apart) and writes
two publication-quality forest plots.

    Figure1B_Unadjusted_vs_Adjusted   Panel B redesigned. Our EDI association with
                                       CMR and CCT capacity, shown unadjusted and
                                       adjusted for metropolitan status, side by
                                       side, with metropolitan status in its own
                                       panel because its effect is on a different
                                       scale. Colour marks the modality.

    Figure_SDI_External_Validation     Our self-built EDI compared with the external
                                       Graham Center SDI for the CMR outcome. Colour
                                       marks the index.

Design notes
    Two stacked panels per figure with scales matched to the estimates, so the small
    deprivation confidence intervals are readable and the large metropolitan effect
    is not compressed. Colour encodes group, a filled marker means significant and an
    open marker means not significant. Light table banding, a clean sans-serif face,
    heavy strokes for crisp rendering at 600 dpi, and a short colour key. No
    descriptive paragraph is placed on the plot. All figure text avoids em-dashes and
    colons.

Run
    python code/09_validated_index_sdi.py     (first, produces the JSON)
    python code/10_jacr_forest_plots.py
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE_DIR, "output", "jacr_revision")
RES = json.load(open(os.path.join(OUT, "validated_index_results.json")))

# Palette
INK   = "#17262f"      # near-black text
TEAL  = "#0d7d75"      # CMR outcome and our EDI
INDIGO= "#3a5ba0"      # CCT outcome
AMBER = "#c07214"      # external Graham SDI
GRID  = "#c7d0d6"      # reference line
BAND  = "#f3f6f8"      # row banding
MUTE  = "#5f6f7a"      # secondary text
HAIR  = "#dfe6ea"      # hairline rules

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10.5, "axes.linewidth": 0.8, "pdf.fonttype": 42,
    "savefig.dpi": 600, "figure.dpi": 150,
})

# Column geometry in axes-fraction units
LABEL_X = 0.015
FL, FR  = 0.355, 0.610
STAT_X  = 0.650


def fmt(r):
    p = r["P"]
    ptxt = "P < 0.001" if p < 0.001 else f"P = {p:.3f}"
    return f"{r['IRR']:.2f} ({r['CI_low']:.2f} to {r['CI_high']:.2f})", ptxt


def _map(v, xmin, xmax, logscale):
    if logscale:
        v, xmin, xmax = np.log(v), np.log(xmin), np.log(xmax)
    return FL + (v - xmin) / (xmax - xmin) * (FR - FL)


def draw_panel(ax, panel_title, accent, rows, xmin, xmax, ticks, logscale, xnote):
    n = len(rows)
    ax.set_xlim(0, 1)
    top, bot = 1.35, -(n - 1) - 1.55
    ax.set_ylim(bot, top)
    ax.axis("off")
    ys = [-i for i in range(n)]

    # banding
    for i, y in enumerate(ys):
        if i % 2 == 0:
            ax.add_patch(Rectangle((0.0, y - 0.5), 1.0, 1.0, facecolor=BAND,
                                   edgecolor="none", zorder=0))

    # coloured accent chip and panel title
    ax.add_patch(FancyBboxPatch((LABEL_X, top - 0.30), 0.022, 0.30,
                 boxstyle="round,pad=0,rounding_size=0.01", facecolor=accent,
                 edgecolor="none", zorder=2, mutation_aspect=0.5, clip_on=False))
    ax.text(LABEL_X + 0.036, top - 0.15, panel_title, fontsize=11,
            fontweight="bold", color=INK, va="center", ha="left")
    ax.text(STAT_X, top - 0.15, "IRR (95% CI)", fontsize=9.4, fontweight="bold",
            color=INK, va="center", ha="left")
    ax.text(STAT_X + 0.205, top - 0.15, "P value", fontsize=9.4, fontweight="bold",
            color=INK, va="center", ha="left")
    ax.plot([LABEL_X, 0.995], [top - 0.42, top - 0.42], color=HAIR, lw=1.0, zorder=1)

    # reference line at IRR = 1
    if xmin <= 1 <= xmax:
        xref = _map(1.0, xmin, xmax, logscale)
        ax.plot([xref, xref], [ys[-1] - 0.5, ys[0] + 0.5], ls=(0, (4, 3)), lw=1.1,
                color=GRID, zorder=1)

    for y, r in zip(ys, rows):
        est = r["est"]
        sig = est["P"] < 0.05
        col = r["color"]
        xp = _map(est["IRR"], xmin, xmax, logscale)
        xlo = _map(max(est["CI_low"], xmin), xmin, xmax, logscale)
        xhi = _map(min(est["CI_high"], xmax), xmin, xmax, logscale)
        ax.plot([xlo, xhi], [y, y], color=col, lw=2.4, zorder=3, solid_capstyle="round")
        for xc in (xlo, xhi):
            ax.plot([xc, xc], [y - 0.11, y + 0.11], color=col, lw=2.0, zorder=3)
        ax.scatter([xp], [y], s=104 if sig else 92,
                   color=(col if sig else "white"), edgecolor=col,
                   linewidth=2.1, zorder=4)
        ax.text(LABEL_X, y, r["label"], fontsize=9.7, color=INK, va="center", ha="left")
        est_txt, p_txt = fmt(est)
        ax.text(STAT_X, y, est_txt, fontsize=9.5, fontweight=("bold" if sig else "normal"),
                color=(INK if sig else MUTE), va="center", ha="left")
        ax.text(STAT_X + 0.205, y, p_txt, fontsize=9.5,
                fontweight=("bold" if sig else "normal"),
                color=(accent if sig else MUTE), va="center", ha="left")

    # forest x-axis
    axis_y = ys[-1] - 0.60
    ax.plot([FL, FR], [axis_y, axis_y], color="#9aa6ae", lw=1.0)
    for t in ticks:
        xt = _map(t, xmin, xmax, logscale)
        ax.plot([xt, xt], [axis_y, axis_y - 0.10], color="#9aa6ae", lw=1.0)
        ax.text(xt, axis_y - 0.30, f"{t:g}", fontsize=8.6, color=MUTE, va="center", ha="center")
    ax.text((FL + FR) / 2, axis_y - 0.72, xnote, fontsize=8.4, color=MUTE,
            va="center", ha="center")


def legend_row(fig, y, items):
    """Draw a compact colour key as a single centred row near the top."""
    ax = fig.add_axes([0.0, y, 1.0, 0.04]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    xs = 0.5 - 0.5 * 0.9
    x = 0.02
    for label, color, filled in items:
        ax.scatter([x], [0.5], s=90, color=(color if filled else "white"),
                   edgecolor=color, linewidth=2.0, transform=ax.transAxes)
        ax.text(x + 0.016, 0.5, label, fontsize=9.2, color=INK, va="center",
                ha="left", transform=ax.transAxes)
        x += 0.016 + 0.011 * len(label) + 0.03


def build_figure(title, footer, legend_items, panels, stem):
    heights = [len(p["rows"]) + 1.9 for p in panels]
    fig = plt.figure(figsize=(9.0, 0.56 * sum(heights) + 1.35))
    gs = fig.add_gridspec(len(panels), 1, height_ratios=heights, hspace=0.34,
                          left=0.02, right=0.99, top=0.855, bottom=0.05)
    for i, p in enumerate(panels):
        ax = fig.add_subplot(gs[i])
        draw_panel(ax, p["title"], p["accent"], p["rows"], p["xmin"], p["xmax"],
                   p["ticks"], p["log"], p["xnote"])
    fig.suptitle(title, x=0.02, ha="left", fontsize=15, fontweight="bold",
                 color=INK, y=0.985)
    legend_row(fig, 0.905, legend_items)
    fig.text(0.02, 0.012, footer, ha="left", fontsize=8.4, color=MUTE)
    for ext, dpi in [("png", 600), ("pdf", None)]:
        fig.savefig(os.path.join(OUT, f"{stem}.{ext}"), dpi=dpi,
                    bbox_inches="tight", pad_inches=0.22, facecolor="white")
    plt.close(fig)
    print(f"wrote {stem}.png and {stem}.pdf")


DEP_TICKS, DEP_RANGE = [0.9, 1.0, 1.1], (0.85, 1.13)
MET_TICKS, MET_RANGE = [1, 2, 5, 10, 20], (0.9, 20)
DEP_NOTE = "IRR per 10-point rise in deprivation (below 1 lower capacity, above 1 higher)"
MET_NOTE = "IRR, metropolitan versus nonmetropolitan (log scale)"

# ---- Figure 1B, our EDI, colour encodes modality --------------------------
e = RES["EDI_models"]["outcomes"]
build_figure(
    "Figure 1B.  Area deprivation and accredited cardiac imaging capacity",
    "Economic Deprivation Index, negative binomial regression with population offset, n = 3,029 counties.",
    [("Cardiac MRI", TEAL, True), ("Cardiac CT", INDIGO, True),
     ("filled significant", INK, True), ("open not significant", INK, False)],
    [
        {"title": "Area deprivation, per 10-point increase", "accent": TEAL, "log": False,
         "xmin": DEP_RANGE[0], "xmax": DEP_RANGE[1], "ticks": DEP_TICKS, "xnote": DEP_NOTE,
         "rows": [
             {"label": "Cardiac MRI, unadjusted", "color": TEAL, "est": e["cmr_facility_count"]["unadjusted"]},
             {"label": "Cardiac MRI, adjusted for metro", "color": TEAL, "est": e["cmr_facility_count"]["adjusted"]},
             {"label": "Cardiac CT, unadjusted", "color": INDIGO, "est": e["cct_facility_count"]["unadjusted"]},
             {"label": "Cardiac CT, adjusted for metro", "color": INDIGO, "est": e["cct_facility_count"]["adjusted"]},
         ]},
        {"title": "Metropolitan status, from the adjusted models", "accent": INDIGO, "log": True,
         "xmin": MET_RANGE[0], "xmax": MET_RANGE[1], "ticks": MET_TICKS, "xnote": MET_NOTE,
         "rows": [
             {"label": "Cardiac MRI capacity", "color": TEAL, "est": e["cmr_facility_count"]["metro_in_adjusted"]},
             {"label": "Cardiac CT capacity", "color": INDIGO, "est": e["cct_facility_count"]["metro_in_adjusted"]},
         ]},
    ],
    "Figure1B_Unadjusted_vs_Adjusted")

# ---- Figure S, EDI vs external SDI, colour encodes index ------------------
s = RES["SDI_models"]["outcomes"]["cmr_facility_count"]
ec = e["cmr_facility_count"]
build_figure(
    "Figure S.  External validation with a published deprivation index",
    "Cardiac MRI outcome. Our EDI compared with the Robert Graham Center Social Deprivation Index (SDI, 2015 to 2019).",
    [("Our EDI", TEAL, True), ("Graham Center SDI", AMBER, True),
     ("filled significant", INK, True), ("open not significant", INK, False)],
    [
        {"title": "Area deprivation and CMR capacity, per 10-point increase", "accent": TEAL, "log": False,
         "xmin": DEP_RANGE[0], "xmax": DEP_RANGE[1], "ticks": DEP_TICKS, "xnote": DEP_NOTE,
         "rows": [
             {"label": "Unadjusted, our EDI", "color": TEAL, "est": ec["unadjusted"]},
             {"label": "Unadjusted, Graham Center SDI", "color": AMBER, "est": s["unadjusted"]},
             {"label": "Adjusted for metro, our EDI", "color": TEAL, "est": ec["adjusted"]},
             {"label": "Adjusted for metro, Graham SDI", "color": AMBER, "est": s["adjusted"]},
         ]},
        {"title": "Metropolitan status and CMR capacity, from the adjusted models", "accent": AMBER, "log": True,
         "xmin": MET_RANGE[0], "xmax": MET_RANGE[1], "ticks": MET_TICKS, "xnote": MET_NOTE,
         "rows": [
             {"label": "Our EDI model", "color": TEAL, "est": ec["metro_in_adjusted"]},
             {"label": "Graham Center SDI model", "color": AMBER, "est": s["metro_in_adjusted"]},
         ]},
    ],
    "Figure_SDI_External_Validation")
