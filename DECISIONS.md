# Decision Log

## Clarified with the reviewers

- Frontend frameworks are allowed; I read "implement the UI yourself" as ruling out component and chat UI kits. Vendor sandboxes are allowed but unused (see Cut). The deliverable is a deployed link, so it must be safe on the public internet.

## Assumptions

- **Users are non-technical business stakeholders.** Answers lead with a narrative and a chart; the SQL is still visible if needed.
- **Scope is the public GA4 dataset as-is** (Nov 2020 to Jan 2021). "Last month" is anchored to 2021-01-31; questions outside the window get "the data doesn't cover that".
- **Metric definitions,** found while exploring and encoded once in the dataset definition:
  - **Orders are deduplicated:** some purchases were logged up to 4 times. 4,907 orders and $339,457, against $362,165 counted naively.
  - **Channel means first-visit acquisition:** per-visit source is missing on most events. About 21% of values are obfuscated, and answers say so.
  - **Users are `user_pseudo_id`** (a browser, not a person); **sessions are `user_pseudo_id` + `ga_session_id`**.
  - **Funnels are closed,** so steps only shrink. A third of buyers have no logged funnel events, and answers say so.

## Technical decisions

- **A semantic layer before free SQL.** Standard metrics go through a typed `query_metrics` tool that compiles to SQL, aggregating each grain (orders, sessions, items) before joining, with values as query parameters. `run_sql` is the fallback. This improves consistency, accuracy and performance.
- **Datasets are configuration.** A dataset is one validated YAML file (tables, period, building blocks, metrics, dimensions, notes); the semantic layer and the prompt's dataset section are generated from it. **TheLook**, a second dataset, needed only a YAML file, matched independent totals exactly and passed its eval 8/8. New sources are easily integrated, and UI switches between them (demonstration purposes).
- **Charts use stored query results:** the model picks a result and columns, the server attaches the rows, so the LLM never does the math itself, which is error-prone.
- **Ports and adapters, one composition root.** The core depends only on interfaces for the LLM, SQL runner and store, wired in `bootstrap.py`. The loop is tested with a scripted fake model; saved chats in a db would be one new store class.
- **Tests at three levels, plus an eval.** Pure logic (SQL guard, semantic compiler, UI reducer) has unit tests, and the semantic layer's run on a made-up dataset. The agent loop is tested with a scripted fake model, so self-correction, step limits and errors are checked for free. Each dataset's numbers are checked against independent BigQuery queries. The eval asks real questions to the real model and checks the numbers in the answers against values computed separately (GA4 11/11, TheLook 8/8). It caught bugs manual testing missed and informed the model choice.
- **Python + FastAPI, synchronous, over SSE.** The Anthropic and BigQuery calls block, which would freeze `async` code. SSE fits one streamed answer per question over plain HTTP.
- **Vue 3 + TypeScript,** hand-written: the framework I know best, for the live extension.
- **Claude Sonnet 5:** fewer query retries than Haiku 4.5 (1 vs 4) and richer analysis, at about $0.03 per question.

## Cut or deprioritized

- **No Python execution:** a second analysis path to build and secure. No significance tests or forecasting.
- **Chats live in memory,** so an idle chat is lost when Cloud Run scales to zero. I only created a memory store interface to allow for possible future implementations of chat history easily.
- **UI polish and features:** Stop, retry, etc.

## Where I got stuck

- **The first test gave confident wrong numbers:** $1.45M revenue instead of $339,457, from joining visits to orders row by row. Prompt rules fixed it, and the semantic layer now makes that join impossible for standard metrics.
- **An eval caught a bug manual testing missed:** narrowing a building block's dates leaked duplicate orders across months (December $158,726 instead of $158,166). Eval went from 7/10 and 8/10 to 10/10.

## With another 40 hours

- Saved conversations with a history sidebar, which also lifts the single-instance limit.
- Dataset onboarding: an agent drafts the YAML from the schema, a person reviews it, the app verifies totals.
- Statistics and forecasting through a code sandbox.
- Asynchronous conversations (multiple chats running at once).
- Model selection.
- Agent profiles (e.g.: Data Analyst, Sales Rep helper, etc.)
