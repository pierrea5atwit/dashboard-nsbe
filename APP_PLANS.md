# MVP App Plans — Streamlit vs React

Two routes to the same MVP: filter chapters by Zone/Region/Type, compose filters, plot dots on a US/Canada/West-Africa map, list chapter names below with a `.txt` download. Both reuse the same Python core (`ingest.py`, `engine.py`, `geo.py`) — only the UI differs.

**Shared, non-negotiable:** geocoding is a bundled `centroids.csv` (state/province + country → lat/lon, with jitter). Fully local, no API. Same recipe schema drives both.

---

## Plan A — Streamlit + pydeck (recommended for MVP)

**Stack:** Streamlit · pydeck `ScatterplotLayer` · pandas core (direct import, no API).

- **Recipe buttons:** `st.sidebar` buttons, one per saved recipe; click sets filter state.
- **Manual filters:** `st.multiselect` for Zone / Region / Type, composed AND-across / OR-within — same `engine.apply(recipe)` call as the buttons.
- **Map:** `st.pydeck_chart` with a `ScatterplotLayer` over `[lon, lat]`; auto-fit view spans US + Canada + West Africa.
- **Text list + download:** `st.dataframe` of chapter names + `st.download_button` → `.txt`.
- **Hosting path:** runs local now (`streamlit run app.py`); later Streamlit Community Cloud or a container — unchanged code.

**Tradeoffs**
- ✅ Fastest to working MVP; one language; engine reused with zero glue.
- ✅ Sustainable for a solo/internal tool — minimal surface to maintain.
- ⚠️ Map interactivity and layout polish are limited vs a real frontend.
- ⚠️ Single-session reactivity model; many concurrent peers is not its strength.

---

## Plan B — React + FastAPI + react-leaflet

**Stack:** Vite + React + TypeScript · react-leaflet (OpenStreetMap tiles, free) · FastAPI wrapping the same pandas core.

- **Backend:** FastAPI exposes `GET /recipes`, `POST /query` (recipe in → `{points, names}` out), `GET /export.txt`. Thin layer over `engine.apply`.
- **Recipe buttons:** components rendered from `/recipes`; click POSTs the recipe.
- **Manual filters:** controlled multi-selects → request body.
- **Map:** `react-leaflet` `CircleMarker` dots; `react-leaflet-markercluster` for dense zones.
- **Text list + download:** list component below the map; download hits `/export.txt`.
- **Hosting path:** static frontend (Vercel/Netlify) + API container; clean multi-user peer access.

**Tradeoffs**
- ✅ Real UI control, clustering, smooth peer-facing experience and scaling.
- ✅ Clean separation — frontend and engine evolve independently.
- ⚠️ Two codebases + an API contract to maintain; slower to first MVP.
- ⚠️ More infra/ops than a personal tool likely needs *yet*.

---

## Recommendation

Build **Plan A now**. It hits every MVP item with the least code, reuses the engine directly, and runs locally today. Because both plans sit on the *same* Python core behind a stable `engine.apply(recipe)` boundary, moving to Plan B later means adding a FastAPI layer over code you already have — not a rewrite. Defer React until peer demand or UI needs actually justify the second codebase.
