"""The TheLook definition: its semantic layer must reproduce totals verified by independent queries.

Expected values come from hand-written queries on the raw snapshot tables (not through the building blocks),
run on 2026-09-28 against project-712b2ec8-82d4-4a79-b9b.thelook_snapshot.
"""

import os

import pytest

from analyst.semantic.dataset import load_dataset
from analyst.semantic.layer import SemanticLayer

THELOOK = load_dataset("thelook")
LAYER = SemanticLayer(THELOOK)


def test_signup_and_visit_channels_are_different_dimensions():
    # They mean different things, so a breakdown must never join one to the other.
    with pytest.raises(ValueError, match="run_sql"):
        LAYER.query_model.model_validate({"metrics": ["revenue", "sessions"], "by": "signup_channel"})


@pytest.fixture(scope="module")
def run():
    from google.cloud import bigquery

    from analyst.adapters.bigquery import BigQueryRunner

    runner = BigQueryRunner(
        bigquery.Client(project=os.environ["GCP_PROJECT_ID"]),
        allowed_datasets=THELOOK.tables,
        max_bytes=5 * 10**9,
        max_rows=1000,
        timeout_s=60,
    )
    return lambda **fields: runner.run(*LAYER.compile(LAYER.query_model.model_validate(fields)))


@pytest.mark.bigquery
def test_full_period_totals_match_the_verified_values(run):
    sales = run(metrics=["revenue", "gross_profit", "units_sold", "orders"]).rows[0]
    customers = run(metrics=["buyers", "sessions", "converted_sessions"]).rows[0]

    assert sales == {"revenue": 8057059.49, "gross_profit": 4183547.27, "units_sold": 135619, "orders": 94173}
    assert customers == {"buyers": 66193, "sessions": 682474, "converted_sessions": 180539}


@pytest.mark.bigquery
def test_a_month_matches_the_verified_value(run):
    assert run(metrics=["revenue"], start="2026-08-01", end="2026-08-31").rows[0]["revenue"] == 351981.62


@pytest.mark.bigquery
def test_a_breakdown_across_blocks_neither_repeats_nor_splits_segments(run):
    result = run(metrics=["revenue", "orders"], by="signup_channel")

    assert len(result.rows) == 5
    assert round(sum(row["revenue"] for row in result.rows), 2) == 8057059.49
    assert sum(row["orders"] for row in result.rows) == 94173


@pytest.mark.bigquery
def test_category_rankings_match_the_verified_values(run):
    profit = run(metrics=["gross_profit"], by="category", limit=1).rows[0]
    returns = run(metrics=["item_return_rate_pct"], by="category", limit=1).rows[0]

    assert profit == {"category": "Outerwear & Coats", "gross_profit": 537838.72}
    assert returns == {"category": "Jumpsuits & Rompers", "item_return_rate_pct": 13.22}
