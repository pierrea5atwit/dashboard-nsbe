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
CLEAN_CSV = DATA_DIR / "chapters_clean.csv"            # active chapters (green)
INACTIVE_CSV = DATA_DIR / "chapters_inactive_clean.csv"  # inactive chapters (grey), optional
RECIPE_DIR = Path(__file__).parent / "recipes"

# Filter dimensions exposed as UI widgets (a subset of engine.FILTER_DIMENSIONS).
UI_DIMENSIONS = {"zone": "Zone", "region": "Region", "chapter_type": "Type", "country": "Country"}

ACTIVE_COLOR = [34, 197, 94, 200]    # green
INACTIVE_COLOR = [148, 163, 184, 150]  # grey

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


@st.cache_data(show_spinner=False)
def _load_inactive(_mtime: float) -> pd.DataFrame:
    return pd.read_csv(INACTIVE_CSV)


def load_inactive() -> pd.DataFrame:
    """Inactive chapters (grey), if the committed file is present; else empty."""
    if INACTIVE_CSV.exists():
        return _load_inactive(INACTIVE_CSV.stat().st_mtime)
    return pd.DataFrame()


def _map_view(active: pd.DataFrame, inactive: pd.DataFrame) -> pdk.ViewState:
    """Frame the map snugly to the chapter bounding box (US / Canada / Africa)."""
    import math

    pts = active[["lon", "lat"]]
    if not inactive.empty:
        pts = pd.concat([pts, inactive[["lon", "lat"]]])
    pts = pts.dropna()
    if pts.empty:
        return pdk.ViewState(latitude=25.0, longitude=-40.0, zoom=1.3)
    lon_min, lon_max = pts["lon"].min(), pts["lon"].max()
    lat_min, lat_max = pts["lat"].min(), pts["lat"].max()
    # Center on the bbox midpoint so North America and Africa sit symmetrically.
    center_lon, center_lat = (lon_min + lon_max) / 2, (lat_min + lat_max) / 2
    span = max(lon_max - lon_min, (lat_max - lat_min) * 1.8, 1.0) * 1.1  # +10% margin
    zoom = min(max(math.log2(360 / span), 1.0), 5.0)
    return pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=zoom)


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

    inactive_df = load_inactive()

    # --- Manual filters (same engine code path as recipes) ----------------
    # Options span both datasets so a value unique to inactive chapters is selectable.
    opt_source = pd.concat([df, inactive_df]) if not inactive_df.empty else df
    cols = st.columns(len(UI_DIMENSIONS))
    filters: dict[str, list[str]] = {}
    for col, (dim, lbl) in zip(cols, UI_DIMENSIONS.items()):
        with col:
            opts = sorted(opt_source[dim].dropna().astype(str).unique())
            filters[dim] = st.multiselect(lbl, opts, key=dim)

    result = engine.apply_filters(df, filters)
    inactive_result = (
        engine.apply_filters(inactive_df, filters) if not inactive_df.empty else inactive_df
    )

    # Toggle + counts
    show_inactive = False
    if inactive_df.empty:
        st.metric("Active chapters matching filter", len(result))
    else:
        show_inactive = st.checkbox("Show inactive chapters (grey)", value=True)
        c1, c2 = st.columns(2)
        c1.metric("Active (green)", len(result))
        c2.metric("Inactive (grey)", len(inactive_result))

    # --- Map (active green + optional inactive grey) ----------------------
    def _scatter(data, color):
        data = data.copy()
        for c in ["city", "state", "country", "email", "phone"]:  # blank, not "nan", in tooltip
            if c in data:
                data[c] = data[c].fillna("")
        return pdk.Layer(
            "ScatterplotLayer", data=data, get_position="[lon, lat]",
            get_fill_color=color, get_radius=4000,
            radius_min_pixels=2, radius_max_pixels=6,          # small dots so clusters are legible
            stroked=True, get_line_color=[20, 24, 33, 180],    # thin dark outline separates overlaps
            line_width_min_pixels=0.5, opacity=0.85, pickable=True,
        )

    a_mapped = result.dropna(subset=["lat", "lon"])
    i_mapped = (
        inactive_result.dropna(subset=["lat", "lon"]) if not inactive_result.empty else inactive_result
    )

    layers = []
    if show_inactive and len(i_mapped):          # grey first → sits beneath green
        layers.append(_scatter(i_mapped, INACTIVE_COLOR))
    if len(a_mapped):
        layers.append(_scatter(a_mapped, ACTIVE_COLOR))

    if layers:
        st.pydeck_chart(
            pdk.Deck(
                layers=layers,
                initial_view_state=_map_view(df, inactive_df),
                tooltip={"text": "{chapter_name}\n{city}, {state} {country}\n{email}  {phone}"},
                map_style=None,
            )
        )
        legend = "🟢 active" + ("  ·  ⚪ inactive" if show_inactive and len(i_mapped) else "")
        st.caption(legend)
    else:
        st.info("No chapters with mappable locations for this filter.")

    # --- Text lists + downloads (with contact info) -----------------------
    def _chapter_table(container, title, frame, fname, key):
        cols = [c for c in ["chapter_name", "email", "phone"] if c in frame.columns]
        tbl = (
            frame[cols]
            .drop_duplicates(subset="chapter_name")
            .sort_values("chapter_name")
            .rename(columns={"chapter_name": "Chapter", "email": "Email", "phone": "Phone"})
        )
        container.subheader(f"{title} ({len(tbl)})")
        container.dataframe(tbl, use_container_width=True, hide_index=True)
        names = engine.chapter_name_list(frame)
        container.download_button(
            "Download names (.txt)", data="\n".join(names),
            file_name=fname, mime="text/plain", key=key,
        )

    if inactive_df.empty:
        _chapter_table(st, "Chapters", result, "chapters.txt", "dl_active")
    else:
        lc, rc = st.columns(2)
        _chapter_table(lc, "🟢 Active chapters", result, "active_chapters.txt", "dl_active")
        _chapter_table(rc, "⚪ Inactive chapters", inactive_result, "inactive_chapters.txt", "dl_inactive")


if __name__ == "__main__":
    main()
# end of app.py
