"""Metrics layer over the GA4 building blocks: the model picks metrics and a breakdown, this module writes the SQL.

Each metric belongs to the building block whose grain defines it (revenue to orders, conversion to sessions).
Metrics from different blocks are aggregated separately and joined on the breakdown, so a query can never
repeat orders once per session. Values from the request become query parameters, never SQL text.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from ga4_agent.datasets.ga4 import BUILDING_BLOCKS, DATASET_END, DATASET_START

Metric = Literal[
    "revenue",
    "orders",
    "buyers",
    "average_order_value",
    "sessions",
    "converted_sessions",
    "conversion_rate_pct",
    "users",
    "product_revenue",
    "units_sold",
]
Breakdown = Literal["day", "week", "month", "device", "country", "channel", "source", "product", "category"]
Segment = Literal["device", "country", "channel", "source", "product", "category"]

DESCRIPTION = """\
Compute the store's standard metrics without writing SQL. Prefer this over run_sql whenever it can \
answer the question: its definitions are verified, so numbers stay consistent. Returns a result_id \
for create_chart, like run_sql.

Metrics: revenue (USD, duplicate purchases removed), orders, buyers (users with an order), \
average_order_value, sessions (visits), converted_sessions (visits with a purchase), \
conversion_rate_pct (converted sessions / sessions, already in percent), users (distinct browsers \
or devices), product_revenue and units_sold (per product line; only by product or category).

Breakdowns and filters: day, week, month, device, country, channel (acquisition medium: how the \
user first arrived, e.g. organic, cpc, referral, (none) for direct), source, product, category. \
For shares, growth or anything else these cannot express, use run_sql."""

TIME_BREAKDOWNS = {
    "day": "{date}",
    "week": "DATE_TRUNC({date}, WEEK(MONDAY))",
    "month": "FORMAT_DATE('%Y-%m', {date})",
}

USER_SEGMENTS = {
    "device": "device_category",
    "country": "country",
    "channel": "acquisition_medium",
    "source": "acquisition_source",
}


@dataclass(frozen=True)
class Block:
    name: str
    date_column: str
    segments: dict[str, str]  # segment name -> column in the block
    metrics: dict[str, str]  # metric name -> aggregate expression


BLOCKS = (
    Block(
        "orders",
        "order_date",
        USER_SEGMENTS,
        {
            "revenue": "ROUND(SUM(revenue), 2)",
            "orders": "COUNT(*)",
            "buyers": "COUNT(DISTINCT user_pseudo_id)",
            "average_order_value": "ROUND(SAFE_DIVIDE(SUM(revenue), COUNT(*)), 2)",
        },
    ),
    Block(
        "sessions",
        "session_date",
        USER_SEGMENTS,
        {
            "sessions": "COUNT(*)",
            "converted_sessions": "COUNTIF(converted)",
            "conversion_rate_pct": "ROUND(100 * SAFE_DIVIDE(COUNTIF(converted), COUNT(*)), 3)",
        },
    ),
    Block("events", "event_date", USER_SEGMENTS, {"users": "COUNT(DISTINCT user_pseudo_id)"}),
    Block(
        "order_items",
        "order_date",
        {"product": "item_name", "category": "item_category"},
        {"product_revenue": "ROUND(SUM(item_revenue), 2)", "units_sold": "SUM(quantity)"},
    ),
)
BLOCK_OF = {metric: block for block in BLOCKS for metric in block.metrics}


class MetricsQuery(BaseModel):
    metrics: list[Metric] = Field(min_length=1, max_length=4, description="Metrics to compute, most important first.")
    by: Breakdown | None = Field(None, description="Break the metrics down by time or by a segment. Omit for totals.")
    filters: dict[Segment, list[str]] = Field(
        default_factory=dict, description='Keep only these values, e.g. {"device": ["mobile"]}.'
    )
    start: date = Field(DATASET_START, description="First day, inclusive.")
    end: date = Field(DATASET_END, description="Last day, inclusive.")
    limit: int = Field(25, ge=1, le=500, description="Rows to keep for segment breakdowns, ranked by the first metric.")

    @model_validator(mode="after")
    def answerable_by_the_blocks(self) -> Self:
        if not DATASET_START <= self.start <= self.end <= DATASET_END:
            raise ValueError(
                f"start must not be after end, and both within the data: "
                f"{DATASET_START:%Y-%m-%d} to {DATASET_END:%Y-%m-%d}."
            )
        segments = [name for name in [self.by, *self.filters] if name and name not in TIME_BREAKDOWNS]
        for metric in self.metrics:
            block = BLOCK_OF[metric]
            unsupported = [name for name in segments if name not in block.segments]
            if unsupported:
                raise ValueError(
                    f"{metric} cannot be broken down or filtered by {', '.join(unsupported)}; "
                    "use run_sql with the building blocks instead."
                )
        return self


def compile_query(query: MetricsQuery) -> tuple[str, dict]:
    """The SQL and its parameters for a validated query."""
    blocks = [block for block in BLOCKS if any(metric in block.metrics for metric in query.metrics)]
    parts = [_aggregate(block, query) for block in blocks]
    params: dict = {"start": query.start, "end": query.end, **query.filters}

    if query.by is None:
        combined = "\nCROSS JOIN ".join(f"({part})" for part in parts)
        select = f"SELECT {', '.join(query.metrics)}\nFROM {combined}"
    else:
        combined = _join_using(parts, query.by)
        select = f"SELECT {query.by}, {', '.join(query.metrics)}\nFROM {combined}"
        if query.by in TIME_BREAKDOWNS:
            select += f"\nORDER BY {query.by}"
        else:
            select += f"\nORDER BY {query.metrics[0]} DESC NULLS LAST\nLIMIT @limit"
            params["limit"] = query.limit

    return f"WITH\n{BUILDING_BLOCKS}\n{select}", params


def _aggregate(block: Block, query: MetricsQuery) -> str:
    columns = [f"{block.metrics[metric]} AS {metric}" for metric in query.metrics if metric in block.metrics]
    where = [f"{block.date_column} BETWEEN @start AND @end"]
    where += [f"{block.segments[name]} IN UNNEST(@{name})" for name in query.filters]
    group_by = ""
    if query.by is not None:
        columns.insert(0, f"{_breakdown(block, query.by)} AS {query.by}")
        group_by = "\nGROUP BY 1"
    return f"SELECT {', '.join(columns)}\nFROM {block.name}\nWHERE {' AND '.join(where)}{group_by}"


def _breakdown(block: Block, by: str) -> str:
    if by in TIME_BREAKDOWNS:
        return TIME_BREAKDOWNS[by].format(date=block.date_column)
    # Missing values become one labeled group, so the join matches them across blocks.
    return f"IFNULL({block.segments[by]}, '(not set)')"


def _join_using(parts: list[str], by: str) -> str:
    joined = f"({parts[0]})"
    for part in parts[1:]:
        joined += f"\nFULL OUTER JOIN ({part}) USING ({by})"
    return joined
