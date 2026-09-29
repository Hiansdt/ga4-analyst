"""Follow-up tool: next questions the user can ask with one click."""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from analyst.core.registry import Tool, ToolOutput, TurnContext


class SuggestFollowUpsInput(BaseModel):
    questions: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]] = Field(
        min_length=2,
        max_length=3,
        description=(
            "Written as the user would ask them, e.g. 'Break down cart drop-off by device'. "
            "Never 'Would you like me to...?'. Each must be answerable with this data."
        ),
    )


# TODO(prompt-tuning): Make the model offer follow-ups on every answer, through the tool only
# WHY: in the TheLook eval Sonnet skipped the tool on 3 of 8 answers and once wrote "Let me know if..." in prose instead
# DONE-WHEN: python -m evals.run --model claude-sonnet-5 --dataset thelook (and ga4) shows follow "yes" for every case except outside_date_range
def suggest_follow_ups_tool() -> Tool:
    def handler(args: SuggestFollowUpsInput, ctx: TurnContext) -> ToolOutput:
        return ToolOutput(content="Suggestions shown to the user.", display={"questions": args.questions})

    return Tool(
        name="suggest_follow_ups",
        description=(
            "Offer the user 2 or 3 next questions as buttons; a click sends the question as their next message. "
            "Call it once per answer, before writing the final answer, together with create_chart when you "
            "make a chart."
        ),
        input_model=SuggestFollowUpsInput,
        handler=handler,
    )
