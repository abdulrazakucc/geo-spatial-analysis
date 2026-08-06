# Output Directory Guide

Everything in this folder is generated. Nothing here is edited by hand, and any
of it can be rebuilt from the committed data:

```bash
python code/00_run_all.py --with-present
```

If a file here ever disagrees with the manuscript, the generated file is
correct and the manuscript needs fixing. That rule exists because an earlier
submission carried two numbers that had been transcribed by hand.

---

## Start here if you are reviewing the analysis

### `validation/` — the paper checked against the data

| File | What it is |
|---|---|
| `manuscript_check.txt` | Every value in the manuscript compared with the data, cell by cell. Current result: **123 checks, 0 mismatches** |
| `manuscript_numbers.txt` | Every number the paper quotes, recomputed and formatted for reading |
| `manuscript_numbers.json` | The same values at full precision, plus model diagnostics |

Produced by `code/12_manuscript_numbers.py`. The JSON also carries a
`model_diagnostics` block with outcome overdispersion, negative binomial versus
Poisson AIC for all eight models, and sensitivity to fixing the dispersion
parameter. See `docs/REPRODUCIBILITY.md` for how to read it.

### `jacr_revision/` — the current submission's figures and results

| File | What it is |
|---|---|
| `Figure1B_Unadjusted_vs_Adjusted.pdf` / `.png` | Manuscript Figure 1B. SVI and EDI, each unadjusted and adjusted, with metropolitan status in its own panel |
| `Figure_SDI_External_Validation.pdf` / `.png` | Figure S. Our EDI against the external Graham Center SDI |
| `validated_index_results.txt` | External validation results, readable |
| `validated_index_results.json` | The same at full precision; Figures 1B and S are drawn from this file, so plotted and reported values cannot drift apart |
| `JACR_Revision_Report.html` | Narrative summary of the revision |

---

## The rest

| Folder | Contents |
|---|---|
| `figures/` | Manuscript and atlas figures, PNG and TIFF at journal resolution |
| `tables/` | Word tables 1-4 and supplementary tables, plus CSV equivalents |
| `supplementary_data/` | Regression results as plain text, and `additional_statistics.json` |
| `models/` | Full regression output, including the Poisson comparisons |
| `requested/` | Collaborator-facing bundle; duplicates of the figures and tables above |
| `documents/` | Methodology PDF and the slide deck |
| `presentation/` | Slide deck |
| `workflow/` | Workflow diagram PDF (optional; needs WeasyPrint, skipped if absent) |

`requested/` deliberately duplicates files from `figures/` and `tables/` so the
folder can be sent as a self-contained package. It is not a separate analysis.

---

## Which figure is which

Several figures were regenerated during revision. If you are assembling a
submission, take figures from `jacr_revision/` and `figures/`, not from any
older copy.

| Manuscript element | File |
|---|---|
| Figure 1A | `figures/Figure1_JACC_Publication.tiff` |
| Figure 1B | `jacr_revision/Figure1B_Unadjusted_vs_Adjusted.pdf` |
| Figure S (supplementary) | `jacr_revision/Figure_SDI_External_Validation.pdf` |
| Figures 2 and 3 | `requested/Figure2_SVI_vs_EDI_Comparison.pdf`, `requested/Figure3_EDI_Quintile_Rates.pdf` |
| Tables 1-3 | `tables/Table1_...`, `tables/Table2_...`, `tables/Table3_...` |
| Table 4 | `tables/Table4_External_Validation_SDI.docx` |

Note that `tables/Table4_SVI_vs_EDI_Comparison.docx` is a *different*, older
comparison table and is **not** manuscript Table 4.
