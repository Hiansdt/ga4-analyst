"""Anthropic adapter for the LLM port: one streamed Messages API call per model turn."""

from collections.abc import Iterator

import anthropic

from ga4_agent.llm import ModelError, ModelTurn


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
            # TODO(security-hardening): Log the API error server-side and give users a generic message
            # WHY: error.message reaches the public UI via TurnFailed and can expose account limits or request details
            # DONE-WHEN: a test forcing anthropic.APIStatusError gets ModelError("The AI service is unavailable. Please try again.") and the raw message only appears in the logs
            raise ModelError(f"The AI service request failed: {error.message}") from error

        yield ModelTurn(
            content=[block.model_dump(mode="json", exclude_none=True) for block in message.content],
            stop_reason=message.stop_reason,
        )
