"""Local geocoding: map (country, state) -> centroid lat/lon, no API.

The export has no coordinates, so chapters are plotted at the centroid of
their state (US/Canada) or country (everywhere else), with a small random
jitter so co-located chapters render as distinct dots.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

_CENTROIDS_PATH = Path(__file__).resolve().parent.parent / "data" / "centroids.csv"
_JITTER_DEG = 0.35  # ~25-40 km; enough to separate dots, small enough to stay in-region


def _load_centroids() -> tuple[dict, dict]:
    """Return (state_lookup, country_lookup)."""
    c = pd.read_csv(_CENTROIDS_PATH).fillna({"state": ""})
    state_lu, country_lu = {}, {}
    for _, r in c.iterrows():
        if r["state"]:
            state_lu[(r["country"], r["state"])] = (r["lat"], r["lon"])
        else:
            country_lu[r["country"]] = (r["lat"], r["lon"])
    return state_lu, country_lu


def geocode(df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """Add ``lat``/``lon`` columns. Rows with no centroid get NaN (flagged, not dropped)."""
    state_lu, country_lu = _load_centroids()
    rng = np.random.default_rng(seed)

    lats, lons = [], []
    for _, row in df.iterrows():
        country = row.get("country") if pd.notna(row.get("country")) else None
        state = row.get("state") if pd.notna(row.get("state")) else None
        coord = state_lu.get((country, state)) or (country_lu.get(country) if country else None)
        if coord is None:
            lats.append(np.nan); lons.append(np.nan)
        else:
            lats.append(coord[0] + rng.uniform(-_JITTER_DEG, _JITTER_DEG))
            lons.append(coord[1] + rng.uniform(-_JITTER_DEG, _JITTER_DEG))

    out = df.copy()
    out["lat"] = lats
    out["lon"] = lons
    return out


def coverage(df: pd.DataFrame) -> float:
    """Fraction of rows that received coordinates."""
    if len(df) == 0:
        return 1.0
    return float(df["lat"].notna().mean())
