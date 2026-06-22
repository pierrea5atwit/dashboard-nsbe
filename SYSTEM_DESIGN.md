# Dataset Analyst Agent — System Design

**Scope:** Local-first agent that ingests periodic Excel snapshots of registrant data, computes trends over time, serves a dashboard, and answers natural-language questions by routing to vetted query templates.

**Locked decisions**
- Deployment: localhost now, structured so it can be hosted for peers later.
- Core need: an **engine that rewrites the recurring pandas for you** (the `memdata.py` pattern), parameterized by a recipe — *not* a full NL-inference system.
- Data cadence: **periodic snapshots** — each uploaded sheet is a full export, compared snapshot-to-snapshot.

**Grounded in the real export** (`Chapters_Active_As_Of_06_19_2026.xlsx`)
- 564 active chapter rows under an **11-row metadata preamble**; the header row is the one containing `Community Group: ID`.
- **Stable key:** `Community Group: ID` (e.g. `a0M6g00000BqR0t`) — enables new/churned chapter detection across snapshots.
- **Segment dimensions:** `Linked Chapter Account: Zone`, `... Region`, `... Type` (NSBE Jr. / Collegiate / Professional), `... Billing State/Province`, `... Billing Country`.
- **Snapshot date** is encoded in the filename (`..._06_19_2026`).
- Junk to drop: `Unnamed: *`, `Community Group: Created Date`, `Linked Chapter Account: Phone`.

---

## 1. Architecture at a glance

```
                        ┌──────────────────────────────────────────────┐
   upload .xlsx  ──────▶│ 1. INGEST                                      │
                        │   openpyxl/pandas → schema-validate (Pydantic) │
                        │   normalize cols → assign snapshot_date        │
                        │   file_hash dedup (idempotent)                 │
                        └───────────────────┬────────────────────────────┘
                                            ▼
                        ┌──────────────────────────────────────────────┐
                        │ 2. SNAPSHOT STORE (the "context over time")    │
                        │   Parquet partitioned by snapshot_date         │
                        │   DuckDB view over all partitions              │
                        │   manifest table: id, date, rows, hash, colmap │
                        └───────┬───────────────────────┬────────────────┘
                                ▼                        ▼
        ┌───────────────────────────────┐   ┌──────────────────────────────┐
        │ 3. INSIGHT ENGINE             │   │ 4. NL QUERY ROUTER            │
        │  current vs prev snapshot     │   │  question → LLM structured     │
        │  Δ totals, per-zone, per-demo │   │  output → {template_id, params}│
        │  new vs churned (ID set diff) │   │  execute vetted template fn    │
        │  full time series             │   │  → DataFrame                   │
        └───────────────┬───────────────┘   └───────────────┬───────────────┘
                        ▼                                    ▼
                        ┌──────────────────────────────────────────────┐
                        │ 5. PRESENTATION — Streamlit                    │
                        │   localhost:8501 now · containerize/host later │
                        └──────────────────────────────────────────────┘
```

---

## 2. Tech stack (explicit — no surprise imports)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | pandas ecosystem, type hints |
| Excel read | `pandas` + `openpyxl` | standard, handles .xlsx |
| Validation | `pydantic` v2 | enforce the data contract at the boundary |
| Snapshot store | **Parquet files + DuckDB** | columnar, append-only, partition by date; DuckDB queries across all snapshots with zero server |
| Insight compute | `pandas` | deltas, set ops, time series |
| NL routing | **Claude API** with tool/structured-output schema | "LLM picks a template" = function-calling over the template registry |
| Dashboard | **Streamlit** | fastest local→hosted path; one `streamlit run` locally, container/Streamlit Cloud later |
| Charts | `plotly` (via Streamlit) | interactive, exports cleanly |
| Config | `pydantic-settings` + `.env` | column maps, API key, paths |

**Why DuckDB over a raw SQLite or a Postgres server:** snapshots are read-heavy, append-only, and analytical (group-by/aggregate). DuckDB reads Parquet partitions directly with no running server — ideal for localhost — and the exact same code works when the Parquet directory later sits on a hosted volume.

---

## 3. Data contract (the foundation everything depends on)

Normalize every incoming sheet to a **canonical schema** before storage. This is the single most important design decision: downstream insights and templates depend on stable column names, so messy source headers are mapped once at ingest.

```python
class ChapterRecord(BaseModel):
    chapter_id: str         # STABLE KEY ← "Community Group: ID"
    chapter_name: str       # "Community Group: Community Group Name"
    zone: str | None        # "Linked Chapter Account: Zone"
    region: str | None      # "Linked Chapter Account: Region"
    chapter_type: str | None# "Linked Chapter Account: Type" (NSBE Jr./Collegiate/Professional)
    state: str | None        # "... Billing State/Province"
    country: str | None      # "... Billing Country"
    snapshot_date: date     # injected from filename, not source
```

Column mapping lives in config (`column_map.yaml`). When a new sheet arrives with unmapped columns, ingest **fails loudly** rather than silently dropping data.

**Confirmed:** `Community Group: ID` is stable across exports, so new-vs-churned chapter detection works (set diff on `chapter_id`). "Registrants up/down" = active-chapter count delta per snapshot.

---

## 4. Component flow

### 4.1 Ingest
1. Read sheet → DataFrame.
2. `file_hash = sha256(bytes)`; if hash already in manifest → skip (idempotent re-upload).
3. Apply column map → validate each row against `RegistrantRecord` → collect rejects into a report.
4. Resolve `snapshot_date` (priority: explicit column → filename pattern → upload date, surfaced to user for confirmation).
5. Write `snapshots/snapshot_date=YYYY-MM-DD/data.parquet`; append row to manifest.

### 4.2 Insight engine
On each new snapshot, compute against the immediately prior snapshot and the full history:
- **Headline delta:** total registrants, absolute and %.
- **Segment deltas:** group-by `zone` and `demographic`, change vs prior.
- **Membership churn:** `set(curr.member_id) - set(prev.member_id)` = new; reverse = churned (requires stable ID).
- **Time series:** total and per-segment across all snapshots for trend lines.

Outputs cache to `insights/<snapshot_date>.json` so the dashboard renders instantly without recompute.

### 4.3 Recipe library (Option B — deterministic, no LLM)
Each recurring cut is a **saved recipe** = a typed YAML spec. Recipes are surfaced on the dashboard as **clickable buttons**; clicking one applies its filters and renders the result. No model in the loop — fully deterministic, offline, zero per-call cost. The library expands one recipe at a time as new cuts are needed.

**Recipe spec** (what each button encodes):
```yaml
name: "Northeast Collegiate"
snapshot: latest                  # or a specific date
filters:                          # AND across dimensions, OR within a list
  region: [Region 1]
  type:   [Collegiate Chapter]
  zone:   [New Jersey]
outputs: [map, table, chapter_name_list.txt]
```

**Flow:** button click (or ad-hoc filter widgets) → load recipe → validate against the recipe schema (Pydantic) → the **one audited transform function** applies it to the active snapshot → map + table + text list. The same function powers both saved buttons and the manual filter controls.

**Hardened cleaning core** (never changes, fixes the script's brittleness):
- detect the header row by locating `Community Group: ID` (no hardcoded `skiprows`);
- drop `Unnamed:*` / known junk columns;
- normalize to the canonical schema; read `.xlsx` directly (no csv round-trip).

**Why Option B fits:** your cuts recur and you want to expand them incrementally. A validated recipe + one transform function gives reliability, zero cost, and no eval/tuning burden — and keeps the door open to add an LLM fallback later only if open-ended querying is ever needed.

### 4.4 MVP scope (current target)
1. **View chapters by Zone, Region, Type** — segment filters over `chapter_name`.
2. **Compose multiple filters** — e.g. `Region 1` + `NSBE Jr.` + `New Jersey` zone (AND across dims).
3. **Map** — plot chapters as dots across US / Canada / West Africa.
   - *Geocoding:* the export has no lat/long. MVP uses a bundled **state/province + country → centroid** lookup table (static CSV, fully local, no API), with small per-chapter jitter so co-located dots are visible. City-level centroids can be added later without changing the pipeline.
4. **Text list below the map** — explicit list of `Community Group: Community Group Name` for the active filter, with a `.txt` download (replaces the script's `export_to_txt`).

---

## 5. Repo layout

```
dataset-analyst/
├── app.py                  # Streamlit entrypoint
├── config/
│   ├── settings.py
│   └── column_map.yaml
├── core/
│   ├── ingest.py           # header detection, normalize, dedup (hardened clean core)
│   ├── store.py            # Parquet + DuckDB + manifest
│   ├── insights.py
│   ├── engine.py           # one audited transform: recipe → filtered DataFrame
│   └── geo.py              # state/country → centroid lookup (+ jitter)
├── recipes/                # saved YAML recipes (dashboard buttons)
├── data/
│   └── centroids.csv       # static geocode table (local, no API)
├── data/
│   ├── snapshots/          # parquet partitions (gitignored)
│   └── insights/           # cached json
├── tests/
│   └── fixtures/           # tiny synthetic snapshots for eval
└── requirements.txt
```

---

## 6. Measurement plan

Define a baseline before any tuning; compare against it.

| Capability | Metric | Target |
|---|---|---|
| Ingest robustness | % rows validated without manual fix, across N real sheets | ≥ 0.95 |
| Snapshot integrity | duplicate-upload double-count incidents | 0 (hash dedup) |
| Insight correctness | engine deltas vs hand