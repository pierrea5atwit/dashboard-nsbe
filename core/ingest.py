"""Ingest a chapter-export .xlsx into a clean, canonical DataFrame.

Hardened against the brittleness of the original Colab script:
- detects the header row instead of hardcoding ``skiprows=11``
- reads .xlsx directly (no csv round-trip)
- renames source columns to a stable canonical schema
- parses the snapshot date from the filename
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

# Raw source column -> canonical name. Anything not listed is dropped.
COLUMN_MAP = {
    "Community Group: ID": "chapter_id",
    "Community Group: Community Group Name": "chapter_name",
    "Linked Chapter Account: Zone": "zone",
    "Linked Chapter Account: Region": "region",
    "Type": "chapter_type",                       # trailing col: Collegiate / NSBE Jr. / Professional
    "Linked Chapter Account: Type": "account_type",
    "Linked Chapter Account: Billing City": "city",
    "Linked Chapter Account: Billing State/Province": "state",
    "Linked Chapter Account: Billing Country": "country",
    "Linked Chapter Account: Account Email": "email",
    "Linked Chapter Account: Phone": "phone",
}

HEADER_MARKER = "Community Group: ID"
_DATE_RE = re.compile(r"(\d{2})[_-](\d{2})[_-](\d{4})")  # e.g. 06_19_2026


def detect_header_row(path: str | Path, max_scan: int = 30) -> int:
    """Return the 0-indexed row containing the real column headers."""
    raw = pd.read_excel(path, header=None, nrows=max_scan)
    for i in range(len(raw)):
        if raw.iloc[i].astype(str).str.contains(HEADER_MARKER, regex=False).any():
            return i
    raise ValueError(f"Header row (containing {HEADER_MARKER!r}) not found in first {max_scan} rows.")


def snapshot_date_from_name(path: str | Path) -> date | None:
    """Parse a MM_DD_YYYY date out of the filename, if present."""
    m = _DATE_RE.search(Path(path).name)
    if not m:
        return None
    mm, dd, yyyy = (int(x) for x in m.groups())
    return date(yyyy, mm, dd)


def load_snapshot(path: str | Path) -> tuple[pd.DataFrame, date | None]:
    """Read one export and return ``(clean_df, snapshot_date)``.

    Fails loudly if required columns are missing rather than silently
    producing a misaligned frame.
    """
    path = Path(path)
    header = detect_header_row(path)
    df = pd.read_excel(path, skiprows=header)

    # Only id + name are truly required. Other columns are mapped if present and
    # filled with NA if absent, so exports with slightly different schemas
    # (e.g. the inactive export, which lacks the chapter Type column) still load.
    required = ["Community Group: ID", "Community Group: Community Group Name"]
    missing_required = [c for c in required if c not in df.columns]
    if missing_required:
        raise ValueError(
            "Export is missing required column(s): "
            + ", ".join(missing_required)
            + ". Update COLUMN_MAP in core/ingest.py if the export format changed."
        )

    present = {src: canon for src, canon in COLUMN_MAP.items() if src in df.columns}
    df = df[list(present)].rename(columns=present)
    for canon in COLUMN_MAP.values():  # ensure a uniform set of canonical columns
        if canon not in df.columns:
            df[canon] = pd.NA

    # Normalize text columns: strip whitespace, treat blanks as NaN.
    for col in ["zone", "region", "chapter_type", "account_type", "city", "state", "country", "email", "phone"]:
        df[col] = df[col].astype("string").str.strip().replace({"": pd.NA})

    df = df.dropna(subset=["chapter_id"]).reset_index(drop=True)

    snap = snapshot_date_from_name(path)
    df["snapshot_date"] = pd.Timestamp(snap) if snap else pd.NaT
    return df, snap
