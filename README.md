# NSBE Chapter Dashboard

Local-first dashboard for NSBE chapter exports. View chapters by Zone / Region / Type,
compose filters, see them as dots on a US / Canada / Africa map, and export the
chapter-name list for any filter.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501.

## Adding a snapshot

Drop the export `.xlsx` into `data/snapshots/`. The newest file (by name) is used.
The snapshot date is read from the filename (e.g. `..._06_19_2026.xlsx`).

## Saved recipes

Each file in `recipes/*.yaml` becomes a one-click button in the sidebar. Add a recipe:

```yaml
name: "Region 1 — Collegiate"
filters:
  region: [Region 1]
  chapter_type: [Collegiate Chapter]
```

Filter dimensions: `zone`, `region`, `chapter_type`, `state`, `country`, `account_type`.
Filtering is AND across dimensions, OR within a dimension's list.

## Layout

```
app.py                 Streamlit UI (recipe buttons, filters, map, list)
core/ingest.py         xlsx -> clean canonical DataFrame (header auto-detect)
core/engine.py         Recipe model + the one audited filter transform
core/geo.py            local centroid geocoding (no API)
data/centroids.csv     state/province + country -> lat/lon
data/snapshots/        drop exports here
recipes/               saved filter recipes (sidebar buttons)
```

See `SYSTEM_DESIGN.md` for architecture and `APP_PLANS.md` for the Streamlit-vs-React rationale.
