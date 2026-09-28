"""Round trip through the real Messages API: stored history must be accepted when sent back."""

import os

import anthropic
import pytest
from fakes import FakeRunner, daily_result

from ga4_agent.adapters.anthropic import AnthropicModel
from ga4_agent.agent import Agent
from ga4_agent.events import TextDelta, ToolFinished, TurnCompleted
from ga4_agent.tools import ToolRegistry, run_sql_tool

pytestmark = pytest.mark.llm


def test_tool_loop_history_round_trips_through_the_api():
    model = AnthropicModel(
        anthropic.Anthropic(),
        model=os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5"),
        max_tokens=2000,
        effort=None,
    )
    tools = ToolRegistry([run_sql_tool(FakeRunner(daily_result(3)), preview_rows=10)])
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt="Use run_sql to answer. Any SELECT works; the tool returns daily event counts.",
        max_steps=4,
    )

    first = list(agent.run_turn([], "How many events were there per day? Be brief."))
    history = first[-1].messages
    second = list(agent.run_turn(history, "Which day had the most? One sentence."))

    assert any(isinstance(e, ToolFinished) for e in first)
    assert any(isinstance(e, TextDelta) for e in second)
    assert isinstance(second[-1], TurnCompleted)
    assert second[-1].messages[-1]["role"] == "assistant"
