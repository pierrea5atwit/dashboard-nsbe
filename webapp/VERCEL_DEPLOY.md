# Vercel Deployment — React + FastAPI

The `webapp/` folder is a self-contained, deploy-ready Vercel project: a Vite +
React frontend and a FastAPI backend that runs as a **Vercel Python serverless
function**, both in one repo and one deploy. It reuses the same engine as the
Streamlit app (copied into `api/lib/` so the function is self-contained).

## Topology

```
Browser ──▶ Vercel (static React from web/dist)
                │  fetch /api/*
                ▼
         Vercel Python function  (api/index.py = FastAPI)
                │  reads bundled snapshot + recipes (read-only)
                ▼
         api/lib/{ingest,engine,geo}  ── same logic as the Streamlit core
```

- **Frontend:** Vite/React, `react-leaflet` dots over OpenStreetMap tiles, filter
  checkboxes (Zone/Region/Type/Country), recipe buttons, chapter list + `.txt`.
- **Backend:** `GET /api/meta` (filter options + recipes + snapshot info),
  `POST /api/query` (filtered points + names). Snapshot is loaded + geocoded once
  per cold start and cached in memory.
- **Data:** the export `.xlsx`, `centroids.csv`, and recipes are bundled in
  `api/data` / `api/recipes` (read-only — fine for serverless).

## Local development

Two terminals:

```bash
# 1) backend on :8000
cd webapp && pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000

# 2) frontend on :5173 (proxies /api -> :8000, see vite.config.js)
cd webapp/web && npm install && npm run dev
```

## Deploy (GitHub → Vercel auto-deploy)

This mirrors the pipeline in the web-design clip ([[building-beautiful-websites-claude-code]]):

1. **Push to GitHub.** Commit the repo (the project root, or just `webapp/`).
2. **Import in Vercel.** vercel.com → Add New → Project → import the GitHub repo.
   - **Root Directory:** set to `webapp` (so `vercel.json` is at the project root).
   - Framework preset: **Other** (vercel.json drives the build).
3. **Deploy.** Vercel runs `web/ → npm install && npm run build`, serves
   `web/dist`, and deploys `api/index.py` as a Python function. `/api/*` is routed
   to it via the rewrite in `vercel.json`.
4. **Every push auto-deploys**; PRs get preview URLs.
5. **Custom domain (optional):** Project → Settings → Domains → add/buy; Vercel
   walks through DNS.

## Updating the data

Drop a new dated export into `api/data/` (e.g. `Chapters_Active_As_Of_07_15_2026.xlsx`)
and push. The function auto-selects the newest by parsed date. No code change.

## Notes & limits

- **Cold starts:** first request after idle pays ~1–2 s to load pandas + geocode
  562 rows. Fine at this scale; if it ever bothers peers, move the API to an
  always-on host (see `APP_PLANS.md`, Plan B "separate API host").
- **Secrets:** none required today. If a backend datasource is added later, use
  Vercel Environment Variables — never commit keys (the clip flags this too).
- **Function size:** pandas/numpy are large; bundled deps + one xlsx stay well
  within Vercel's limits.
- **Engine duplication:** `api/lib/` is a copy of the project `core/`. If you
  change one, sync the other (or later promote `core/` to a shared package).
