import datetime
import os
from decimal import Decimal

import pytest

from analyst.adapters.bigquery import BigQueryRunner, to_json_value
from analyst.datasets.ga4 import DATASET
from analyst.ports.sql import Column, QueryError

EVENTS = f"`{DATASET}.events_*`"


def test_converts_bigquery_values_to_json_safe_values():
    value = {
        "day": datetime.date(2020, 12, 1),
        "at": datetime.datetime(2020, 12, 1, 9, 30, tzinfo=datetime.UTC),
        "amount": Decimal("12.50"),
        "tags": [Decimal(1), "a"],
    }

    assert to_json_value(value) == {
        "day": "2020-12-01",
        "at": "2020-12-01T09:30:00+00:00",
        "amount": 12.5,
        "tags": [1.0, "a"],
    }


@pytest.fixture(scope="module")
def runner() -> BigQueryRunner:
    from google.cloud import bigquery

    return BigQueryRunner(
        bigquery.Client(project=os.environ["GCP_PROJECT_ID"]),
        allowed_dataset=DATASET,
        max_bytes=5 * 10**9,
        max_rows=10,
        timeout_s=60,
    )


@pytest.mark.bigquery
def test_returns_typed_columns_and_caps_rows(runner):
    result = runner.run(
        f"SELECT PARSE_DATE('%Y%m%d', event_date) AS day, COUNT(*) AS events FROM {EVENTS} GROUP BY 1 ORDER BY 1"
    )

    assert result.columns == [Column("day", "DATE"), Column("events", "INTEGER")]
    assert result.total_rows == 92
    assert len(result.rows) == 10
    assert result.rows[0]["day"] == "2020-11-01"
    assert result.bytes_processed > 0


@pytest.mark.bigquery
def test_syntax_errors_come_back_as_query_errors(runner):
    with pytest.raises(QueryError, match="Syntax error") as error:
        runner.run(f"SELEC event_name FROM {EVENTS}")

    # Only BigQuery's reason reaches the model, not the request URL or job id.
    assert "https://" not in str(error.value)


@pytest.mark.bigquery
def test_tables_outside_the_dataset_are_rejected(runner):
    with pytest.raises(QueryError, match="Only tables in"):
        runner.run("SELECT word FROM `bigquery-public-data.samples.shakespeare` LIMIT 1")


@pytest.mark.bigquery
def test_writes_are_rejected(runner):
    with pytest.raises(QueryError):
        runner.run(f"DELETE FROM `{DATASET}.events_20201101` WHERE TRUE")


@pytest.mark.bigquery
def test_values_are_passed_as_query_parameters(runner):
    result = runner.run(
        f"SELECT device.category AS device, COUNT(*) AS events FROM {EVENTS} "
        "WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', @start) AND FORMAT_DATE('%Y%m%d', @start) "
        "AND device.category IN UNNEST(@devices) GROUP BY 1 ORDER BY 1 LIMIT @limit",
        {"start": datetime.date(2020, 12, 1), "devices": ["mobile", "tablet"], "limit": 5},
    )

    assert [row["device"] for row in result.rows] == ["mobile", "tablet"]
