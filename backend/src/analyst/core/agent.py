"""The agentic loop: call the model, run the tools it asks for, repeat until it answers."""

from collections.abc import Generator, Iterator

from analyst.core.events import Event, TextDelta, ToolFinished, ToolStarted, TurnCompleted, TurnFailed
from analyst.core.registry import ToolRegistry, TurnContext
from analyst.ports.llm import ModelClient, ModelError, ModelTurn, Usage


class Agent:
    def __init__(self, *, model: ModelClient, tools: ToolRegistry, system_prompt: str, max_steps: int) -> None:
        self._model = model
        self._tools = tools
        self._system_prompt = system_prompt
        self._max_steps = max_steps

    def run_turn(self, history: list[dict], user_message: str) -> Iterator[Event]:
        """Answer one user message. The last event is always TurnCompleted with the new messages.

        History is append-only: messages are added verbatim (thinking blocks included) and never edited.
        """
        new_messages: list[dict] = [{"role": "user", "content": user_message}]
        ctx = TurnContext()
        usage = Usage()

        for step in range(self._max_steps):
            # On the last step the model must answer with what it has instead of calling more tools.
            allow_tools = step < self._max_steps - 1
            try:
                turn = yield from self._stream_model(history + new_messages, allow_tools)
            except ModelError as error:
                yield TurnFailed(str(error))
                break
            usage += turn.usage

            if turn.stop_reason == "end_turn":
                # An empty reply (possible after a tool result) would make every later request invalid.
                if turn.content:
                    new_messages.append({"role": "assistant", "content": turn.content})
                break
            if turn.stop_reason != "tool_use":
                # max_tokens, refusal...: the reply may hold a truncated tool call, so it is not kept.
                yield TurnFailed(f"The model stopped unexpectedly ({turn.stop_reason}).")
                break

            new_messages.append({"role": "assistant", "content": turn.content})
            results = yield from self._run_tools(turn, ctx)
            new_messages.append({"role": "user", "content": results})
        else:
            yield TurnFailed(f"No answer after {self._max_steps} steps.")

        yield TurnCompleted(new_messages, usage)

    def _stream_model(self, messages: list[dict], allow_tools: bool) -> Generator[Event, None, ModelTurn]:
        turn: ModelTurn | None = None
        for item in self._model.stream_turn(
            system=self._system_prompt,
            tools=self._tools.definitions(),
            messages=messages,
            allow_tools=allow_tools,
        ):
            if isinstance(item, ModelTurn):
                turn = item
            else:
                yield TextDelta(item)
        if turn is None:
            raise ModelError("The model stream ended without a final message.")
        return turn

    def _run_tools(self, turn: ModelTurn, ctx: TurnContext) -> Generator[Event, None, list[dict]]:
        results = []
        for block in turn.content:
            if block["type"] != "tool_use":
                continue
            yield ToolStarted(block["id"], block["name"], block["input"])
            output = self._tools.run(block["name"], block["input"], ctx)
            yield ToolFinished(block["id"], block["name"], output.is_error, output.display)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": output.content,
                    "is_error": output.is_error,
                }
            )
        return results
