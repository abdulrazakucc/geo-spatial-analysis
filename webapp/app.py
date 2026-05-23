"""
ACR Cardiac Imaging Geographic Disparities - Web Application
============================================================
FastAPI application with token-based access control.
Serves an interactive dashboard with MapLibre GL JS maps.

Run:
    python webapp/app.py

Access:
    http://localhost:8000/?token=acr-cardiac-2026
"""

import os
import json
import hashlib
import secrets
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import jinja2
import uvicorn

# ===========================================================================
# Configuration
# ===========================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
WEBAPP_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"

# Access tokens - share these links with authorized collaborators
# Format: token -> {"name": "...", "email": "..."}
VALID_TOKENS = {
    "acr-cardiac-2026": {"name": "Dr. Naeem", "role": "PI"},
    "shiloh-analyst-2026": {"name": "Shiloh Johnson", "role": "Analyst"},
    # Add more tokens as needed
}

# Generate a session secret
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(32))

# ===========================================================================
# App Setup
# ===========================================================================
app = FastAPI(
    title="ACR Cardiac Imaging - Geographic Disparities Dashboard",
    docs_url=None,  # Disable public API docs
    redoc_url=None,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR / "static")), name="static")

# Templates
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(WEBAPP_DIR / "templates")),
    autoescape=True,
)
jinja_env.policies['json.dumps_kwargs'] = {'ensure_ascii': False}


def render_template(name: str, **context) -> HTMLResponse:
    """Render a Jinja2 template and return HTMLResponse."""
    template = jinja_env.get_template(name)
    html = template.render(**context)
    return HTMLResponse(content=html)


# ===========================================================================
# Auth Middleware
# ===========================================================================
def verify_token(token: str = Query(None)):
    """Verify access token from query parameter."""
    if token not in VALID_TOKENS:
        raise HTTPException(
            status_code=403,
            detail="Access denied. Please use the authorized link provided to you."
        )
    return VALID_TOKENS[token]


# ===========================================================================
# Load Data (cached)
# ===========================================================================
_data_cache = {}

def get_analytic_data():
    if "df" not in _data_cache:
        df = pd.read_csv(DATA_DIR / "county_analytic_dataset.csv", dtype={"county_fips": str})
        _data_cache["df"] = df
    return _data_cache["df"]


def get_summary_stats():
    """Compute summary statistics for the dashboard."""
    df = get_analytic_data()
    
    total_counties = len(df)
    total_cmr = int(df['cmr_facility_count'].sum())
    total_cct = int(df['cct_facility_count'].sum())
    counties_with_cmr = int((df['cmr_facility_count'] > 0).sum())
    counties_with_cct = int((df['cct_facility_count'] > 0).sum())
    pct_no_cmr = round((1 - counties_with_cmr / total_counties) * 100, 1)
    pct_no_cct = round((1 - counties_with_cct / total_counties) * 100, 1)
    
    # Metro vs non-metro
    metro = df[df['metro_indicator'] == 1]
    nonmetro = df[df['metro_indicator'] == 0]
    
    return {
        "total_counties": total_counties,
        "total_cmr_facilities": total_cmr,
        "total_cct_facilities": total_cct,
        "counties_with_cmr": counties_with_cmr,
        "counties_with_cct": counties_with_cct,
        "pct_no_cmr": pct_no_cmr,
        "pct_no_cct": pct_no_cct,
        "metro_cmr": int(metro['cmr_facility_count'].sum()),
        "nonmetro_cmr": int(nonmetro['cmr_facility_count'].sum()),
        "metro_cct": int(metro['cct_facility_count'].sum()),
        "nonmetro_cct": int(nonmetro['cct_facility_count'].sum()),
        "metro_counties": len(metro),
        "nonmetro_counties": len(nonmetro),
    }


def get_table1_data():
    """Load Table 1 data."""
    path = BASE_DIR / "output" / "tables" / "table1_descriptive.csv"
    if path.exists():
        return pd.read_csv(path).to_dict(orient='records')
    return []


def get_regression_summary():
    """Load regression results."""
    path = BASE_DIR / "output" / "models" / "regression_results.txt"
    if path.exists():
        return path.read_text()
    return "Regression results not available."


# ===========================================================================
# Routes
# ===========================================================================
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, token: str = Query(None)):
    """Main dashboard page with token authentication."""
    if token is None:
        return render_template("login.html")
    
    user = verify_token(token)
    
    stats = get_summary_stats()
    table1 = get_table1_data()
    regression = get_regression_summary()
    
    return render_template(
        "dashboard.html",
        token=token,
        user=user,
        stats=stats,
        table1=table1,
        regression=regression,
    )


@app.get("/api/stats")
async def api_stats(user=Depends(verify_token)):
    """API endpoint for summary statistics."""
    return get_summary_stats()


@app.get("/api/table1")
async def api_table1(user=Depends(verify_token)):
    """API endpoint for Table 1 data."""
    return get_table1_data()


@app.get("/api/svi-distribution")
async def api_svi_distribution(user=Depends(verify_token)):
    """API endpoint for SVI distribution chart data."""
    df = get_analytic_data()
    df_valid = df[df['rate_excluded'] == 0].copy()
    
    # Facility rates by SVI decile
    df_valid['svi_decile'] = pd.qcut(df_valid['svi_percentile'], 10, labels=False, duplicates='drop') + 1
    
    grouped = df_valid.groupby('svi_decile').agg(
        mean_cmr_rate=('cmr_rate_per_100k', 'mean'),
        mean_cct_rate=('cct_rate_per_100k', 'mean'),
        n_counties=('county_fips', 'count')
    ).reset_index()
    
    return grouped.to_dict(orient='records')


# ===========================================================================
# Run
# ===========================================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ACR Cardiac Imaging - Geographic Disparities Dashboard")
    print("=" * 60)
    print(f"\n  Access URLs (share with authorized users):")
    print(f"  ─────────────────────────────────────────────")
    for token, info in VALID_TOKENS.items():
        print(f"  {info['name']}: http://localhost:8050/?token={token}")
    print(f"\n  Unauthorized access will be blocked.")
    print(f"  Press Ctrl+C to stop the server.\n")
    
    port = int(os.environ.get("PORT", 8050))
    uvicorn.run(app, host="0.0.0.0", port=port)
