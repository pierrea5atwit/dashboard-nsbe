"""Regenerate the committed, PII-free data file the cloud app reads.

Run this after dropping a new export into data/snapshots/, then commit + push:

    python build_clean_data.py
    git add data/chapters_clean.csv && git commit -m "Update data" && git push

It reads the newest snapshot, applies the standard cleaning + geocoding, and
writes only non-sensitive columns (no emails, phones, or street addresses).
"""
from __future__ import annotations

import glob
import sys

from core import geo
from core.ingest import load_snapshot

KEEP = [
    "chapter_id", "chapter_name", "zone", "region", "chapter_type",
    "account_type", "city", "state", "country", "lat", "lon", "snapshot_date",
]


def main() -> None:
    files = sorted(glob.glob("data/snapshots/*.xlsx"))
    if not files:
        sys.exit("No export found in data/snapshots/. Add one and re-run.")
    df, snap = load_snapshot(files[-1])
    df = geo.geocode(df)
    df[KEEP].to_csv("data/chapters_clean.csv", index=False)
    print(f"Wrote data/chapters_clean.csv — {len(df)} chapters, snapshot {snap}.")
    print("No emails / phones / addresses included. Commit and push to update the live app.")


if __name__ == "__main__":
    main()
