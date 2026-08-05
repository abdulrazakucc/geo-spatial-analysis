#!/usr/bin/env python3
"""
10_jacr_forest_plots.py
=======================
JACR revision figures. Reads output/jacr_revision/validated_index_results.json
(single source of truth, so numbers and plots can never drift apart) and writes
two publication-quality forest plots.

    Figure1B_Unadjusted_vs_Adjusted   Manuscript Panel B. Three stacked panels. The SVI
                                       and the EDI each get a panel showing CMR and CCT
                                       capacity, unadjusted and adjusted for metropolitan
                                       status, and metropolitan status gets its own panel
                                       because its effect is an order of magnitude larger.
                                       Both indices appear so the panel carries the
                                       paper's claim on its own, that neither index
                                       survives adjustment. Colour marks the modality.

    Figure_SDI_External_Validation     Our self-built EDI compared with the external
                                       Graham Center SDI for the CMR outcome. Colour
                                       marks the index.

Design notes
    Stacked panels with scales matched to the estimates, so the small index confidence
    intervals are readable and the large metropolitan effect is not compressed. Index
    panels use a linear scale, the metropolitan panel a log scale, and the figure legend
    in the manuscript says so. Colour encodes the data series, modality or index, and is
    never reused for panel furniture, which is why panel accents are neutral slate. A
    filled marker means significant and an open marker means not significant. Light table
    banding, a clean sans-serif face, heavy strokes for crisp rendering at 600 dpi, and a
    short colour key. No descriptive paragraph is placed on the plot. All figure text
    avoids em-dashes and colons.

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
AMBER  = "#bd6b16"     # external Graham SDI, and the metropolitan-status panel
SLATE  = "#5b6b7a"     # neutral panel accent, never used for a data series
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
    top, bot = 1.45, -(n - 1) - 1.42
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
    heights = [len(p["rows"]) + 1.85 for p in panels]
    fig = plt.figure(figsize=(9.6, 0.50 * sum(heights) + 1.5))
    gs = fig.add_gridspec(len(panels), 1, height_ratios=heights, hspace=0.30,
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
DEP_NOTE = "IRR per 10-percentile increase in the index (below 1 lower capacity, above 1 higher)"
MET_NOTE = "IRR, metropolitan versus nonmetropolitan (log scale)"


def index_rows(block):
    """Four rows for one index: each modality, unadjusted then adjusted."""
    o = block["outcomes"]
    return [
        {"label": "Cardiac MR, unadjusted", "color": TEAL,
         "est": o["cmr_facility_count"]["unadjusted"]},
        {"label": "Cardiac MR, adjusted for metropolitan status", "color": TEAL,
         "est": o["cmr_facility_count"]["adjusted"]},
        {"label": "Cardiac CT, unadjusted", "color": INDIGO,
         "est": o["cct_facility_count"]["unadjusted"]},
        {"label": "Cardiac CT, adjusted for metropolitan status", "color": INDIGO,
         "est": o["cct_facility_count"]["adjusted"]},
    ]


# ---- Figure 1B, both indices side by side, colour encodes modality --------
# Three panels so the figure carries the paper's central claim on its own:
# neither index survives adjustment, and metropolitan status is what remains.
e = RES["EDI_models"]["outcomes"]
s_svi = RES["SVI_models"]
n_svi, n_edi = RES["SVI_models"]["n"], RES["EDI_models"]["n"]
# The lower panel plots the metropolitan term from the EDI models. The SVI models
# give near-identical values, stated in the footer so the panel cannot be misread
# as belonging to both indices.
svi_met = RES["SVI_models"]["outcomes"]
build_figure(
    "Figure 1B.  Area disadvantage, metropolitan status, and accredited cardiac imaging capacity",
    "Neither index is associated with capacity once metropolitan status is in the model. "
    "Metropolitan status is what remains.",
    f"Negative binomial regression with a log-population offset (adults aged 45 and older). "
    f"n = {n_svi:,} counties for the SVI and {n_edi:,} for the EDI. "
    f"Metropolitan status estimates in the lower panel are from the EDI models. The SVI models give "
    f"{svi_met['cmr_facility_count']['metro_in_adjusted']['IRR']:.2f} for cardiac MR and "
    f"{svi_met['cct_facility_count']['metro_in_adjusted']['IRR']:.2f} for cardiac CT.",
    [("Cardiac MR", TEAL, True), ("Cardiac CT", INDIGO, True),
     ("filled significant", INK, True), ("open not significant", INK, False)],
    [
        {"title": "Social Vulnerability Index, per 10 percentiles", "accent": SLATE, "log": False,
         "xmin": DEP_RANGE[0], "xmax": DEP_RANGE[1], "ticks": DEP_TICKS, "xnote": DEP_NOTE,
         "rows": index_rows(s_svi)},
        {"title": "Economic Deprivation Index, per 10 percentiles", "accent": SLATE, "log": False,
         "xmin": DEP_RANGE[0], "xmax": DEP_RANGE[1], "ticks": DEP_TICKS, "xnote": DEP_NOTE,
         "rows": index_rows(RES["EDI_models"])},
        {"title": "Metropolitan status, from the adjusted models", "accent": AMBER, "log": True,
         "xmin": MET_RANGE[0], "xmax": MET_RANGE[1], "ticks": MET_TICKS, "xnote": MET_NOTE, "marker": "D",
         "rows": [
             {"label": "Cardiac MR capacity", "color": TEAL, "est": e["cmr_facility_count"]["metro_in_adjusted"]},
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
    f"Cardiac MR outcome. Our EDI compared with the Robert Graham Center Social Deprivation Index "
    f"(SDI, 2015 to 2019). Negative binomial regression with a log-population offset (adults aged 45 "
    f"and older). n = {RES['EDI_models']['n']:,} counties for the EDI and "
    f"{RES['SDI_models']['n']:,} for the SDI, which matched "
    f"{RES['sdi_matched_counties']:,} of {RES['total_counties']:,} counties.",
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
