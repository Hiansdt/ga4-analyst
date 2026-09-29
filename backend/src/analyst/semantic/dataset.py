"""A dataset definition: everything dataset-specific the analyst needs, as data.

Definitions live in YAML files under datasets/ and are validated when loaded. Names end up inside
generated SQL, so they are restricted to lowercase identifiers.
"""

from datetime import date
from pathlib import Path
from typing import Annotated, Self

import yaml
from pydantic import BaseModel, StringConstraints, model_validator

DATASETS_DIR = Path(__file__).parent.parent / "datasets"

Name = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]


class Period(BaseModel):
    start: date
    end: date  # also "today" for relative dates such as "last month"

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.start > self.end:
            raise ValueError("start must not be after end")
        return self


class Dimension(BaseModel):
    name: Name
    description: str


class Block(BaseModel):
    """A building block: one CTE at a known grain, which later blocks may read from."""

    name: Name
    description: str  # the grain and meaning, e.g. "One row per order"
    sql: str
    date_column: Name | None = None
    dimensions: dict[Name, str] = {}  # dimension name -> column or expression in this block


class Metric(BaseModel):
    name: Name
    block: Name
    sql: str  # an aggregate over the block, e.g. SUM(revenue)
    description: str


class Dataset(BaseModel):
    name: str
    tables: list[str]  # datasets queries may read, e.g. "bigquery-public-data.ga4_obfuscated_sample_ecommerce"
    period: Period
    description: str
    dimensions: list[Dimension]
    blocks: list[Block]
    block_notes: str = ""
    metrics: list[Metric]
    reference_totals: str = ""
    metric_notes: str = ""
    example_questions: list[str] = []

    @model_validator(mode="after")
    def consistent(self) -> Self:
        for kind, names in [
            ("dimension", [d.name for d in self.dimensions]),
            ("block", [b.name for b in self.blocks]),
            ("metric", [m.name for m in self.metrics]),
        ]:
            duplicates = sorted({name for name in names if names.count(name) > 1})
            if duplicates:
                raise ValueError(f"duplicate {kind} names: {', '.join(duplicates)}")

        declared = {d.name for d in self.dimensions}
        blocks = {b.name: b for b in self.blocks}
        for block in self.blocks:
            undeclared = sorted(set(block.dimensions) - declared)
            if undeclared:
                raise ValueError(f"block {block.name} uses undeclared dimension {', '.join(undeclared)}")
        for metric in self.metrics:
            block = blocks.get(metric.block)
            if block is None:
                raise ValueError(f"metric {metric.name} refers to unknown block {metric.block}")
            if block.date_column is None:
                raise ValueError(f"block {block.name} has metrics, so it needs a date_column")
        return self


def load_dataset(name: str) -> Dataset:
    """Load datasets/<name>.yaml."""
    path = DATASETS_DIR / f"{name}.yaml"
    return Dataset.model_validate(yaml.safe_load(path.read_text()))
