# GA4 Analyst

A chat app for asking business questions about the [GA4 ecommerce demo dataset](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset) (the Google Merchandise Store, Nov 2020 to Jan 2021). Each answer comes back as a written narrative with charts, and follow-up questions keep the context of the conversation.

The agent loop is hand-written on the Anthropic Messages API, with no agent framework. The UI is hand-written Vue, with no component kit.

Assumptions, trade-offs and cuts are in [DECISIONS.md](DECISIONS.md).

## How a question is answered

Example: *"Which device converts best?"*

1. The browser posts the question to `POST /api/conversations/{id}/messages` and keeps the response open as a Server-Sent Events stream.
2. The agent sends Claude the conversation, the system prompt (dataset notes, metric definitions, reusable SQL building blocks) and the tool definitions.
3. Claude calls `run_sql`. The query is validated with a BigQuery dry run, then executed with a byte cap. The full rows are stored server-side, and Claude receives a preview.
4. If the query fails, the error goes back to Claude, which fixes the query and tries again.
5. Claude calls `create_chart` with a stored result id, a chart type and column names. The server attaches the stored rows, so every number on a chart comes straight from BigQuery.
6. Claude streams its written answer. Every step reaches the browser as a typed event: `tool_started`, `sql_result`, `chart`, `text_delta`, `done`.

## Architecture

```
            ┌──────────────── agent core ────────────────┐
 FastAPI ──►│ agent loop                                 │──► LLM port    ◄── Anthropic adapter  | scripted fake (tests)
 CLI     ──►│ tool registry (run_sql, create_chart)      │──► SQL port    ◄── BigQuery adapter   | fake runner (tests)
            │ system prompt                              │──► Store port  ◄── in-memory store    | database store (future)
            └────────────────────────────────────────────┘
```

- **Ports and adapters.** The agent core depends only on small interfaces. Anthropic, BigQuery and conversation storage are adapters, created in one place (the composition root, `bootstrap.py`, shared by the server and the terminal CLI) and passed in. The loop is tested with fakes, and storage can be swapped without touching the agent.
- **Events as the contract.** The agent yields typed events. The SSE endpoint, the CLI and the tests are all consumers of the same stream, and the frontend mirrors the event types in TypeScript.
- **Chat-shaped API.** Conversations are owned by the server behind a `ConversationStore` interface, so persisted chat history is a new store class, not a new contract.

## Design principles

- **One reason to change per module.** Metric definitions change only `datasets/ga4.py`, analyst behavior only `prompt.py`, SQL safety rules only `sql.py`, the HTTP contract only `api.py`.
- **Open for extension.** Tools are registered as `{name, input schema, handler}`; adding one does not change the loop.
- **Functional core, imperative shell.** Decisions such as the SQL guard and the frontend event reducer are pure functions, unit tested without I/O.
- **Defense in depth.** The service account can only run queries (no data access beyond the public dataset). Queries must dry-run as a single `SELECT` over the allowlisted dataset. Jobs run with `maximum_bytes_billed`, results are row-capped, the loop has a step limit, and the public endpoint is rate limited.
- **Single source of truth.** Chart data comes from query results, never from numbers the model writes. Metric definitions (deduplicated orders, sessions, channel) live in one set of SQL building blocks that every query reuses.
- **Errors as data for the model, exceptions for the system.** Tool failures return to Claude so it can recover. Infrastructure failures surface to the user as an error event.
- **Validation at the edges.** Pydantic validates HTTP input and tool input; the core works with typed data.
- **Dataset knowledge is separate from analyst behavior.** `prompt.py` is dataset-agnostic; everything GA4- or BigQuery-specific lives in `datasets/ga4.py` and the BigQuery adapter. There is no dataset interface yet: with one dataset it would be speculative.
- **Abstractions only where a second implementation exists.** Interfaces exist for the LLM, the SQL runner and the store because tests and planned persistence need them. Everything else is plain functions: no DI container, no class hierarchies.

## Testing

- **Unit tests:** the SQL guard, the tool registry and the frontend event reducer.
- **Loop tests:** driven by a scripted fake LLM. They cover self-correction after a failed query, the step limit and error handling, deterministically and at no API cost.
- **Eval** (`backend/evals/`): 10 business questions run against the real agent, Claude and BigQuery. Each answer is checked against values computed independently of the agent: exact figures, percentages at most 100%, no dollar amount above full-period revenue. Most expected answers are deliberately absent from the system prompt. It prints pass/fail, query retries, latency and cost per question:

  ```
  cd backend
  uv run --env-file ../.env python -m evals.run --model claude-haiku-4-5 --model claude-sonnet-5
  ```
- **Integration tests** (opt-in): `pytest -m bigquery` checks the SQL building blocks against verified totals and the BigQuery adapter; `pytest -m llm` round-trips a tool conversation through the real API.
