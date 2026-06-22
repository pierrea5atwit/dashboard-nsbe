"""FastAPI backend for the NSBE Chapter Dashboard, deployed as a Vercel
Python serverless function. Reuses the same engine as the Streamlit app.

Endpoints (all under /api via vercel.json rewrite):
  GET  /api/health
  GET  /api/meta     -> snapshot info, filter options, saved recipes
  POST /api/query    -> filtered points + chapter-name list
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from datetime import date  # noqa: E402

from lib import engine, geo  # noqa: E402
from lib.ingest import load_snapshot, snapshot_date_from_name  # noqa: E402

DATA = BASE / "data"
RECIPES = BASE / "recipes"


def _pick_snapshot() -> Path:
    """Newest bundled export by parsed date; prefer dated filenames."""
    xlsx = list(DATA.glob("*.xlsx"))
    dated = [p for p in xlsx if snapshot_date_from_name(p)]
    pool = dated or xlsx
    return max(pool, key=lambda p: (snapshot_date_from_name(p) or date.min, p.name))


SNAPSHOT = _pick_snapshot()


def _clean(v):
    """NA/NaN -> None, else str (pandas 'string'/object cells may hold pd.NA)."""
    import pandas as pd

    return None if pd.isna(v) else str(v)

app = FastAPI(title="NSBE Chapter Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # same-origin in prod; permissive eases local dev
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load + geocode once per cold start, then serve from memory.
_DF = None
_SNAP = None


def _data():
    global _DF, _SNAP
    if _DF is None:
        df, snap = load_snapshot(str(SNAPSHOT))
        _DF = geo.geocode(df)
        _SNAP = snap
    return _DF


class QueryBody(BaseModel):
    filters: dict[str, list[str]] = {}


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    df = _data()
    options = {
        dim: sorted(df[dim].dropna().astype(str).unique().tolist())
        for dim in ["zone", "region", "chapter_type", "country"]
    }
    recipes = [
        {"name": r.name, "filters": r.filters} for r in engine.load_recipes(RECIPES)
    ]
    return {
        "snapshot": SNAPSHOT.name,
        "snapshot_date": str(_SNAP) if _SNAP else None,
        "total": int(len(df)),
        "options": options,
        "recipes": recipes,
    }


@app.post("/api/query")
def query(body: QueryBody):
    df = _data()
    res = engine.apply_filters(df, body.filters)
    mapped = res.dropna(subset=["lat", "lon"])
    points = [
        {
            "lat": float(r.lat),
            "lon": float(r.lon),
            "name": _clean(r.chapter_name),
            "city": _clean(r.city),
            "state": _clean(r.state),
            "country": _clean(r.country),
        }
        for r in mapped.itertuples()
    ]
    return {
        "count": int(len(res)),
        "mapped": int(len(mapped)),
        "points": points,
        "names": engine.chapter_name_list(res),
    }
