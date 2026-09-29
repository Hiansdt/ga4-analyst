"""The semantic layer: turns a metric request into SQL over a dataset's building blocks.

Each metric belongs to the block whose grain defines it (revenue to orders, conversion to sessions).
Metrics from different blocks are aggregated separately and joined on the breakdown, so a query can never
repeat orders once per session. Values from the request become query parameters, never SQL text.
The generated SQL is BigQuery Standard SQL, like the only runner adapter.
"""

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from analyst.semantic.dataset import Block, Dataset

TIME_BREAKDOWNS = {
    "day": "{date}",
    "week": "DATE_TRUNC({date}, WEEK(MONDAY))",
    "month": "FORMAT_DATE('%Y-%m', {date})",
}


class SemanticLayer:
    def __init__(self, dataset: Dataset) -> None:
        self.dataset = dataset
        blocks = {block.name: block for block in dataset.blocks}
        self._metrics = {metric.name: metric for metric in dataset.metrics}
        self._block_of = {metric.name: blocks[metric.block] for metric in dataset.metrics}
        self.query_model = self._query_model()

    def with_clause(self) -> str:
        """Every building block as one WITH clause; BigQuery skips the blocks a query does not use."""
        ctes = [f"{block.name} AS (\n{_indent(block.sql.strip())}\n)" for block in self.dataset.blocks]
        return "WITH\n" + ",\n".join(ctes)

    def compile(self, query: BaseModel) -> tuple[str, dict]:
        """The SQL and its parameters for a validated request."""
        blocks = [block for block in self.dataset.blocks if any(self._block_of[m] is block for m in query.metrics)]
        parts = [self._aggregate(block, query) for block in blocks]
        params: dict = {"start": query.start, "end": query.end, **query.filters}

        if query.by is None:
            combined = "\nCROSS JOIN ".join(f"({part})" for part in parts)
            select = f"SELECT {', '.join(query.metrics)}\nFROM {combined}"
        else:
            combined = f"({parts[0]})" + "".join(f"\nFULL OUTER JOIN ({part}) USING ({query.by})" for part in parts[1:])
            select = f"SELECT {query.by}, {', '.join(query.metrics)}\nFROM {combined}"
            if query.by in TIME_BREAKDOWNS:
                select += f"\nORDER BY {query.by}"
            else:
                select += f"\nORDER BY {query.metrics[0]} DESC NULLS LAST\nLIMIT @limit"
                params["limit"] = query.limit

        return f"{self.with_clause()}\n{select}", params

    def describe(self, query: BaseModel) -> str:
        """A plain-language label, e.g. "Revenue and sessions by device, Dec 1 to Dec 31, 2020"."""
        names = [metric.removesuffix("_pct").replace("_", " ") for metric in query.metrics]
        label = _join_words(names).capitalize()
        if query.by:
            label += f" by {query.by}"
        if query.filters:
            label += f" for {_join_words([value for values in query.filters.values() for value in values])}"
        period = self.dataset.period
        if (query.start, query.end) != (period.start, period.end):
            start = f"{query.start:%b} {query.start.day}"
            if query.start.year != query.end.year:
                start += f", {query.start.year}"
            label += f", {start} to {query.end:%b} {query.end.day}, {query.end.year}"
        return label

    def tool_description(self) -> str:
        metrics = "\n".join(
            f"- {m.name}: {m.description} Breakdowns: {', '.join(self._breakdowns(m.name))}."
            for m in self.dataset.metrics
        )
        dimensions = "\n".join(f"- {d.name}: {d.description}" for d in self.dataset.dimensions)
        return (
            "Compute the dataset's standard metrics without writing SQL. Prefer this over run_sql whenever it "
            "can answer the question: its definitions are verified, so numbers stay consistent. Returns a "
            f"result_id for create_chart, like run_sql.\n\nMetrics:\n{metrics}\n\n"
            f"Breakdowns and filters (day, week and month use each metric's own date):\n{dimensions}\n\n"
            "For shares, growth or anything else these cannot express, use run_sql."
        )

    def _breakdowns(self, metric: str) -> list[str]:
        return [*TIME_BREAKDOWNS, *self._block_of[metric].dimensions]

    def _aggregate(self, block: Block, query: BaseModel) -> str:
        columns = [f"{self._metrics[m].sql} AS {m}" for m in query.metrics if self._block_of[m] is block]
        where = [f"{block.date_column} BETWEEN @start AND @end"]
        where += [f"{block.dimensions[name]} IN UNNEST(@{name})" for name in query.filters]
        group_by = ""
        if query.by is not None:
            columns.insert(0, f"{_breakdown(block, query.by)} AS {query.by}")
            group_by = "\nGROUP BY 1"
        return f"SELECT {', '.join(columns)}\nFROM {block.name}\nWHERE {' AND '.join(where)}{group_by}"

    def _query_model(self) -> type[BaseModel]:
        """The tool's input model, with the dataset's metric and dimension names as its only allowed values."""
        layer, period = self, self.dataset.period
        metric_names = Literal[tuple(m.name for m in self.dataset.metrics)]
        dimension_names = Literal[tuple(d.name for d in self.dataset.dimensions)]
        breakdown_names = Literal[(*TIME_BREAKDOWNS, *(d.name for d in self.dataset.dimensions))]

        class MetricsQuery(BaseModel):
            metrics: list[metric_names] = Field(
                min_length=1, max_length=4, description="Metrics to compute, most important first."
            )
            by: breakdown_names | None = Field(
                None, description="Break the metrics down by time or by a segment. Omit for totals."
            )
            filters: dict[dimension_names, list[str]] = Field(
                default_factory=dict, description='Keep only these values, e.g. {"device": ["mobile"]}.'
            )
            start: date = Field(period.start, description="First day, inclusive.")
            end: date = Field(period.end, description="Last day, inclusive.")
            limit: int = Field(
                25, ge=1, le=500, description="Rows to keep for segment breakdowns, ranked by the first metric."
            )

            @model_validator(mode="after")
            def answerable_by_the_blocks(self) -> Self:
                if not period.start <= self.start <= self.end <= period.end:
                    raise ValueError(
                        f"start must not be after end, and both within the data: "
                        f"{period.start:%Y-%m-%d} to {period.end:%Y-%m-%d}."
                    )
                segments = [name for name in [self.by, *self.filters] if name and name not in TIME_BREAKDOWNS]
                for metric in self.metrics:
                    unsupported = [name for name in segments if name not in layer._block_of[metric].dimensions]
                    if unsupported:
                        raise ValueError(
                            f"{metric} cannot be broken down or filtered by {', '.join(unsupported)}; "
                            "use run_sql with the building blocks instead."
                        )
                return self

        return MetricsQuery


def _breakdown(block: Block, by: str) -> str:
    if by in TIME_BREAKDOWNS:
        return TIME_BREAKDOWNS[by].format(date=block.date_column)
    # Missing values become one labeled group, so the join matches them across blocks.
    return f"IFNULL({block.dimensions[by]}, '(not set)')"


def _join_words(words: list[str]) -> str:
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


def _indent(text: str) -> str:
    return "\n".join(f"  {line}" if line else line for line in text.splitlines())
