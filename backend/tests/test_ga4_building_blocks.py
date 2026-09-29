"""The prompt's SQL building blocks must reproduce totals verified by independent queries."""

import os

import pytest
from google.cloud import bigquery

from analyst.datasets.ga4 import BUILDING_BLOCKS

pytestmark = pytest.mark.bigquery


@pytest.fixture(scope="module")
def client() -> bigquery.Client:
    return bigquery.Client(project=os.environ["GCP_PROJECT_ID"])


def query_one(client: bigquery.Client, select: str) -> dict:
    sql = f"WITH {BUILDING_BLOCKS}\n{select}"
    job_config = bigquery.QueryJobConfig(maximum_bytes_billed=3 * 10**9)
    return dict(next(iter(client.query(sql, job_config=job_config).result())))


def dry_run_bytes(client: bigquery.Client, select: str) -> int:
    sql = f"WITH {BUILDING_BLOCKS}\n{select}"
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    return client.query(sql, job_config=job_config).total_bytes_processed


def test_orders_are_deduplicated(client):
    row = query_one(
        client, "SELECT COUNT(*) AS orders, COUNT(DISTINCT order_id) AS ids, SUM(revenue) AS revenue FROM orders"
    )

    assert row["orders"] == row["ids"] == 4907
    assert row["revenue"] == pytest.approx(339457)


def test_sessions_and_users(client):
    row = query_one(client, "SELECT COUNT(*) AS sessions, COUNT(DISTINCT user_pseudo_id) AS users FROM sessions")

    assert row == {"sessions": 360129, "users": 270154}


def test_order_items_are_not_multiplied_by_item_count(client):
    row = query_one(client, "SELECT SUM(item_revenue) AS item_revenue FROM order_items")

    assert row["item_revenue"] == pytest.approx(339412)


def test_order_queries_skip_event_params(client):
    # Reading event_params costs ~1 GB; orders must not depend on it.
    assert dry_run_bytes(client, "SELECT SUM(revenue) FROM orders") < 300 * 10**6


def test_user_funnel_is_closed_so_steps_only_shrink(client):
    row = query_one(
        client,
        "SELECT COUNTIF(viewed_item) AS viewed, COUNTIF(added_to_cart) AS carted, "
        "COUNTIF(began_checkout) AS checkout, COUNTIF(purchased) AS purchased FROM user_funnel",
    )

    assert row == {"viewed": 61252, "carted": 12539, "checkout": 5656, "purchased": 2915}
