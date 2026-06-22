"""The single audited transform: a validated Recipe applied to a snapshot.

Both saved-recipe buttons and the manual filter widgets call ``apply_filters``,
so there is exactly one code path that turns a filter spec into rows.

Dependency-free on purpose: uses only the stdlib + pandas, so the app runs on
Streamlit Cloud's base image without any extra pip installs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# Filterable canonical dimensions. Filtering is AND across dimensions,
# OR within a single dimension's list (isin).
FILTER_DIMENSIONS = ["zone", "region", "chapter_type", "state", "country", "account_type"]


@dataclass
class Recipe:
    name: str
    filters: dict[str, list[str]] = field(default_factory=dict)
    snapshot: str = "latest"
    outputs: list[str] = field(default_factory=lambda: ["map", "table", "list"])

    def __post_init__(self) -> None:
        bad = set(self.filters) - set(FILTER_DIMENSIONS)
        if bad:
            raise ValueError(
                f"Recipe {self.name!r} has unknown filter dimension(s): {sorted(bad)}. "
                f"Allowed: {FILTER_DIMENSIONS}"
            )


def load_recipe(path: str | Path) -> Recipe:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Recipe(
        name=data["name"],
        filters=data.get("filters", {}),
        snapshot=data.get("snapshot", "latest"),
        outputs=data.get("outputs", ["map", "table", "list"]),
    )


def load_recipes(folder: str | Path) -> list[Recipe]:
    folder = Path(folder)
    return [load_recipe(p) for p in sorted(folder.glob("*.json"))]


def apply_recipe(df: pd.DataFrame, recipe: Recipe) -> pd.DataFrame:
    """Return the rows of ``df`` matching ``recipe.filters``."""
    return apply_filters(df, recipe.filters)


def apply_filters(df: pd.DataFrame, filters: dict[str, list[str]]) -> pd.DataFrame:
    out = df
    for dim, values in filters.items():
        if not values:
            continue
        out = out[out[dim].isin(values)]
    return out.reset_index(drop=True)


def chapter_name_list(df: pd.DataFrame) -> list[str]:
    """Sorted, de-duplicated chapter names for the active filter."""
    names = df["chapter_name"].dropna().astype(str).str.strip()
    return sorted(set(names))
