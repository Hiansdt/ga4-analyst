# Decision Log

## Clarified with the reviewers

- **Frontend frameworks are allowed** (React was confirmed fine). I read "implement the UI yourself" as still ruling out component and chat UI kits.
- **Vendor-hosted sandboxes are allowed.** I still don't use one (see Cut).
- **The deliverable is a deployed link,** so the app must be safe to leave open on the public internet.

## Assumptions

- **The user is a non-technical business stakeholder.** Answers start with a plain-language narrative and a chart. SQL is available but collapsed, so it builds trust without getting in the way.
- **Scope is the public dataset as-is.** That means `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`, 2020-11-01 to 2021-01-31. For questions outside that window, the agent says the data doesn't cover it instead of extrapolating.

## Metric definitions

Found while exploring the data. They are baked into the system prompt so every answer uses the same definitions.

- **Orders are deduplicated.** Some purchases were logged more than once: transaction `119233` ($177) appears 4 times. Of 906 purchase events with no `transaction_id`, 450 also have no revenue.
  - **Rule:** each transaction ID counts once (its earliest event); ID-less purchases count only if they have revenue.
  - **Result:** 4,907 orders and $339,457, against 5,692 events and $362,165 counted naively (about 7% overstated).
  - 15 IDs carry different amounts across their duplicates; the earliest event wins.
- **Channel means first-visit acquisition.** Per-visit source is missing on most events, and on every `session_start`, so only `traffic_source.*` (how the user first arrived) is reliable. Answers label it "acquisition channel (first visit)". About 21% of those values are obfuscated (`<Other>`, `(data deleted)`), and answers mention that.
- **Users and sessions.**
  - Users = `user_pseudo_id`, since `user_id` is always empty.
  - Sessions = distinct `user_pseudo_id` + `ga_session_id` (360,129). Counting `session_start` events undercounts (354,970).
- **"Now" is the end of the dataset.** Relative dates such as "last month" are anchored to 2021-01-31, and the answer says so.

## Technical decisions

- **Python + FastAPI backend.** The server is a thin layer: a few endpoints that stream agent steps over SSE, with request validation from Pydantic. The agent logic lives in plain modules that don't depend on the framework.
- **Synchronous backend, no `async`.** The agent loop is a plain generator that yields step events, and FastAPI streams it from a worker thread. The Anthropic and BigQuery calls block, and a blocking call inside `async def` would freeze every request on the server. Writing everything sync removes that risk and keeps the loop easy to read and test. The thread pool handles far more concurrent chats than this app will see.
- **The server owns conversations, behind a `ConversationStore` interface.** The API is shaped like a chat product (create a conversation, post a message, reload a conversation), so adding saved chat history later means one new store class and no contract change. The current implementation is in-memory, so Cloud Run runs a single always-on instance. A database-backed store is the first item under "40 hours".
- **Charts are built from stored query results, not from numbers the model writes.** The model picks a result, a chart type and columns; the server attaches the rows. Every number on a chart comes straight from BigQuery. Rendering uses Apache ECharts, which has a native funnel chart.
- **Vue 3 + Vite + TypeScript frontend,** with hand-written components and no UI kit. Vue is the framework I know best, which matters for the live extension.
- **Claude Sonnet 5 for answers.** Correct SQL over GA4's nested schema matters more than per-query cost, so answers use a strong model. A cheaper model (Haiku) is used only while building the plumbing. The model is set by `ANTHROPIC_MODEL`.
- **No service-account keys.** Locally, the app uses ADC with service-account impersonation. On Cloud Run, the service account is attached to the service. Either way no credential file can leak, and the app always runs as a least-privilege account that has only BigQuery Job User.
- **Canonical SQL building blocks in the prompt, not derived tables.** The prompt ships reusable CTEs (orders, sessions, purchased items, param extraction) that the model must reuse verbatim. Otherwise "total revenue" in one turn and "revenue by country" in a later turn could be computed differently and not add up. Materialized tables would need setup scripts, extra IAM and objects that can expire, for the same consistency.
- **SQL is the only analysis tool.** It covers descriptive and diagnostic questions on this dataset and is simple to guard (read-only, SELECT-only, byte cap).

## Cut or deprioritized

- **No Python execution (pandas/stats sandbox).** A vendor sandbox would be allowed, but moving query results into it and handling its outputs adds a second analysis path to build and test. Given the time-box, I chose a smaller scope done well. That rules out statistical tests and forecasting.

## Where I got stuck

_Filled in during the build._

## With another 40 hours

- Statistical analysis (significance tests, forecasting) through a vendor code-execution sandbox fed with query results.
- Persistent conversations (Firestore or Postgres store) with a history sidebar. It also lifts the single-instance limit on Cloud Run.
- A curated data layer: deduplicated `orders` and `sessions` tables built on a schedule. SQL gets simpler and cheaper, and metric definitions live in one place instead of in the prompt.
