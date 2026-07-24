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
import matplotlib.colors as mcolors
from matplotlib.patches import FancyBboxPatch
from matplotlib.patheffects import withStroke

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE_DIR, "output", "jacr_revision")
RES = json.load(open(os.path.join(OUT, "validated_index_results.json")))

# Palette, refined for an elegant journal look
INK    = "#16232e"     # near-black text
TEAL   = "#0f766e"     # CMR outcome and our EDI
INDIGO = "#3d5a99"     # CCT outcome
AMBER  = "#bd6b16"     # external Graham SDI
PAGE   = "#ffffff"
MUTE   = "#61707b"     # secondary text
HAIR   = "#e4eaee"     # hairline rules
FRAME  = "#e8edf0"     # panel frame

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10.5, "axes.linewidth": 0.8, "pdf.fonttype": 42,
    "savefig.dpi": 600, "figure.dpi": 150,
})

# Column geometry in axes-fraction units
LABEL_X = 0.028
FL, FR  = 0.360, 0.605
STAT_X  = 0.648


def tint(color, amount):
    """Blend a colour toward white. amount 0 keeps colour, 1 gives white."""
    r, g, b = mcolors.to_rgb(color)
    return (r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount)


def fmt(r):
    p = r["P"]
    ptxt = "P < 0.001" if p < 0.001 else f"P = {p:.3f}"
    return f"{r['IRR']:.2f} ({r['CI_low']:.2f} to {r['CI_high']:.2f})", ptxt


def _map(v, xmin, xmax, logscale):
    if logscale:
        v, xmin, xmax = np.log(v), np.log(xmin), np.log(xmax)
    return FL + (v - xmin) / (xmax - xmin) * (FR - FL)


def _rrect(ax, x, y, w, h, fc, ec="none", lw=0, r=0.02, z=0):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle=f"round,pad=0,rounding_size={r}", facecolor=fc,
                 edgecolor=ec, linewidth=lw, zorder=z, mutation_aspect=0.55,
                 clip_on=False))


def draw_panel(ax, panel_title, accent, rows, xmin, xmax, ticks, logscale,
               xnote, marker="o", arrows=False):
    n = len(rows)
    ax.set_xlim(0, 1)
    top, bot = 1.55, -(n - 1) - 1.9
    ax.set_ylim(bot, top)
    ax.axis("off")
    ys = [-i for i in range(n)]

    # soft panel frame
    _rrect(ax, -0.005, ys[-1] - 0.62, 1.01, (top - 0.05) - (ys[-1] - 0.62),
           fc=PAGE, ec=FRAME, lw=1.3, r=0.02, z=0)

    # tinted header band
    _rrect(ax, -0.005, top - 0.52, 1.01, 0.50, fc=tint(accent, 0.90),
           ec="none", r=0.02, z=0.5)

    # highlight band behind each significant row, soft neutral behind the rest
    for y, r in zip(ys, rows):
        sig = r["est"]["P"] < 0.05
        fc = tint(r["color"], 0.86) if sig else "#f7f9fa"
        _rrect(ax, -0.005, y - 0.5, 1.01, 1.0, fc=fc, ec="none", r=0.015, z=0.6)

    # accent chip and panel title
    _rrect(ax, LABEL_X, top - 0.42, 0.020, 0.30, fc=accent, ec="none", r=0.008, z=2)
    ax.text(LABEL_X + 0.034, top - 0.27, panel_title, fontsize=11.2,
            fontweight="bold", color=INK, va="center", ha="left")
    ax.text(STAT_X, top - 0.27, "IRR (95% CI)", fontsize=9.3, fontweight="bold",
            color=INK, va="center", ha="left")
    ax.text(STAT_X + 0.208, top - 0.27, "P value", fontsize=9.3, fontweight="bold",
            color=INK, va="center", ha="left")

    # reference line at IRR = 1
    if xmin <= 1 <= xmax:
        xref = _map(1.0, xmin, xmax, logscale)
        ax.plot([xref, xref], [ys[-1] - 0.5, ys[0] + 0.5], ls=(0, (3, 3)), lw=1.2,
                color="#b4c0c8", zorder=1.2)
        ax.text(xref, ys[0] + 0.62, "no effect", fontsize=7.6, style="italic",
                color="#9aa7b0", va="bottom", ha="center")

    halo = [withStroke(linewidth=3.4, foreground="white")]
    for y, r in zip(ys, rows):
        est = r["est"]
        sig = est["P"] < 0.05
        col = r["color"]
        xp = _map(est["IRR"], xmin, xmax, logscale)
        xlo = _map(max(est["CI_low"], xmin), xmin, xmax, logscale)
        xhi = _map(min(est["CI_high"], xmax), xmin, xmax, logscale)
        ax.plot([xlo, xhi], [y, y], color=col, lw=2.6, zorder=3,
                solid_capstyle="round", path_effects=halo)
        for xc in (xlo, xhi):
            ax.plot([xc, xc], [y - 0.10, y + 0.10], color=col, lw=2.2, zorder=3)
        ax.scatter([xp], [y], s=150 if sig else 118, marker=marker,
                   color=(col if sig else "white"), edgecolor=col,
                   linewidth=2.3, zorder=4, path_effects=halo)
        ax.text(LABEL_X, y, r["label"], fontsize=9.8,
                color=(INK if sig else "#33434e"),
                fontweight=("bold" if sig else "normal"), va="center", ha="left")
        est_txt, p_txt = fmt(est)
        ax.text(STAT_X, y, est_txt, fontsize=9.6, fontweight=("bold" if sig else "normal"),
                color=(col if sig else MUTE), va="center", ha="left")
        ax.text(STAT_X + 0.208, y, p_txt, fontsize=9.6,
                fontweight=("bold" if sig else "normal"),
                color=(col if sig else MUTE), va="center", ha="left")

    # forest x-axis
    axis_y = ys[-1] - 0.52
    ax.plot([FL, FR], [axis_y, axis_y], color="#aab4bc", lw=1.0)
    for t in ticks:
        xt = _map(t, xmin, xmax, logscale)
        ax.plot([xt, xt], [axis_y, axis_y - 0.09], color="#aab4bc", lw=1.0)
        ax.text(xt, axis_y - 0.28, f"{t:g}", fontsize=8.6, color=MUTE, va="center", ha="center")

    if arrows:
        yb = axis_y - 0.62
        ax.annotate("", xy=(FL - 0.005, yb), xytext=(FL + 0.085, yb),
                    arrowprops=dict(arrowstyle="->", color="#9aa7b0", lw=1.1))
        ax.annotate("", xy=(FR + 0.005, yb), xytext=(FR - 0.085, yb),
                    arrowprops=dict(arrowstyle="->", color="#9aa7b0", lw=1.1))
        ax.text(FL + 0.095, yb, "lower capacity", fontsize=7.9, color=MUTE, va="center", ha="left")
        ax.text(FR - 0.095, yb, "higher capacity", fontsize=7.9, color=MUTE, va="center", ha="right")
        ax.text((FL + FR) / 2, yb - 0.30, xnote, fontsize=8.3, color=MUTE, va="center", ha="center")
    else:
        ax.text((FL + FR) / 2, axis_y - 0.66, xnote, fontsize=8.3, color=MUTE, va="center", ha="center")


def legend_row(fig, y, items):
    """Draw a compact rounded colour key as a single row near the top."""
    ax = fig.add_axes([0.0, y, 1.0, 0.05]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    x = 0.028
    for label, color, filled in items:
        ax.scatter([x], [0.5], s=104, color=(color if filled else "white"),
                   edgecolor=color, linewidth=2.2, transform=ax.transAxes,
                   path_effects=[withStroke(linewidth=3.0, foreground="white")])
        ax.text(x + 0.017, 0.5, label, fontsize=9.3, color=INK, va="center",
                ha="left", transform=ax.transAxes)
        x += 0.017 + 0.0108 * len(label) + 0.032


def build_figure(title, subtitle, footer, legend_items, panels, stem):
    heights = [len(p["rows"]) + 2.35 for p in panels]
    fig = plt.figure(figsize=(9.2, 0.56 * sum(heights) + 1.6))
    gs = fig.add_gridspec(len(panels), 1, height_ratios=heights, hspace=0.40,
                          left=0.02, right=0.985, top=0.845, bottom=0.055)
    for i, p in enumerate(panels):
        ax = fig.add_subplot(gs[i])
        draw_panel(ax, p["title"], p["accent"], p["rows"], p["xmin"], p["xmax"],
                   p["ticks"], p["log"], p["xnote"],
                   marker=p.get("marker", "o"), arrows=p.get("arrows", False))
    fig.suptitle(title, x=0.028, ha="left", fontsize=15.5, fontweight="bold",
                 color=INK, y=0.988)
    fig.text(0.028, 0.928, subtitle, ha="left", fontsize=9.6, color=MUTE)
    fig.add_artist(plt.Line2D([0.028, 0.30], [0.912, 0.912], color=TEAL, lw=2.4))
    legend_row(fig, 0.868, legend_items)
    fig.text(0.028, 0.014, footer, ha="left", fontsize=8.3, color=MUTE)
    for ext, dpi in [("png", 600), ("pdf", None)]:
        fig.savefig(os.path.join(OUT, f"{stem}.{ext}"), dpi=dpi,
                    bbox_inches="tight", pad_inches=0.24, facecolor="white")
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
    "The deprivation signal for cardiac MRI disappears once metropolitan status is taken into account.",
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
         "xmin": MET_RANGE[0], "xmax": MET_RANGE[1], "ticks": MET_TICKS, "xnote": MET_NOTE, "marker": "D",
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
    "A published outside index does not reproduce our unadjusted result, yet both agree the driver is metropolitan status.",
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
         "xmin": MET_RANGE[0], "xmax": MET_RANGE[1], "ticks": MET_TICKS, "xnote": MET_NOTE, "marker": "D",
         "rows": [
             {"label": "Our EDI model", "color": TEAL, "est": ec["metro_in_adjusted"]},
             {"label": "Graham Center SDI model", "color": AMBER, "est": s["metro_in_adjusted"]},
         ]},
    ],
    "Figure_SDI_External_Validation")
