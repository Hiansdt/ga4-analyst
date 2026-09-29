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
6. Claude streams its written answer. Every step reaches the browser as a typed event: `text_delta`, `tool_started`, `tool_finished` (with the SQL, rows or chart), `turn_failed`, `turn_completed`.

## Running it

Needs Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 24, and a Google Cloud project. BigQuery access uses Application Default Credentials, so there are no key files:

```
gcloud auth application-default login --impersonate-service-account ga4-agent-runtime@<project>.iam.gserviceaccount.com
cp .env.example .env   # then fill in ANTHROPIC_API_KEY and GCP_PROJECT_ID
```

Development, with the API and the Vite dev server in two terminals:

```
cd backend && uv run --env-file ../.env uvicorn analyst.bootstrap:build_app --factory --port 8000
cd web && npm install && npm run dev      # API_URL=http://localhost:<port> if the API is not on 8000
```

Two datasets are defined in `backend/src/analyst/datasets/`, and the app serves both (`DATASETS=ga4,thelook`, the first is the default). The UI switches between them; each chat belongs to one dataset, and `?dataset=thelook` opens a link on that one:

- `ga4`: the GA4 export of the Google Merchandise Store, the dataset the task specifies.
- `thelook`: TheLook, a synthetic clothing store with orders, products, customers and web events in plain tables. Google regenerates the public copy daily, so the definition reads a snapshot in the project's own `thelook_snapshot` dataset, which keeps its verified totals stable. The runtime service account needs BigQuery Data Viewer on that dataset, and a fork needs its own snapshot: the definition names this project's copy.

Adding a dataset means a YAML definition, a test that checks its totals against independent queries, and eval cases (`evals/cases/`); no code changes.

A terminal client is also available: `cd backend && uv run --env-file ../.env analyst`.

## Deploying

The `Dockerfile` builds the frontend and serves it from the same FastAPI process, so the app is one Cloud Run service. `deploy/cloudrun.sh` builds the image with Cloud Build and deploys it:

- The service runs as `ga4-agent-runtime`, whose only role is BigQuery Job User. The container has no credentials of its own.
- The image is built by `ga4-agent-builder`, which only has the Cloud Run builder role.
- The Anthropic key is read from Secret Manager (`anthropic-api-key`), never baked into the image. `.dockerignore` and `.gcloudignore` keep `.env` out of both the image and the upload.
- It scales to zero when idle and to at most one instance, which caps cost. Conversations are kept in memory, so an idle chat is gone once the instance stops.

```
gcloud services enable secretmanager.googleapis.com
(set -a; . ./.env; printf %s "$ANTHROPIC_API_KEY" | gcloud secrets create anthropic-api-key --data-file=-)
deploy/cloudrun.sh
```

## Architecture

```
            ┌──────────────── agent core ────────────────┐
 FastAPI ──►│ agent loop                                 │──► LLM port    ◄── Anthropic adapter  | scripted fake (tests)
 CLI     ──►│ tool registry (query_metrics, run_sql...)  │──► SQL port    ◄── BigQuery adapter   | fake runner (tests)
            │ system prompt                              │──► Store port  ◄── in-memory store    | database store (future)
            └────────────────────────────────────────────┘
```

Code layout (`backend/src/analyst/`), one folder per layer:

```
bootstrap.py  config.py  cli.py   composition root, settings, terminal client
core/       the agent: loop, events, prompt, tool registry, SQL guard. No vendor imports.
ports/      interfaces the core depends on: LLM, SQL runner, conversation store
adapters/   their implementations: Anthropic, BigQuery, in-memory store
tools/      what the model can call: queries, charts, follow-up suggestions
semantic/   the semantic layer: dataset definition model, metric compiler, prompt context
datasets/   one YAML definition per dataset (ga4.yaml): tables, building blocks, metrics, notes
api/        HTTP layer: endpoints, SSE, rate limit
```

- **Ports and adapters.** The agent core depends only on small interfaces. Anthropic, BigQuery and conversation storage are adapters, created in one place (the composition root, `bootstrap.py`, shared by the server and the terminal CLI) and passed in. The loop is tested with fakes, and storage can be swapped without touching the agent.
- **Events as the contract.** The agent yields typed events. The SSE endpoint, the CLI and the tests are all consumers of the same stream, and the frontend mirrors the event types in TypeScript.
- **Chat-shaped API.** Conversations are owned by the server behind a `ConversationStore` interface, so persisted chat history is a new store class, not a new contract.

## Design principles

- **One reason to change per module.** Metric definitions change only `datasets/ga4.yaml`, analyst behavior only `core/prompt.py`, SQL safety rules only `core/sql_guard.py`, the HTTP contract only `api/app.py`.
- **Open for extension.** Tools are registered as `{name, input schema, handler}`; adding one does not change the loop.
- **Functional core, imperative shell.** Decisions such as the SQL guard and the frontend event reducer are pure functions, unit tested without I/O.
- **Defense in depth.** The service account can only run queries (no data access beyond the public dataset). Queries must dry-run as a single `SELECT` over the allowlisted dataset. Jobs run with `maximum_bytes_billed`, results are row-capped, the loop has a step limit, and the public endpoint is rate limited.
- **Single source of truth.** Chart data comes from query results, never from numbers the model writes. Metric definitions (deduplicated orders, sessions, channel) live in one set of SQL building blocks that every query reuses.
- **Errors as data for the model, exceptions for the system.** Tool failures return to Claude so it can recover. Infrastructure failures surface to the user as an error event.
- **Validation at the edges.** Pydantic validates HTTP input and tool input; the core works with typed data.
- **Datasets are configuration.** Everything dataset-specific (tables, building blocks, metrics, dimensions, notes, example questions) is one YAML file in `datasets/`, validated when loaded. The loop, tools, semantic layer and prompt are dataset-agnostic, and `DATASET=<name>` picks the definition. The semantic layer's tests run on a made-up dataset, so nothing in it depends on GA4.
- **Abstractions only where a second implementation exists.** Interfaces exist for the LLM, the SQL runner and the store because tests and planned persistence need them. Everything else is plain functions: no DI container, no class hierarchies.

## Testing

- **Unit tests:** the SQL guard, the tool registry and the frontend event reducer.
- **Loop tests:** driven by a scripted fake LLM. They cover self-correction after a failed query, the step limit and error handling, deterministically and at no API cost.
- **Eval** (`backend/evals/`): 10 business questions run against the real agent, Claude and BigQuery. Each answer is checked against values computed independently of the agent: exact figures, percentages at most 100%, no dollar amount above full-period revenue. Most expected answers are deliberately absent from the system prompt. It prints pass/fail, query retries, latency and cost per question:

  ```
  cd backend
  uv run --env-file ../.env python -m evals.run --model claude-haiku-4-5 --model claude-sonnet-5 [--dataset thelook]
  ```
- **Integration tests** (opt-in): `pytest -m bigquery` checks the SQL building blocks against verified totals and the BigQuery adapter; `pytest -m llm` round-trips a tool conversation through the real API.
