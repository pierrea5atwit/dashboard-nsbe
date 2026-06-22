"""Smoke + correctness tests for the ingest/engine/geo pipeline.

Run from the project root:  python -m pytest -q   (or: python tests/test_pipeline.py)
Skips gracefully if no snapshot is present.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import engine, geo
from core.ingest import load_snapshot, snapshot_date_from_name

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS = sorted((ROOT / "data" / "snapshots").glob("*.xlsx"))
pytestmark = pytest.mark.skipif(not SNAPSHOTS, reason="no snapshot in data/snapshots")


@pytest.fixture(scope="module")
def df():
    frame, _ = load_snapshot(str(SNAPSHOTS[-1]))
    return frame


def test_canonical_schema(df):
    expected = {"chapter_id", "chapter_name", "zone", "region", "chapter_type", "country"}
    assert expected.issubset(df.columns)
    assert df["chapter_id"].notna().all()  # rows without a stable key are dropped


def test_snapshot_date_parsed_from_name():
    d = snapshot_date_from_name("Chapters_Active_As_Of_06_19_2026.xlsx")
    assert (d.year, d.month, d.day) == (2026, 6, 19)


def test_filter_is_subset(df):
    res = engine.apply_filters(df, {"chapter_type": ["NSBE Jr. Chapter"]})
    assert len(res) <= len(df)
    assert set(res["chapter_type"].unique()) == {"NSBE Jr. Chapter"}


def test_composed_filter_and_logic(df):
    res = engine.apply_filters(df, {"region": ["Region 1"], "chapter_type": ["Collegiate Chapter"]})
    assert (res["region"] == "Region 1").all()
    assert (res["chapter_type"] == "Collegiate Chapter").all()


def test_recipe_count_matches_manual(df):
    r = engine.load_recipe(ROOT / "recipes" / "region_1_collegiate.yaml")
    via_recipe = engine.apply_recipe(df, r)
    via_manual = engine.apply_filters(df, r.filters)
    assert len(via_recipe) == len(via_manual)


def test_recipe_rejects_unknown_dimension():
    with pytest.raises(Exception):
        engine.Recipe(name="bad", filters={"not_a_dim": ["x"]})


def test_geocode_coverage(df):
    g = geo.geocode(df)
    assert geo.coverage(g) >= 0.98


def test_chapter_name_list_sorted_unique(df):
    names = engine.chapter_name_list(df)
    assert names == sorted(set(names))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
