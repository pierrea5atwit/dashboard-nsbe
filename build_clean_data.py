"""Regenerate the committed, PII-free data files the cloud app reads.

Run this after dropping new export(s) into data/snapshots/, then commit + push:

    python build_clean_data.py
    git add data/*.csv && git commit -m "Update data" && git push

Exports are classified by filename:
  - "...Inactive..."  -> data/chapters_inactive_clean.csv  (grey on the map)
  - anything else      -> data/chapters_clean.csv           (green on the map)

Only non-sensitive columns are written (no emails, phones, or street addresses).
"""
from __future__ import annotations

import glob

from core import geo
from core.ingest import load_snapshot, snapshot_date_from_name

KEEP = [
    "chapter_id", "chapter_name", "zone", "region", "chapter_type",
    "account_type", "city", "state", "country", "lat", "lon", "snapshot_date",
]


def _newest(files: list[str]) -> str:
    from datetime import date
    return max(files, key=lambda p: (snapshot_date_from_name(p) or date.min, p))


def _build(files: list[str], out: str, label: str) -> None:
    if not files:
        print(f"No {label} export found — skipping {out}.")
        return
    df, snap = load_snapshot(_newest(files))
    df = geo.geocode(df)
    df[KEEP].to_csv(out, index=False)
    print(f"Wrote {out} — {len(df)} {label} chapters, snapshot {snap}.")


def main() -> None:
    all_files = sorted(glob.glob("data/snapshots/*.xlsx"))
    if not all_files:
        raise SystemExit("No exports in data/snapshots/. Add at least one and re-run.")
    inactive = [f for f in all_files if "inactive" in f.lower()]
    active = [f for f in all_files if "inactive" not in f.lower()]
    _build(active, "data/chapters_clean.csv", "active")
    _build(inactive, "data/chapters_inactive_clean.csv", "inactive")
    print("Done. No emails / phones / addresses included. Commit and push to update the live app.")


if __name__ == "__main__":
    main()
