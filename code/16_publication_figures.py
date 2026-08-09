#!/usr/bin/env python3
"""
16_publication_figures.py
=========================
Builds every figure in the manuscript and its supplement, at 600 dpi.

Each figure reads its values from the generated results when it is drawn, so a
plotted number cannot drift from the table it accompanies. Nothing here refits
a model or recomputes a statistic.

Inputs
    output/validation/manuscript_numbers.json    descriptives, models, quintiles
    output/results/index_comparison_results.json SVI / EDI / SDI comparison
    data/processed/county_analytic_geo.gpkg      county geometry

Outputs
    output/figures/Figure1A_CMR_Choropleth.{png,pdf}
    output/figures/Figure1B_Forest.{png,pdf}
    output/figures/Figure2_External_Validation.{png,pdf}
    output/figures/FigureS1_CCT_Choropleth.{png,pdf}
    output/figures/FigureS2_EDI_Quintiles.{png,pdf}

Run
    python code/16_publication_figures.py
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figure_style as st  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE_DIR, "data", "processed")
FIG = os.path.join(BASE_DIR, "output", "figures")
RESULTS = os.path.join(BASE_DIR, "output", "results")
VALID = os.path.join(BASE_DIR, "output", "validation")
os.makedirs(FIG, exist_ok=True)

st.apply()


def load():
    with open(os.path.join(VALID, "manuscript_numbers.json")) as f:
        numbers = json.load(f)
    with open(os.path.join(RESULTS, "index_comparison_results.json")) as f:
        idx = json.load(f)
    return numbers, idx


def save(fig, stem):
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(FIG, f"{stem}.{ext}"), dpi=st.DPI)
    plt.close(fig)
    print(f"  wrote {stem}.png / .pdf")


# ----------------------------------------------------------------- choropleth
def _draw(ax, frame, rate_col, state_lines=True):
    colours = [st.fill_for(r, bool(x)) for r, x in
               zip(frame[rate_col], frame["rate_excluded"])]
    frame.plot(ax=ax, color=colours, edgecolor="#ffffff", linewidth=0.13)
    if state_lines and len(frame):
        frame.dissolve(by="state_abbr").boundary.plot(
            ax=ax, color="#95a3b0", linewidth=0.45)
    ax.set_axis_off()
    ax.set_aspect("equal")


def choropleth(parts, rate_col, modality, title, stem, numbers):
    """Lower 48 with Alaska and Hawaii drawn in their own inset axes."""
    lower48, ak, hi = parts
    d = numbers["descriptives"]
    is_cmr = modality == "cmr"
    n_fac = d["cmr_facilities"] if is_cmr else d["cct_facilities"]
    n_cty = d["counties_with_cmr"] if is_cmr else d["counties_with_cct"]
    pct = d["counties_with_cmr_pct"] if is_cmr else d["counties_with_cct_pct"]

    fig = plt.figure(figsize=(13.2, 7.9))
    ax = fig.add_axes([0.055, 0.155, 0.92, 0.735])
    _draw(ax, lower48, rate_col)

    if len(ak):
        axa = fig.add_axes([0.035, 0.105, 0.185, 0.195])
        _draw(axa, ak, rate_col, state_lines=False)
        axa.text(0.5, -0.02, "Alaska", transform=axa.transAxes, ha="center",
                 va="top", fontsize=9.4, color=st.MUTE)
    if len(hi):
        axh = fig.add_axes([0.225, 0.115, 0.10, 0.11])
        _draw(axh, hi, rate_col, state_lines=False)
        axh.text(0.5, -0.04, "Hawaii", transform=axh.transAxes, ha="center",
                 va="top", fontsize=9.4, color=st.MUTE)

    st.title_block(fig, title,
                   "Rate per 100,000 adults aged ≥45 years. "
                   "Alaska and Hawaii shown as insets, not to scale.",
                   right=f"{n_fac:,} facilities   ·   {n_cty:,} counties ({pct:.1f}%)")
    st.bin_legend(fig, [0.44, 0.075, 0.36, 0.055])
    fig.text(0.44, 0.028,
             "White: county excluded from rate calculation (<1,000 adults aged ≥45 years)",
             ha="left", va="bottom", fontsize=9, color=st.MUTE)
    save(fig, stem)


# --------------------------------------------------------------- forest plots
def _marker(irr, p):
    """Filled and coloured when significant; open grey when not."""
    if p >= 0.05:
        return dict(mfc="white", mec="#9aa7b3", color="#9aa7b3", lw=1.7, ms=8.5)
    c = st.TEAL if irr < 1 else st.RUST
    return dict(mfc=c, mec=c, color=c, lw=2.3, ms=9.5)


def _rows(ax, rows, xmin, xmax, log=False):
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(len(rows) - 0.45, -0.55)
    ax.axvline(1, color=st.RULE, lw=1.1, ls=(0, (4, 3)), zorder=0)
    for i, r in enumerate(rows):
        s = _marker(r["irr"], r["p"])
        ax.plot([r["lo"], r["hi"]], [i, i], color=s["color"], lw=s["lw"],
                solid_capstyle="round", zorder=2)
        ax.plot([r["irr"]], [i], "o", mfc=s["mfc"], mec=s["mec"],
                ms=s["ms"], mew=1.9, zorder=3)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["label"] for r in rows], fontsize=11.2, color=st.INK)
    ax.tick_params(axis="y", length=0, pad=8)
    if log:
        ax.set_xscale("log")
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=st.FAINT, lw=0.9, zorder=0)
    ax.set_axisbelow(True)


X_IRR, X_P = 1.44, 1.86


def _stat_text(ax, rows, x_irr=X_IRR, x_p=X_P):
    for i, r in enumerate(rows):
        bold = r["p"] < 0.05
        ax.text(x_irr, i, f"{r['irr']:.2f} ({r['lo']:.2f}–{r['hi']:.2f})",
                transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=11, color=st.INK if bold else st.MUTE,
                fontweight="bold" if bold else "normal")
        p = "<0.001" if r["p"] < 0.001 else f"{r['p']:.3f}"
        ax.text(x_p, i, p, transform=ax.get_yaxis_transform(), ha="right",
                va="center", fontsize=11,
                color=st.INK if bold else st.MUTE,
                fontweight="bold" if bold else "normal")


def _e(block, key):
    e = block[key]
    return dict(irr=e["irr"], lo=e["ci_low"], hi=e["ci_high"], p=e["p"])


def figure1b(numbers):
    M = numbers["regressions"]["models"]
    R = numbers["regressions"]

    def group(outcome):
        out = []
        for idx in ("SVI", "EDI"):
            m = M[f"{idx}_{outcome}"]
            for key, lab in (("unadjusted", "unadjusted"),
                             ("adjusted_metro", "adjusted for metropolitan status")):
                r = _e(m, key)
                r["label"] = f"{idx}, {lab}"
                out.append(r)
        return out

    metro = []
    for outcome, oname in (("CMR", "Cardiac MR"), ("CCT", "Cardiac CT")):
        for idx in ("SVI", "EDI"):
            e = M[f"{idx}_{outcome}"]["metro_effect"]
            metro.append(dict(irr=e["irr"], lo=e["ci_low"], hi=e["ci_high"],
                              p=e["p"], label=f"{oname}, {idx} model"))

    L, W = 0.255, 0.285                 # plot area; stats sit to its right
    fig = plt.figure(figsize=(14.6, 11.0))
    st.title_block(
        fig, "Area disadvantage, metropolitan status, and accredited cardiac imaging capacity",
        f"Negative binomial regression, dispersion estimated, log-population offset "
        f"(adults aged ≥45 years); {R['n_svi']:,} counties (SVI), {R['n_edi']:,} (EDI)",
        y=0.982)

    fig.text(L + X_IRR * W, 0.900, "IRR (95% CI)", ha="right", fontsize=11,
             style="italic", color=st.MUTE)
    fig.text(L + X_P * W, 0.900, "P", ha="right", fontsize=11, style="italic",
             color=st.MUTE)

    for n, (outcome, oname, top) in enumerate(
            (("CMR", "Cardiac MR", 0.630), ("CCT", "Cardiac CT", 0.330))):
        ax = fig.add_axes([L, top, W, 0.205])
        rows = group(outcome)
        _rows(ax, rows, 0.885, 1.075)
        _stat_text(ax, rows)
        fig.text(0.008, top + 0.232, oname, fontsize=13.5, fontweight="bold",
                 color=st.INK)
        ax.set_xticks([0.90, 0.95, 1.00, 1.05])
        if n == 1:
            ax.set_xlabel("IRR per 10-percentile increase in index",
                          fontsize=11.2, color=st.INK, labelpad=9)
        else:
            ax.set_xticklabels([])

    axm = fig.add_axes([L, 0.115, W, 0.110])
    _rows(axm, metro, 1.4, 22, log=True)
    _stat_text(axm, metro)
    axm.set_xticks([2, 4, 8, 16])
    axm.set_xticklabels(["2", "4", "8", "16"])
    axm.set_xlabel("IRR, metropolitan versus nonmetropolitan (log scale)",
                   fontsize=11.2, color=st.INK, labelpad=9)
    fig.text(0.008, 0.243, "Metropolitan status (RUCC 1–3)", fontsize=13.5,
             fontweight="bold", color=st.INK)

    _legend(fig, 0.012)
    save(fig, "Figure1B_Forest")


def _legend(fig, y):
    handles = [
        Line2D([], [], marker="o", ls="", mfc=st.TEAL, mec=st.TEAL, ms=9,
               label="P < 0.05, lower capacity"),
        Line2D([], [], marker="o", ls="", mfc=st.RUST, mec=st.RUST, ms=9,
               label="P < 0.05, higher capacity"),
        Line2D([], [], marker="o", ls="", mfc="white", mec="#9aa7b3", mew=1.9,
               ms=9, label="Not significant"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, y),
               ncol=3, frameon=False, fontsize=11.2, handletextpad=0.5,
               columnspacing=3.2)


def figure2(numbers, idx):
    """EDI against the published SDI, with how much rurality each carries."""
    edi = idx["EDI_models"]["outcomes"]
    sdi = idx["SDI_models"]["outcomes"]
    rl = idx["rurality_link"]

    labels = [("cmr_facility_count", "unadjusted", "Cardiac MR, unadjusted"),
              ("cmr_facility_count", "adjusted", "Cardiac MR, adjusted for metropolitan status"),
              ("cct_facility_count", "unadjusted", "Cardiac CT, unadjusted"),
              ("cct_facility_count", "adjusted", "Cardiac CT, adjusted for metropolitan status")]

    fig = plt.figure(figsize=(15.2, 8.0))
    st.title_block(
        fig, "External validation: a published index reproduces the geography, not the deprivation gradient",
        f"Purpose-built EDI ({idx['EDI_models']['n']:,} counties) versus Robert Graham Center Social "
        f"Deprivation Index ({idx['SDI_models']['n']:,} counties). The two indices agree closely "
        f"(Spearman ρ = {idx['agreement_with_EDI']['spearman_rho']:.2f}) but differ in how much "
        f"rurality they encode.")

    FL, FW = 0.235, 0.235          # forest plot; stats sit to its right
    ax = fig.add_axes([FL, 0.20, FW, 0.63])
    ax.set_ylim(len(labels) - 0.4, -0.6)
    ax.set_xlim(0.885, 1.075)
    ax.axvline(1, color=st.RULE, lw=1.1, ls=(0, (4, 3)), zorder=0)
    ytl = []
    for i, (oc, spec, lab) in enumerate(labels):
        for src, off, colour in ((edi, -0.19, st.TEAL), (sdi, 0.19, st.RUST)):
            e = src[oc][spec]
            r = dict(irr=e["IRR"], lo=e["CI_low"], hi=e["CI_high"], p=e["P"])
            sig = r["p"] < 0.05
            c = colour if sig else "#9aa7b3"
            ax.plot([r["lo"], r["hi"]], [i + off, i + off], color=c,
                    lw=2.3 if sig else 1.7, solid_capstyle="round", zorder=2)
            ax.plot([r["irr"]], [i + off], "o", mfc=c if sig else "white",
                    mec=c, ms=9.5 if sig else 8.5, mew=1.9, zorder=3)
            ax.text(X_IRR, i + off, f"{r['irr']:.2f} ({r['lo']:.2f}–{r['hi']:.2f})",
                    transform=ax.get_yaxis_transform(), ha="right", va="center",
                    fontsize=10.6, color=st.INK if sig else st.MUTE,
                    fontweight="bold" if sig else "normal")
            p = "<0.001" if r["p"] < 0.001 else f"{r['p']:.3f}"
            ax.text(X_P, i + off, p, transform=ax.get_yaxis_transform(),
                    ha="right", va="center", fontsize=10.6,
                    color=st.INK if sig else st.MUTE,
                    fontweight="bold" if sig else "normal")
        ytl.append(lab)
        if i:
            ax.axhline(i - 0.5, color=st.FAINT, lw=0.9, zorder=0)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(ytl, fontsize=11, color=st.INK)
    ax.tick_params(axis="y", length=0, pad=8)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=st.FAINT, lw=0.9, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlabel("IRR per 10-percentile increase in index", fontsize=11.2,
                  color=st.INK, labelpad=9)
    fig.text(FL + X_IRR * FW, 0.862, "IRR (95% CI)", ha="right", fontsize=10.6,
             style="italic", color=st.MUTE)
    fig.text(FL + X_P * FW, 0.862, "P", ha="right", fontsize=10.6,
             style="italic", color=st.MUTE)

    axr = fig.add_axes([0.745, 0.31, 0.195, 0.40])
    vals = [rl["EDI"]["spearman_vs_rucc"], rl["SDI"]["spearman_vs_rucc"]]
    gaps = [rl["EDI"]["gap"], rl["SDI"]["gap"]]
    axr.barh([1, 0], vals, color=[st.TEAL, st.RUST], height=0.30)
    axr.set_ylim(-0.62, 1.62)
    for y, v, g in zip((1, 0), vals, gaps):
        axr.text(v + 0.010, y, f"ρ = {v:.2f}", va="center", fontsize=11.5,
                 color=st.INK)
        axr.text(0.004, y - 0.27, f"{g:.1f}-point nonmetropolitan gap",
                 va="top", fontsize=9.6, color=st.MUTE)
    axr.set_yticks([1, 0])
    axr.set_yticklabels(["EDI", "SDI"], fontsize=11.5, fontweight="bold",
                        color=st.MUTE)
    axr.tick_params(axis="y", length=0, pad=6)
    axr.set_xlim(0, max(vals) * 1.65)
    axr.set_xlabel("Spearman ρ with ordinal RUCC", fontsize=10.6, color=st.INK,
                   labelpad=8)
    axr.spines["left"].set_visible(False)
    axr.grid(axis="x", color=st.FAINT, lw=0.9)
    axr.set_axisbelow(True)
    fig.text(0.835, 0.775, "Rurality carried by each index", ha="center",
             fontsize=12, fontweight="bold", color=st.INK)

    handles = [
        Line2D([], [], marker="o", ls="", mfc=st.TEAL, mec=st.TEAL, ms=9, label="EDI"),
        Line2D([], [], marker="o", ls="", mfc=st.RUST, mec=st.RUST, ms=9,
               label="Graham Center SDI"),
        Line2D([], [], marker="o", ls="", mfc="white", mec="#9aa7b3", mew=1.9,
               ms=9, label="Not significant"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.025),
               ncol=3, frameon=False, fontsize=11.2, columnspacing=3.2)
    save(fig, "Figure2_External_Validation")


def figure_s2(numbers):
    q = numbers["quintiles"]
    cmr = q["cmr_rate_by_edi_quintile"]
    cct = q["cct_rate_by_edi_quintile"]
    n = sum(numbers["table1"][f"edi_q{i}"]["counties"] for i in range(1, 6))

    fig = plt.figure(figsize=(13.4, 6.6))
    st.title_block(
        fig, "Accredited capacity across economic deprivation quintiles",
        f"{n:,} counties with ≥1,000 adults aged ≥45 years and an available EDI value. "
        f"Kruskal-Wallis P < 0.001 for cardiac MR;\nneither gradient is monotonic across "
        f"the intervening quintiles.")

    labels = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    for k, (vals, colour, name, rect) in enumerate((
            (cmr, st.TEAL, "Cardiac MR", [0.065, 0.20, 0.39, 0.56]),
            (cct, st.RUST, "Cardiac CT", [0.575, 0.20, 0.39, 0.56]))):
        ax = fig.add_axes(rect)
        ax.bar(labels, vals, color=colour, width=0.62)
        for i, v in enumerate(vals):
            ax.text(i, v + max(vals) * 0.025, f"{v:.2f}", ha="center",
                    va="bottom", fontsize=12, color=st.INK)
        ax.set_ylim(0, max(vals) * 1.22)
        ax.set_title(name, fontsize=13.5, fontweight="bold", color=st.INK,
                     loc="left", pad=10)
        ax.grid(axis="y", color=st.FAINT, lw=0.9)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", length=0, labelsize=12)
        ax.tick_params(axis="y", labelsize=11)
        if k == 0:
            ax.set_ylabel("Mean county facility rate\nper 100,000 adults ≥45 y",
                          fontsize=11.2, color=st.INK)
            ax.text(0.985, 0.955, f"Q1 vs Q5: {q['q1_over_q5_ratio']:.1f}-fold",
                    transform=ax.transAxes, ha="right", va="top",
                    fontsize=11.5, color=st.MUTE)
        ax.text(0, -0.115, "least deprived", transform=ax.transAxes,
                ha="left", fontsize=10.5, color=st.MUTE)
        ax.text(1, -0.115, "most deprived", transform=ax.transAxes,
                ha="right", fontsize=10.5, color=st.MUTE)
    save(fig, "FigureS2_EDI_Quintiles")


def main():
    numbers, idx = load()
    import geopandas as gpd
    gdf = gpd.read_file(os.path.join(PROC, "county_analytic_geo.gpkg"))
    parts = st.split_for_insets(gdf)

    choropleth(parts, "cmr_rate_per_100k", "cmr",
               "Accredited cardiac MR capacity, US counties",
               "Figure1A_CMR_Choropleth", numbers)
    figure1b(numbers)
    figure2(numbers, idx)
    choropleth(parts, "cct_rate_per_100k", "cct",
               "Accredited cardiac CT capacity, US counties",
               "FigureS1_CCT_Choropleth", numbers)
    figure_s2(numbers)
    print("\n  All figures written at "
          f"{st.DPI} dpi to output/figures/")


if __name__ == "__main__":
    main()
