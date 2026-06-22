"""Dataset Analyst — Streamlit MVP.

Pick a saved recipe (button) or set filters manually, see chapters as dots on a
US/Canada/Africa map, and read/download the chapter-name list for the active cut.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

from core import engine, geo
from core.ingest import load_snapshot, snapshot_date_from_name

DATA_DIR = Path(__file__).parent / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
CLEAN_CSV = DATA_DIR / "chapters_clean.csv"  # committed, PII-free, pre-geocoded (used on cloud)
RECIPE_DIR = Path(__file__).parent / "recipes"

# Filter dimensions exposed as UI widgets (a subset of engine.FILTER_DIMENSIONS).
UI_DIMENSIONS = {"zone": "Zone", "region": "Region", "chapter_type": "Type", "country": "Country"}

st.set_page_config(page_title="Chapter Dashboard", layout="wide")


def _latest_snapshot_path() -> Path | None:
    """Newest snapshot by parsed date, falling back to filename order."""
    files = list(SNAPSHOT_DIR.glob("*.xlsx"))
    if not files:
        return None
    return max(files, key=lambda p: (snapshot_date_from_name(p) or p.name, p.name))


@st.cache_data(show_spinner=True)
def _load(path_str: str, _mtime: float) -> pd.DataFrame:
    # _mtime is part of the cache key so replacing a file invalidates the cache.
    df, _ = load_snapshot(path_str)
    return geo.geocode(df)


@st.cache_data(show_spinner=True)
def _load_clean(_mtime: float) -> pd.DataFrame:
    # Committed, PII-free, already-geocoded data — used on Streamlit Cloud.
    return pd.read_csv(CLEAN_CSV)


def load_data() -> tuple[pd.DataFrame, str]:
    """Prefer the committed clean CSV (cloud); fall back to local xlsx (dev)."""
    if CLEAN_CSV.exists():
        df = _load_clean(CLEAN_CSV.stat().st_mtime)
        date = str(df["snapshot_date"].iloc[0])[:10] if "snapshot_date" in df else "—"
        return df, f"clean export · {date}"
    path = _latest_snapshot_path()
    if path is None:
        return pd.DataFrame(), ""
    return _load(str(path), path.stat().st_mtime), path.name


def _apply_recipe_to_widgets(recipe: engine.Recipe) -> None:
    """Populate widget state from a recipe; warn on dims the UI can't show."""
    for dim in UI_DIMENSIONS:
        st.session_state[dim] = recipe.filters.get(dim, [])
    ignored = set(recipe.filters) - set(UI_DIMENSIONS)
    if ignored:
        st.session_state["_recipe_warning"] = (
            f"Recipe {recipe.name!r} also filters on {sorted(ignored)}, "
            "which has no UI control yet — that part was not applied."
        )
    else:
        st.session_state.pop("_recipe_warning", None)


def main() -> None:
    st.title("NSBE Chapter Dashboard")

    df, label = load_data()
    if df.empty:
        st.warning(
            f"No data found. Add `{CLEAN_CSV.name}` to `data/`, or drop an export "
            f".xlsx into `{SNAPSHOT_DIR}`."
        )
        st.stop()

    st.caption(f"Snapshot: **{label}** · {len(df)} active chapters")

    # --- Saved recipes as buttons (write directly to widget state) --------
    with st.sidebar:
        st.header("Saved recipes")
        for r in engine.load_recipes(RECIPE_DIR):
            if st.button(r.name, use_container_width=True):
                _apply_recipe_to_widgets(r)
                st.rerun()
        st.divider()
        if st.button("Clear filters", use_container_width=True):
            for dim in UI_DIMENSIONS:
                st.session_state[dim] = []
            st.session_state.pop("_recipe_warning", None)
            st.rerun()

    if msg := st.session_state.get("_recipe_warning"):
        st.warning(msg)

    # --- Manual filters (same engine code path as recipes) ----------------
    cols = st.columns(len(UI_DIMENSIONS))
    filters: dict[str, list[str]] = {}
    for col, (dim, label) in zip(cols, UI_DIMENSIONS.items()):
        with col:
            opts = sorted(df[dim].dropna().astype(str).unique())
            filters[dim] = st.multiselect(label, opts, key=dim)

    result = engine.apply_filters(df, filters)
    st.metric("Chapters matching filter", len(result))

    # --- Map ---------------------------------------------------------------
    mapped = result.dropna(subset=["lat", "lon"])
    if len(mapped):
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=mapped,
            get_position="[lon, lat]",
            get_radius=22000,
            get_fill_color=[200, 30, 80, 160],
            pickable=True,
        )
        view = pdk.ViewState(latitude=20.0, longitude=-40.0, zoom=1.3)
        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=view,
                tooltip={"text": "{chapter_name}\n{city}, {state} {country}"},
            )
        )
        if len(mapped) < len(result):
            st.caption(f"{len(result) - len(mapped)} chapter(s) had no mappable location.")
    else:
        st.info("No chapters with mappable locations for this filter.")

    # --- Text list + download ---------------------------------------------
    names = engine.chapter_name_list(result)
    st.subheader(f"Chapters ({len(names)})")
    st.dataframe(pd.DataFrame({"Chapter": names}), use_container_width=True, hide_index=True)
    st.download_button(
        "Download list (.txt)",
        data="\n".join(names),
        file_name="chapters.txt",
        mime="text/plain",
    )


if __name__ == "__main__":
    main()
# end of app.py
