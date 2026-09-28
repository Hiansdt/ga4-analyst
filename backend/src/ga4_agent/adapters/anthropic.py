"""Anthropic adapter for the LLM port: one streamed Messages API call per model turn."""

import logging
from collections.abc import Iterator

import anthropic

from ga4_agent.llm import ModelError, ModelTurn, Usage

logger = logging.getLogger(__name__)


class AnthropicModel:
    def __init__(self, client: anthropic.Anthropic, *, model: str, max_tokens: int, effort: str | None) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort  # None leaves the model default; some models (Haiku 4.5) reject the parameter

    def stream_turn(
        self, *, system: str, tools: list[dict], messages: list[dict], allow_tools: bool
    ) -> Iterator[str | ModelTurn]:
        params: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system,
            "tools": tools,
            "messages": messages,
            # The system prompt and tools are static, so every step after the first reads them from cache.
            "cache_control": {"type": "ephemeral"},
        }
        if not allow_tools:
            params["tool_choice"] = {"type": "none"}
        if self._effort:
            params["output_config"] = {"effort": self._effort}

        try:
            with self._client.messages.stream(**params) as stream:
                for event in stream:
                    if event.type == "text":
                        yield event.text
                message = stream.get_final_message()
        except anthropic.APIError as error:
            # The message can reveal account limits or request details, so it goes to the logs, not to users.
            logger.error("Anthropic API request failed: %s", error.message)
            raise ModelError("The AI service is unavailable. Please try again.") from error

        yield ModelTurn(
            content=[block.model_dump(mode="json", exclude_none=True) for block in message.content],
            stop_reason=message.stop_reason,
            usage=Usage(
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
                cache_read_input_tokens=message.usage.cache_read_input_tokens or 0,
                cache_creation_input_tokens=message.usage.cache_creation_input_tokens or 0,
            ),
        )
