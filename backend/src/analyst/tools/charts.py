"""Chart tool: draws a stored query result, so every number on a chart comes from the query."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from analyst.core.registry import Tool, ToolOutput, TurnContext, tool_error

NUMERIC_TYPES = {"INTEGER", "INT64", "FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"}


class CreateChartInput(BaseModel):
    result_id: str = Field(description="A result_id returned by a query earlier in this answer.")
    type: Literal["line", "bar", "funnel", "pie"] = Field(
        description="line for trends over time, bar to compare categories, funnel for step drop-off, pie for shares."
    )
    title: str = Field(description="Short title in plain business language.")
    x: str = Field(description="Column with the labels: dates, categories or funnel steps, one row each.")
    y: list[str] = Field(
        min_length=1, max_length=3, description="Numeric columns to plot; exactly one for funnel and pie."
    )

    @model_validator(mode="after")
    def single_series_for_funnel_and_pie(self) -> Self:
        if self.type in ("funnel", "pie") and len(self.y) != 1:
            raise ValueError(f"a {self.type} chart takes exactly one y column")
        return self


def create_chart_tool() -> Tool:
    def handler(args: CreateChartInput, ctx: TurnContext) -> ToolOutput:
        result = ctx.results.get(args.result_id)
        if result is None:
            return tool_error(f"Unknown result_id {args.result_id!r}; available: {', '.join(ctx.results) or 'none'}.")

        types = {c.name: c.type for c in result.columns}
        missing = [name for name in [args.x, *args.y] if name not in types]
        if missing:
            return tool_error(f"Unknown columns {missing}; the result has {list(types)}.")
        not_numeric = [name for name in args.y if types[name] not in NUMERIC_TYPES]
        if not_numeric:
            return tool_error(f"y columns must be numeric; {not_numeric} are not.")

        # The rows come from the stored result, so every number on the chart comes from the query.
        rows = [{name: row[name] for name in [args.x, *args.y]} for row in result.rows]
        display = {"type": args.type, "title": args.title, "x": args.x, "y": args.y, "rows": rows}
        return ToolOutput(content=f"Chart shown to the user with {len(rows)} data points.", display=display)

    return Tool(
        name="create_chart",
        description=(
            "Show the user a chart of a query result from this answer. The chart uses the full stored "
            "result, not the preview. Shape the query so each row is one point, bar, slice or funnel step."
        ),
        input_model=CreateChartInput,
        handler=handler,
    )
