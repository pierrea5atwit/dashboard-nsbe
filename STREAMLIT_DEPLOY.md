# Deploy to Streamlit Community Cloud (free public URL)

This gives non-technical peers a link they just click — no install, no login to view.

## What gets deployed

- `app.py` (the dashboard) + `core/` + `recipes/`
- `data/chapters_clean.csv` and `data/chapters_inactive_clean.csv` — cleaned data
  (chapter names, zone/region/type, city/state/country, map coordinates, **and chapter
  email/phone**). Street addresses are NOT included.
- ⚠️ **Contact info is included by choice.** These files hold chapter emails/phones and are
  committed to the repo, so on a public app/repo anyone can see them. If you ever want to
  hide contacts, drop `email`/`phone` from `KEEP` in `build_clean_data.py` and rebuild, or
  restrict the app via Streamlit Cloud's viewer allow-list.
- The raw exports (`data/snapshots/*.xlsx`) stay **git-ignored** — street addresses never
  reach the repo.

## One-time setup

1. **Push the repo to GitHub** (origin is already set to `dashboard-nsbe`):
   ```
   cd "C:\Users\andpi\Claude\Projects\Dataset Analyst - Agent"
   git add -A
   git commit -m "Streamlit Cloud: PII-free data + cloud loader"
   git push
   ```
2. Go to **https://share.streamlit.io** and sign in with GitHub.
3. **Create app → From existing repo:**
   - Repository: `pierrea5atwit/dashboard-nsbe`
   - Branch: whichever you push (e.g. `main` or `master`)
   - **Main file path: `app.py`**
4. (Optional) **Advanced settings → Python version: 3.12**.
5. **Deploy.** In ~1–2 minutes you get a public URL like
   `https://dashboard-nsbe.streamlit.app` — share it with anyone.

Streamlit Cloud installs from the root `requirements.txt` automatically (streamlit,
pydeck, pandas, etc.). No Vercel-style build config needed.

## Updating the data later

When you get a new export, drop the `.xlsx` into `data/snapshots/`, then:

```
python build_clean_data.py
git add data/*.csv
git commit -m "Update chapter data"
git push
```

The live app redeploys automatically on push.

**Active vs inactive:** the build script classifies exports by filename — a file with
**"Inactive"** in its name (e.g. `Chapters_Inactive_As_Of_06_19_2026.xlsx`) becomes the
grey layer (`data/chapters_inactive_clean.csv`); anything else is the green active layer.
Add an inactive export the same way and the grey dots + toggle appear automatically.

## Notes

- **Repo visibility:** public is fine — only the cleaned CSV is committed. (Private also
  works; Streamlit Cloud supports private repos.)
- **Access control:** by default anyone with the URL can view. If you ever need to
  restrict it, Streamlit Cloud has viewer allow-lists in the app settings.
- **Local dev still works:** on your machine the app reads the raw `.xlsx` directly if the
  clean CSV isn't present, so nothing changes about `streamlit run app.py` locally.
