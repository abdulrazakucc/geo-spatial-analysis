# This is the `webapp` branch

`main` holds the analysis: the pipeline, the data, the generated figures and
tables, and the validation gate that checks the manuscript against the data.
It is kept journal-agnostic and free of anything a reviewer does not need.

This branch holds everything else.

## What lives here and not on `main`

| Path | What it is |
|---|---|
| `webapp/` | Read-only FastAPI + MapLibre GL dashboard. Loads the same `county_analytic_dataset.csv` and serves an interactive county map. Decoupled from the pipeline |
| `Dockerfile` | Container for the dashboard, uvicorn on :7860 |
| `DEPLOYMENT.md` | Hugging Face Spaces deployment notes |
| `requirements-web.txt` | Dashboard dependencies, separate from the analysis stack |
| `output/presentation/`, `output/documents/` | Slide deck and methodology PDF |
| `output/workflow/` | Workflow diagram PDF |
| `output/requested/` | Collaborator-facing bundle, duplicating figures and tables |
| `output/supplementary_data/` | Older duplicate of the regression text output |
| `docs/reference/` | Third-party and internal working documents |
| `docs/Results_and_Interpretation_Guide.md` | Hand-maintained narrative summary. **Do not quote numbers from it** — two wrong values reached an earlier submission this way. Quote generated output instead |
| `code/generate_requested_outputs.py` | Builds `output/requested/` |

## Running the dashboard

```bash
pip install -r requirements-web.txt
python webapp/app.py
```

Then open <http://localhost:8050/?token=acr-cardiac-2026> in Chrome or Firefox.
Not VS Code's Simple Browser, which blocks the map CDN.

Access is gated by a `?token=` parameter checked against the `VALID_TOKENS`
dictionary hardcoded in `webapp/app.py`. That is share-link obscurity, not
authentication. Do not put anything sensitive behind it.

## Keeping in step with `main`

The dashboard reads `data/processed/county_analytic_dataset.csv`, which is
produced on `main`. When the analysis changes, merge `main` into this branch so
the dashboard serves current numbers:

```bash
git checkout webapp
git merge main
```

Nothing on this branch feeds back into the analysis, so the merge only ever
travels in that direction.

## Stale artifacts warning

Several files under `output/` on this branch have no generator in `code/` and
were last written on 21 July 2026, before the rurality-adjusted revision. They
still carry the retired "ADI" label and pre-adjustment estimates:

- `output/tables/Table2_Regression_Results.docx` — no metropolitan adjustment
- `output/tables/Table3_Sensitivity_Analyses.docx` — "ADI" label
- `output/tables/Complete_Statistical_Results.docx` — "ADI" label
- `output/requested/Table1_*`, `Table2_*`, `Table3_*`
- `output/figures/Figure1_JACC_Publication.*`, `Cardiac_Imaging_Atlas_US.*`,
  `PanelA_CMR_Choropleth.*`, `PanelB_CCT_Choropleth.*`

They are kept here for history only. **Do not submit them to a journal.**
Manuscript Tables 1 to 3 live in the manuscript itself, where
`code/12_manuscript_numbers.py` checks them cell by cell.
