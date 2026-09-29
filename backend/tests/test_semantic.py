"""The semantic layer on a small made-up dataset: nothing here knows about GA4."""

import datetime

import pytest
from pydantic import ValidationError

from analyst.semantic.context import render_context
from analyst.semantic.dataset import Dataset
from analyst.semantic.layer import SemanticLayer

SHOP = {
    "name": "Test Shop",
    "tables": ["proj.shop"],
    "period": {"start": "2024-01-01", "end": "2024-03-31"},
    "description": "- A shop that sells mugs.",
    "dimensions": [
        {"name": "device", "description": "Device type."},
        {"name": "product", "description": "Product name."},
    ],
    "blocks": [
        {
            "name": "orders",
            "description": "One row per order.",
            "sql": "SELECT * FROM `proj.shop.orders`",
            "date_column": "order_date",
            "dimensions": {"device": "device"},
        },
        {
            "name": "visits",
            "description": "One row per visit.",
            "sql": "SELECT * FROM `proj.shop.visits`",
            "date_column": "visit_date",
            "dimensions": {"device": "device_type"},
        },
        {
            "name": "lines",
            "description": "One row per order line.",
            "sql": "SELECT order_date, item.name AS item_name, item.quantity\nFROM orders, UNNEST(items) AS item",
            "date_column": "order_date",
            "dimensions": {"product": "item_name"},
        },
    ],
    "block_notes": "Visits are counted per browser.",
    "metrics": [
        {"name": "revenue", "block": "orders", "sql": "SUM(total)", "description": "Order totals in USD."},
        {"name": "visits", "block": "visits", "sql": "COUNT(*)", "description": "Visits to the site."},
        {"name": "units", "block": "lines", "sql": "SUM(quantity)", "description": "Units sold."},
    ],
    "reference_totals": "Revenue $1,000.",
    "metric_notes": "- Revenue excludes refunds.",
    "example_questions": ["What was revenue by month?"],
}


def shop(**changes) -> Dataset:
    return Dataset.model_validate({**SHOP, **changes})


@pytest.fixture
def layer() -> SemanticLayer:
    return SemanticLayer(shop())


def compiled(layer: SemanticLayer, **fields) -> tuple[str, dict]:
    """The generated part of the SQL, after the verbatim building blocks, and the parameters."""
    sql, params = layer.compile(layer.query_model.model_validate(fields))
    blocks, generated = sql.split(layer.with_clause())
    assert blocks == ""
    return generated, params


# The dataset definition


def test_blocks_become_one_with_clause_in_definition_order(layer):
    assert layer.with_clause() == (
        "WITH\norders AS (\n  SELECT * FROM `proj.shop.orders`\n),\n"
        "visits AS (\n  SELECT * FROM `proj.shop.visits`\n),\n"
        "lines AS (\n  SELECT order_date, item.name AS item_name, item.quantity\n  FROM orders, UNNEST(items) AS item\n)"
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"metrics": [{"name": "Revenue; DROP", "block": "orders", "sql": "SUM(x)", "description": "d"}]}, "pattern"),
        ({"metrics": [{"name": "revenue", "block": "carts", "sql": "SUM(x)", "description": "d"}]}, "unknown block"),
        ({"metrics": SHOP["metrics"] + [SHOP["metrics"][0]]}, "duplicate"),
        ({"dimensions": SHOP["dimensions"][:1]}, "undeclared dimension"),
        ({"period": {"start": "2024-03-31", "end": "2024-01-01"}}, "start"),
    ],
)
def test_invalid_definitions_are_rejected_when_loaded(changes, message):
    with pytest.raises(ValidationError, match=message):
        shop(**changes)


def test_a_block_with_metrics_needs_a_date_column():
    blocks = [{**SHOP["blocks"][0], "date_column": None}, *SHOP["blocks"][1:]]

    with pytest.raises(ValidationError, match="date_column"):
        shop(blocks=blocks)


# Compiling metric requests


def test_a_total_reads_one_block_over_the_full_period_by_default(layer):
    sql, params = compiled(layer, metrics=["revenue"])

    assert "FROM orders" in sql
    assert "FROM visits" not in sql
    assert "GROUP BY" not in sql
    assert params == {"start": datetime.date(2024, 1, 1), "end": datetime.date(2024, 3, 31)}


def test_metrics_from_different_blocks_are_aggregated_separately_then_joined_on_the_breakdown(layer):
    sql, _ = compiled(layer, metrics=["revenue", "visits"], by="device")

    assert "IFNULL(device, '(not set)') AS device" in sql
    assert "IFNULL(device_type, '(not set)') AS device" in sql
    assert "FULL OUTER JOIN" in sql
    assert "USING (device)" in sql


def test_totals_from_different_blocks_are_cross_joined(layer):
    sql, _ = compiled(layer, metrics=["revenue", "visits"])

    assert "CROSS JOIN" in sql


def test_filter_values_are_parameters_not_sql(layer):
    sql, params = compiled(layer, metrics=["revenue"], filters={"device": ["O'Brien's phone"]})

    assert "Brien" not in sql
    assert "device IN UNNEST(@device)" in sql
    assert params["device"] == ["O'Brien's phone"]


def test_segments_are_ranked_by_the_first_metric_and_limited(layer):
    sql, params = compiled(layer, metrics=["units"], by="product", limit=5)

    assert "ORDER BY units DESC NULLS LAST" in sql
    assert params["limit"] == 5


def test_time_series_are_in_date_order_and_complete(layer):
    sql, params = compiled(layer, metrics=["revenue"], by="month")

    assert "FORMAT_DATE('%Y-%m', order_date) AS month" in sql
    assert "ORDER BY month" in sql
    assert "limit" not in params


def test_dates_are_filtered_on_each_block_own_date_column(layer):
    sql, _ = compiled(layer, metrics=["revenue", "visits"], start="2024-02-01", end="2024-02-29")

    assert "order_date BETWEEN @start AND @end" in sql
    assert "visit_date BETWEEN @start AND @end" in sql


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"metrics": ["units"], "by": "device"}, "run_sql"),
        ({"metrics": ["visits"], "filters": {"product": ["Mug"]}}, "run_sql"),
        ({"metrics": ["revenue"], "start": "2023-01-01"}, "2024-01-01 to 2024-03-31"),
        ({"metrics": ["revenue"], "start": "2024-02-10", "end": "2024-02-01"}, "start"),
        ({"metrics": ["profit"]}, "revenue"),
        ({"metrics": []}, "at least 1"),
    ],
)
def test_requests_the_blocks_cannot_answer_are_rejected_with_a_way_forward(layer, fields, message):
    with pytest.raises(ValidationError, match=message):
        layer.query_model.model_validate(fields)


@pytest.mark.parametrize(
    ("fields", "label"),
    [
        ({"metrics": ["revenue"]}, "Revenue"),
        ({"metrics": ["revenue", "visits"], "by": "device"}, "Revenue and visits by device"),
        ({"metrics": ["revenue"], "start": "2024-02-01", "end": "2024-02-29"}, "Revenue, Feb 1 to Feb 29, 2024"),
        ({"metrics": ["visits"], "filters": {"device": ["mobile", "tablet"]}}, "Visits for mobile and tablet"),
    ],
)
def test_describes_a_request_in_plain_language(layer, fields, label):
    assert layer.describe(layer.query_model.model_validate(fields)) == label


# What the model reads


def test_the_tool_description_lists_metrics_and_where_they_can_be_broken_down(layer):
    description = layer.tool_description()

    assert "- revenue: Order totals in USD. Breakdowns: day, week, month, device." in description
    assert "- units: Units sold. Breakdowns: day, week, month, product." in description
    assert "- device: Device type." in description


def test_the_dataset_context_carries_the_definition_and_the_blocks():
    context = render_context(shop())

    assert context.startswith("# The data\n\n- A shop that sells mugs.")
    assert "```sql\nWITH\norders AS (" in context
    assert "- `lines`: One row per order line." in context
    assert "(`order_date`, `visit_date`)" in context
    assert "Visits are counted per browser." in context
    assert "# Reference totals\n\nRevenue $1,000." in context
    assert context.endswith("# Metric definitions\n\n- Revenue excludes refunds.")
