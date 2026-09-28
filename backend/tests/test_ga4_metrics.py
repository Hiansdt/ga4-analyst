import datetime

import pytest
from pydantic import ValidationError

from ga4_agent.datasets.ga4 import BUILDING_BLOCKS, DATASET_END, DATASET_START
from ga4_agent.datasets.ga4_metrics import MetricsQuery, compile_query, describe


def compiled(**fields) -> tuple[str, dict]:
    """The generated part of the SQL, after the verbatim building blocks, and the parameters."""
    sql, params = compile_query(MetricsQuery.model_validate(fields))
    blocks, generated = sql.split(BUILDING_BLOCKS)
    assert blocks == "WITH\n"
    return generated, params


def test_a_total_reads_one_building_block_over_the_full_range_by_default():
    sql, params = compiled(metrics=["revenue", "orders"])

    assert "FROM orders" in sql
    assert "FROM sessions" not in sql
    assert "GROUP BY" not in sql
    assert params == {"start": DATASET_START, "end": DATASET_END}


def test_metrics_from_different_blocks_are_aggregated_separately_then_joined_on_the_breakdown():
    sql, _ = compiled(metrics=["revenue", "sessions"], by="device")

    assert "FROM orders" in sql
    assert "FROM sessions" in sql
    assert "FULL OUTER JOIN" in sql
    assert "USING (device)" in sql


def test_totals_from_different_blocks_are_cross_joined():
    sql, _ = compiled(metrics=["revenue", "sessions"])

    assert "CROSS JOIN" in sql


def test_filter_values_are_parameters_not_sql():
    sql, params = compiled(metrics=["revenue"], filters={"country": ["Côte d'Ivoire"]})

    assert "Ivoire" not in sql
    assert "IN UNNEST(@country)" in sql
    assert params["country"] == ["Côte d'Ivoire"]


def test_categories_are_ranked_by_the_first_metric_and_limited():
    sql, params = compiled(metrics=["product_revenue", "units_sold"], by="product", limit=5)

    assert "ORDER BY product_revenue DESC" in sql
    assert params["limit"] == 5


def test_time_series_are_in_date_order_and_complete():
    sql, params = compiled(metrics=["revenue"], by="month")

    assert "ORDER BY month" in sql
    assert "limit" not in params


def test_dates_are_filtered_on_each_block_own_date_column():
    sql, params = compiled(metrics=["revenue", "sessions"], start="2020-12-01", end="2020-12-31")

    assert "order_date BETWEEN @start AND @end" in sql
    assert "session_date BETWEEN @start AND @end" in sql
    assert params["start"] == datetime.date(2020, 12, 1)


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"metrics": ["product_revenue"], "by": "device"}, "run_sql"),
        ({"metrics": ["sessions"], "filters": {"product": ["Mug"]}}, "run_sql"),
        ({"metrics": ["revenue"], "start": "2019-01-01"}, "2020-11-01 to 2021-01-31"),
        ({"metrics": ["revenue"], "start": "2021-01-10", "end": "2021-01-01"}, "start"),
        ({"metrics": []}, "at least 1"),
    ],
)
def test_requests_the_blocks_cannot_answer_are_rejected_with_a_way_forward(fields, message):
    with pytest.raises(ValidationError, match=message):
        MetricsQuery.model_validate(fields)


@pytest.mark.parametrize(
    ("fields", "label"),
    [
        ({"metrics": ["revenue"]}, "Revenue"),
        ({"metrics": ["revenue", "sessions"], "by": "device"}, "Revenue and sessions by device"),
        (
            {"metrics": ["orders", "buyers", "average_order_value"], "by": "month"},
            "Orders, buyers and average order value by month",
        ),
        (
            {"metrics": ["conversion_rate_pct"], "start": "2020-12-01", "end": "2020-12-31"},
            "Conversion rate, Dec 1 to Dec 31, 2020",
        ),
        ({"metrics": ["revenue"], "start": "2020-12-15", "end": "2021-01-15"}, "Revenue, Dec 15, 2020 to Jan 15, 2021"),
        ({"metrics": ["sessions"], "filters": {"device": ["mobile", "tablet"]}}, "Sessions for mobile and tablet"),
    ],
)
def test_describes_a_query_in_plain_language(fields, label):
    assert describe(MetricsQuery.model_validate(fields)) == label


@pytest.fixture(scope="module")
def run():
    import os

    from google.cloud import bigquery

    from ga4_agent.adapters.bigquery import BigQueryRunner
    from ga4_agent.datasets.ga4 import DATASET

    runner = BigQueryRunner(
        bigquery.Client(project=os.environ["GCP_PROJECT_ID"]),
        allowed_dataset=DATASET,
        max_bytes=5 * 10**9,
        max_rows=1000,
        timeout_s=60,
    )
    return lambda **fields: runner.run(*compile_query(MetricsQuery.model_validate(fields)))


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
