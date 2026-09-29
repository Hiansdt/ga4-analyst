"""The GA4 definition: its semantic layer must reproduce totals verified by independent queries."""

import pytest

from analyst.semantic.dataset import load_dataset
from analyst.semantic.layer import SemanticLayer

GA4 = load_dataset("ga4")
LAYER = SemanticLayer(GA4)


def test_revenue_comes_from_deduplicated_orders_alone():
    sql, _ = LAYER.compile(LAYER.query_model.model_validate({"metrics": ["revenue"]}))

    assert sql.endswith(
        "SELECT revenue\nFROM (SELECT ROUND(SUM(revenue), 2) AS revenue\nFROM orders\nWHERE order_date BETWEEN @start AND @end)"
    )


def test_product_metrics_cannot_be_split_by_visit_attributes():
    with pytest.raises(ValueError, match="run_sql"):
        LAYER.query_model.model_validate({"metrics": ["product_revenue"], "by": "device"})


@pytest.fixture(scope="module")
def run():
    import os

    from google.cloud import bigquery

    from analyst.adapters.bigquery import BigQueryRunner

    runner = BigQueryRunner(
        bigquery.Client(project=os.environ["GCP_PROJECT_ID"]),
        allowed_dataset=GA4.tables[0],
        max_bytes=5 * 10**9,
        max_rows=1000,
        timeout_s=60,
    )
    return lambda **fields: runner.run(*LAYER.compile(LAYER.query_model.model_validate(fields)))


# Expected values were verified by independent queries (tests/test_ga4_building_blocks.py, evals/cases.py).
@pytest.mark.bigquery
def test_full_period_totals_match_the_verified_values(run):
    orders = run(metrics=["revenue", "orders", "buyers", "sessions"])
    traffic = run(metrics=["converted_sessions", "users"])

    assert orders.rows[0] == {
        "revenue": pytest.approx(339457, abs=1),
        "orders": 4907,
        "buyers": 4055,
        "sessions": 360129,
    }
    assert traffic.rows[0] == {"converted_sessions": 4848, "users": 270154}


@pytest.mark.bigquery
def test_a_month_counts_orders_logged_across_its_boundary_once(run):
    result = run(metrics=["revenue"], start="2020-12-01", end="2020-12-31")

    assert result.rows[0]["revenue"] == pytest.approx(158166, abs=1)


@pytest.mark.bigquery
def test_a_breakdown_across_blocks_neither_repeats_nor_splits_segments(run):
    result = run(metrics=["revenue", "sessions", "conversion_rate_pct"], by="device")

    devices = [row["device"] for row in result.rows]
    assert len(devices) == len(set(devices))
    assert sum(row["revenue"] or 0 for row in result.rows) == pytest.approx(339457, abs=1)
    assert sum(row["sessions"] or 0 for row in result.rows) == 360129
    mobile = next(row for row in result.rows if row["device"] == "mobile")
    assert mobile["conversion_rate_pct"] == pytest.approx(1.393, abs=0.001)


@pytest.mark.bigquery
def test_order_metrics_do_not_pay_for_session_data(run):
    # Unused building blocks are not evaluated; reading event_params (sessions) costs ~1 GB.
    assert run(metrics=["revenue"], by="channel").bytes_processed < 300 * 10**6
