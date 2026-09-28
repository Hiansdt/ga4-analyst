"""API failures must not leak account or request details to the public UI."""

import logging
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from ga4_agent.adapters.anthropic import AnthropicModel
from ga4_agent.llm import ModelError


def failing_client(error: Exception) -> SimpleNamespace:
    def stream(**_):
        raise error

    return SimpleNamespace(messages=SimpleNamespace(stream=stream))


def test_api_errors_reach_users_as_a_generic_message_and_the_logs_in_full(caplog):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.RateLimitError(
        "Your organization has hit its monthly spend limit of $20",
        response=httpx2.Response(429, request=request),
        body=None,
    )
    model = AnthropicModel(failing_client(error), model="m", max_tokens=10, effort=None)

    with caplog.at_level(logging.ERROR), pytest.raises(ModelError) as raised:
        list(model.stream_turn(system="s", tools=[], messages=[], allow_tools=True))

    assert str(raised.value) == "The AI service is unavailable. Please try again."
    assert "monthly spend limit of $20" in caplog.text
