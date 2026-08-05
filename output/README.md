# Output Directory Guide

This folder contains all publication-ready outputs from the geographic disparities analysis.
Everything is organized into clear subfolders for easy navigation.

## Folder Structure

```
output/
├── figures/              <- All maps, charts, and visualizations
├── tables/               <- All Word-formatted tables for manuscript
├── documents/            <- Methodology PDF, presentation slides
├── supplementary_data/   <- Raw text results, JSON statistics
└── README.md             <- This file
```

---

## Figures

| File | Description |
|------|-------------|
| `Figure1_Choropleth.png` | Two-panel US county map showing CMR and CCT facility rates |
| `PanelA_CMR_Choropleth.png` | Standalone CMR map (for separate use) |
| `PanelB_CCT_Choropleth.png` | Standalone CCT map (for separate use) |
| `Figure2_SVI_vs_EDI_Comparison.png` | 4-panel comparison: SVI map, EDI map, CMR overlay, scatter |
| `Figure2_SVI_vs_EDI_Comparison.pdf` | Same as above in vector format |
| `Figure3_EDI_Quintile_Rates.png` | Bar chart: CMR/CCT rates by EDI quintile with error bars |
| `Figure3_EDI_Quintile_Rates.pdf` | Same as above in vector format |

## Tables (Word Format)

| File | Description |
|------|-------------|
| `Table1_Capacity_by_SVI_Rurality.docx` | Descriptive: facility counts/rates by SVI quartile and metro status |
| `Table2_Regression_Results.docx` | Primary Negative Binomial regression results (SVI) |
| `Table3_Sensitivity_Analyses.docx` | Stratified and quartile contrast results |
| `Table4_SVI_vs_EDI_Comparison.docx` | **Key table:** Side-by-side SVI vs EDI comparison + quintile rates |
| `Supplementary_Table_EDI_Regression.docx` | EDI regression details |
| `Complete_Statistical_Results.docx` | All statistical tests in one reference table |

## Documents

| File | Description |
|------|-------------|
| `Methodology_and_Results.pdf` | Full methods and results write-up (PDF) |
| `ACR_Cardiac_Imaging_Presentation.pptx` | 8-slide presentation deck |

## Supplementary Data

| File | Description |
|------|-------------|
| `Regression_Results.txt` | Plain-text SVI regression output |
| `EDI_Regression_Results.txt` | Plain-text EDI regression output |
| `Table1_Formatted.txt` | Plain-text Table 1 |
| `additional_statistics.json` | JSON with extra computed statistics |

---

## Key Finding

**EDI detects a significant 6.3% decrease in CMR capacity per 10-percentile increase
in area deprivation (IRR = 0.937, p = 0.002). SVI shows no association (p = 0.681).**

See `Table4_SVI_vs_EDI_Comparison.docx` for the full comparison.
