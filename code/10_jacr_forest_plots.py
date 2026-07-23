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
                                       scale.

    Figure_SDI_External_Validation     Our self-built EDI compared with the external
                                       Graham Center SDI for the CMR outcome.

Design notes
    Each figure has two stacked panels with scales matched to the estimates, so the
    small deprivation confidence intervals are readable and the large metropolitan
    effect is not compressed. Rows use light table banding, labels sit in a left
    column, and the numbers sit in a right column. No descriptive paragraph is placed
    on the plot. All figure text avoids em-dashes and colons.

Outputs are 600-dpi PNG plus vector PDF, written to output/jacr_revision/.

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
from matplotlib.patches import Rectangle

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE_DIR, "output", "jacr_revision")
RES = json.load(open(os.path.join(OUT, "validated_index_results.json")))

NAVY, TEAL, GRAY = "#12303f", "#0f766e", "#9aa6ae"
BAND, INK, MUTE = "#f1f5f7", "#1d2b36", "#5b6b78"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.linewidth": 0.8, "pdf.fonttype": 42})

# Column geometry in axes-fraction units (shared by both panels)
LABEL_X = 0.015          # left label column, left aligned
FL, FR = 0.345, 0.605    # forest region, left and right edges
STAT_X = 0.640           # numbers column, left aligned


def fmt(r):
    p = r["P"]
    ptxt = "P < 0.001" if p < 0.001 else f"P = {p:.3f}"
    return f"{r['IRR']:.2f} ({r['CI_low']:.2f} to {r['CI_high']:.2f})", ptxt


def _map(v, xmin, xmax, logscale):
    if logscale:
        v, xmin, xmax = np.log(v), np.log(xmin), np.log(xmax)
    return FL + (v - xmin) / (xmax - xmin) * (FR - FL)


def draw_panel(ax, panel_title, rows, xmin, xmax, ticks, logscale, xnote):
    """Draw one forest strip inside a blank axes using axes-fraction geometry."""
    n = len(rows)
    ax.set_xlim(0, 1)
    top, bot = 1.15, -(n - 1) - 1.7        # room for header and x-axis note
    ax.set_ylim(bot, top)
    ax.axis("off")

    ys = [-i for i in range(n)]

    # table banding across the full width
    for i, y in enumerate(ys):
        if i % 2 == 0:
            ax.add_patch(Rectangle((0.0, y - 0.5), 1.0, 1.0, facecolor=BAND,
                                   edgecolor="none", zorder=0))

    # reference line at IRR = 1 spanning the estimate rows
    if xmin <= 1 <= xmax:
        xref = _map(1.0, xmin, xmax, logscale)
        ax.plot([xref, xref], [ys[-1] - 0.5, ys[0] + 0.5], ls="--", lw=1.0,
                color="#b7c2ca", zorder=1)

    # panel title and column headers, on the header line
    ax.text(LABEL_X, top - 0.15, panel_title, fontsize=10.5, fontweight="bold",
            color=NAVY, va="center", ha="left")
    ax.text(STAT_X, top - 0.15, "IRR (95% CI)          P value", fontsize=9.2,
            fontweight="bold", color=NAVY, va="center", ha="left")

    # estimate rows
    for y, r in zip(ys, rows):
        est = r["est"]
        sig = est["P"] < 0.05
        col = NAVY if sig else GRAY
        xp = _map(est["IRR"], xmin, xmax, logscale)
        xlo = _map(max(est["CI_low"], xmin), xmin, xmax, logscale)
        xhi = _map(min(est["CI_high"], xmax), xmin, xmax, logscale)
        ax.plot([xlo, xhi], [y, y], color=col, lw=2.0, zorder=3,
                solid_capstyle="round")
        ax.plot([xlo, xlo], [y - 0.09, y + 0.09], color=col, lw=1.6, zorder=3)
        ax.plot([xhi, xhi], [y - 0.09, y + 0.09], color=col, lw=1.6, zorder=3)
        ax.scatter([xp], [y], s=78, color=(col if sig else "white"),
                   edgecolor=col, linewidth=1.8, zorder=4)
        ax.text(LABEL_X, y, r["label"], fontsize=9.4, color=INK, va="center", ha="left")
        est_txt, p_txt = fmt(est)
        wt = "bold" if sig else "normal"
        cc = "#0d2733" if sig else MUTE
        ax.text(STAT_X, y, f"{est_txt}     {p_txt}", fontsize=9.2, fontweight=wt,
                color=cc, va="center", ha="left")

    # x-axis for the forest region
    axis_y = ys[-1] - 0.62
    ax.plot([FL, FR], [axis_y, axis_y], color="#8a97a1", lw=0.9)
    for t in ticks:
        xt = _map(t, xmin, xmax, logscale)
        ax.plot([xt, xt], [axis_y, axis_y - 0.10], color="#8a97a1", lw=0.9)
        ax.text(xt, axis_y - 0.34, f"{t:g}", fontsize=8.4, color=MUTE,
                va="center", ha="center")
    ax.text((FL + FR) / 2, axis_y - 0.85, xnote, fontsize=8.3, color=MUTE,
            va="center", ha="center")


def build_figure(title, footer, panels, stem):
    heights = [len(p["rows"]) + 2.1 for p in panels]
    fig = plt.figure(figsize=(9.6, 0.52 * sum(heights) + 1.1))
    gs = fig.add_gridspec(len(panels), 1, height_ratios=heights,
                          hspace=0.30, left=0.02, right=0.99, top=0.90, bottom=0.055)
    for i, p in enumerate(panels):
        ax = fig.add_subplot(gs[i])
        draw_panel(ax, p["title"], p["rows"], p["xmin"], p["xmax"],
                   p["ticks"], p["log"], p["xnote"])
    fig.suptitle(title, x=0.02, ha="left", fontsize=14, fontweight="bold",
                 color=NAVY, y=0.975)
    fig.text(0.02, 0.018, footer, ha="left", fontsize=8.2, color=MUTE)
    for ext, dpi in [("png", 600), ("pdf", None)]:
        fig.savefig(os.path.join(OUT, f"{stem}.{ext}"), dpi=dpi,
                    bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {stem}.png and {stem}.pdf")


DEP_TICKS = [0.9, 1.0, 1.1]
DEP_RANGE = (0.85, 1.13)
MET_TICKS = [1, 2, 5, 10, 20]
MET_RANGE = (0.9, 20)
DEP_NOTE = "IRR per 10-point rise in deprivation (below 1 lower capacity, above 1 higher)"
MET_NOTE = "IRR, metropolitan versus nonmetropolitan (log scale)"

# ---- Figure 1B, our EDI unadjusted vs adjusted ----------------------------
e = RES["EDI_models"]["outcomes"]
build_figure(
    "Figure 1B.  Area deprivation and accredited cardiac imaging capacity",
    "Economic Deprivation Index, negative binomial regression with population offset, "
    "n = 3,029 counties.  Filled marker significant, open marker not significant.",
    [
        {"title": "Area deprivation, per 10-point increase", "log": False,
         "xmin": DEP_RANGE[0], "xmax": DEP_RANGE[1], "ticks": DEP_TICKS, "xnote": DEP_NOTE,
         "rows": [
             {"label": "Cardiac MRI, unadjusted", "est": e["cmr_facility_count"]["unadjusted"]},
             {"label": "Cardiac MRI, adjusted for metro", "est": e["cmr_facility_count"]["adjusted"]},
             {"label": "Cardiac CT, unadjusted", "est": e["cct_facility_count"]["unadjusted"]},
             {"label": "Cardiac CT, adjusted for metro", "est": e["cct_facility_count"]["adjusted"]},
         ]},
        {"title": "Metropolitan status (from the adjusted models)", "log": True,
         "xmin": MET_RANGE[0], "xmax": MET_RANGE[1], "ticks": MET_TICKS, "xnote": MET_NOTE,
         "rows": [
             {"label": "Cardiac MRI capacity", "est": e["cmr_facility_count"]["metro_in_adjusted"]},
             {"label": "Cardiac CT capacity", "est": e["cct_facility_count"]["metro_in_adjusted"]},
         ]},
    ],
    "Figure1B_Unadjusted_vs_Adjusted")

# ---- Figure S, EDI vs external SDI, CMR outcome ---------------------------
s = RES["SDI_models"]["outcomes"]["cmr_facility_count"]
ec = e["cmr_facility_count"]
build_figure(
    "Figure S.  External validation with a published deprivation index",
    "Cardiac MRI outcome. Our EDI compared with the Robert Graham Center Social "
    "Deprivation Index (SDI, 2015 to 2019).  Filled marker significant, open marker not significant.",
    [
        {"title": "Area deprivation and CMR capacity, per 10-point increase", "log": False,
         "xmin": DEP_RANGE[0], "xmax": DEP_RANGE[1], "ticks": DEP_TICKS, "xnote": DEP_NOTE,
         "rows": [
             {"label": "Unadjusted, our EDI", "est": ec["unadjusted"]},
             {"label": "Unadjusted, Graham Center SDI", "est": s["unadjusted"]},
             {"label": "Adjusted for metro, our EDI", "est": ec["adjusted"]},
             {"label": "Adjusted for metro, Graham SDI", "est": s["adjusted"]},
         ]},
        {"title": "Metropolitan status and CMR capacity (from the adjusted models)", "log": True,
         "xmin": MET_RANGE[0], "xmax": MET_RANGE[1], "ticks": MET_TICKS, "xnote": MET_NOTE,
         "rows": [
             {"label": "Our EDI model", "est": ec["metro_in_adjusted"]},
             {"label": "Graham Center SDI model", "est": s["metro_in_adjusted"]},
         ]},
    ],
    "Figure_SDI_External_Validation")
