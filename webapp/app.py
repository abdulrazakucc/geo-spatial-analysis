"""
ACR Cardiac Imaging Geographic Disparities - Web Application
============================================================
Production-ready FastAPI application with token-based access control.
Serves an interactive dashboard with MapLibre GL JS maps and Chart.js charts.

Run locally:
    python webapp/app.py
    open http://localhost:8050/?token=acr-cardiac-2026

Deploy (Hugging Face Spaces, Docker):
    uvicorn webapp.app:app --host 0.0.0.0 --port 7860

Configuration (environment variables, all optional):
    ACCESS_TOKENS   JSON map of token -> {"name": ..., "role": ...}
                    Overrides the built-in demo tokens in production.
    PORT            Port for the local dev server (default 8050).

Privacy note:
    The dashboard serves county-level aggregates only. No individual
    facility names, addresses, or identities are exposed through any
    endpoint. If facility-level views are ever added, centers must be
    de-identified as "Center 1", "Center 2", ... in display order.
"""

import os
import json
import secrets
import time
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import jinja2
import uvicorn

# ===========================================================================
# Configuration
# ===========================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
WEBAPP_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"

APP_VERSION = "2.0.0"

# Access tokens. In production set the ACCESS_TOKENS env var (JSON) instead
# of relying on these defaults, e.g.
#   ACCESS_TOKENS='{"my-secret-token": {"name": "Dr. X", "role": "Reviewer"}}'
_DEFAULT_TOKENS = {
    "acr-cardiac-2026": {"name": "Dr. Naeem", "role": "PI"},
    "shiloh-analyst-2026": {"name": "Shiloh Johnson", "role": "Analyst"},
}

def _load_tokens() -> dict:
    raw = os.environ.get("ACCESS_TOKENS")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed:
                return parsed
        except json.JSONDecodeError:
            pass
    return _DEFAULT_TOKENS

VALID_TOKENS = _load_tokens()

# ===========================================================================
# App setup
# ===========================================================================
app = FastAPI(
    title="ACR Cardiac Imaging - Geographic Disparities Dashboard",
    version=APP_VERSION,
    docs_url=None,   # no public API docs
    redoc_url=None,
    openapi_url=None,
)

# Compress everything above 1 KB (the counties GeoJSON is ~3 MB raw)
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR / "static")), name="static")

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(WEBAPP_DIR / "templates")),
    autoescape=True,
)
jinja_env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}


def render_template(name: str, **context) -> HTMLResponse:
    template = jinja_env.get_template(name)
    return HTMLResponse(content=template.render(**context))


# ---------------------------------------------------------------------------
# Security headers + cache policy on every response
# ---------------------------------------------------------------------------
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
    "https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://unpkg.com; "
    "img-src 'self' data: blob: https://*.cartocdn.com; "
    "connect-src 'self' https://*.cartocdn.com https://raw.githubusercontent.com; "
    "worker-src 'self' blob:; "
    "font-src 'self' data:; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = _CSP
    if request.url.path.startswith("/static/"):
        # Static data changes only on redeploy
        response.headers["Cache-Control"] = "public, max-age=86400"
    else:
        # Token-gated pages must never be cached by shared caches
        response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Auth (constant-time token comparison)
# ---------------------------------------------------------------------------
def verify_token(token: str = Query(None)):
    if token is not None:
        for known, user in VALID_TOKENS.items():
            if secrets.compare_digest(str(token), known):
                return user
    raise HTTPException(
        status_code=403,
        detail="Access denied. Please use the authorized link provided to you.",
    )


# ===========================================================================
# Data access (cached at first request)
# ===========================================================================
_data_cache: dict = {}

def get_analytic_data() -> pd.DataFrame:
    if "df" not in _data_cache:
        df = pd.read_csv(DATA_DIR / "county_analytic_dataset.csv",
                         dtype={"county_fips": str})
        _data_cache["df"] = df
    return _data_cache["df"]


def get_summary_stats() -> dict:
    if "stats" in _data_cache:
        return _data_cache["stats"]
    df = get_analytic_data()

    total_counties = len(df)
    total_cmr = int(df["cmr_facility_count"].sum())
    total_cct = int(df["cct_facility_count"].sum())
    counties_with_cmr = int((df["cmr_facility_count"] > 0).sum())
    counties_with_cct = int((df["cct_facility_count"] > 0).sum())
    neither = int(((df["cmr_facility_count"] == 0) &
                   (df["cct_facility_count"] == 0)).sum())

    metro = df[df["metro_indicator"] == 1]
    nonmetro = df[df["metro_indicator"] == 0]

    _data_cache["stats"] = {
        "total_counties": total_counties,
        "total_cmr_facilities": total_cmr,
        "total_cct_facilities": total_cct,
        "counties_with_cmr": counties_with_cmr,
        "counties_with_cct": counties_with_cct,
        "pct_no_cmr": round((1 - counties_with_cmr / total_counties) * 100, 1),
        "pct_no_cct": round((1 - counties_with_cct / total_counties) * 100, 1),
        "counties_neither": neither,
        "pct_neither": round(neither / total_counties * 100, 1),
        "metro_cmr": int(metro["cmr_facility_count"].sum()),
        "nonmetro_cmr": int(nonmetro["cmr_facility_count"].sum()),
        "metro_cct": int(metro["cct_facility_count"].sum()),
        "nonmetro_cct": int(nonmetro["cct_facility_count"].sum()),
        "metro_counties": len(metro),
        "nonmetro_counties": len(nonmetro),
    }
    return _data_cache["stats"]


def get_table1_data() -> list:
    path = BASE_DIR / "output" / "tables" / "table1_descriptive.csv"
    if path.exists():
        return pd.read_csv(path).to_dict(orient="records")
    return []


def get_regression_summary() -> str:
    path = BASE_DIR / "output" / "models" / "regression_results.txt"
    if path.exists():
        return path.read_text()
    return "Regression results not available."


# ===========================================================================
# Routes
# ===========================================================================
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, token: str = Query(None)):
    if token is None:
        return render_template("login.html")
    user = verify_token(token)
    return render_template(
        "dashboard.html",
        token=token,
        user=user,
        stats=get_summary_stats(),
        table1=get_table1_data(),
        regression=get_regression_summary(),
        version=APP_VERSION,
    )


@app.get("/healthz")
async def healthz():
    """Unauthenticated liveness probe for the hosting platform."""
    return {"status": "ok", "version": APP_VERSION}


@app.get("/api/stats")
async def api_stats(user=Depends(verify_token)):
    return get_summary_stats()


@app.get("/api/table1")
async def api_table1(user=Depends(verify_token)):
    return get_table1_data()


@app.get("/api/svi-distribution")
async def api_svi_distribution(user=Depends(verify_token)):
    df = get_analytic_data()
    d = df[df["rate_excluded"] == 0].copy()
    d["svi_decile"] = pd.qcut(d["svi_percentile"], 10,
                              labels=False, duplicates="drop") + 1
    grouped = d.groupby("svi_decile").agg(
        mean_cmr_rate=("cmr_rate_per_100k", "mean"),
        mean_cct_rate=("cct_rate_per_100k", "mean"),
        n_counties=("county_fips", "count"),
    ).reset_index()
    return grouped.round(4).to_dict(orient="records")


# ---------------------------------------------------------------------------
# Reviewer feedback (lightweight; appended to a local JSONL file)
# ---------------------------------------------------------------------------
class Feedback(BaseModel):
    message: str = Field(min_length=3, max_length=4000)
    page: str = Field(default="", max_length=200)

_FEEDBACK_PATH = WEBAPP_DIR / "feedback.jsonl"

@app.post("/api/feedback")
async def api_feedback(item: Feedback, user=Depends(verify_token)):
    record = {
        "ts": int(time.time()),
        "from": user.get("name", "unknown"),
        "role": user.get("role", ""),
        "page": item.page,
        "message": item.message.strip(),
    }
    with open(_FEEDBACK_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"ok": True}


# ===========================================================================
# Local dev server
# ===========================================================================
if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  ACR Cardiac Imaging - Geographic Disparities Dashboard")
    print("=" * 62)
    print("\n  Access URLs (share only with authorized collaborators):")
    for tok, info in VALID_TOKENS.items():
        print(f"    {info['name']:<18} http://localhost:8050/?token={tok}")
    print("\n  Health check:  http://localhost:8050/healthz")
    print("  Press Ctrl+C to stop.\n")
    port = int(os.environ.get("PORT", 8050))
    uvicorn.run(app, host="0.0.0.0", port=port)
