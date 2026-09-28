# Decision Log

## Clarified with the reviewers

- **Frontend frameworks are allowed** (React was confirmed fine). I read "implement the UI yourself" as still ruling out component and chat UI kits.
- **Vendor-hosted sandboxes are allowed.** I still don't use one (see Cut).
- **The deliverable is a deployed link,** so the app must be safe to leave open on the public internet.

## Assumptions

- **The user is a non-technical business stakeholder.** Answers start with a plain-language narrative and a chart. SQL is available but collapsed, so it builds trust without getting in the way.
- **Scope is the public dataset as-is.** That means `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`, 2020-11-01 to 2021-01-31. For questions outside that window, the agent says the data doesn't cover it instead of extrapolating.

## Technical decisions

- **Python + FastAPI backend, not Django.** The app needs only a few endpoints, SSE streaming of agent steps, and long-running LLM and BigQuery calls. Django's ORM, admin, auth and templates would go unused, and its streaming support is awkward.
- **Synchronous backend, no `async`.** The agent loop is a plain generator that yields step events, and FastAPI streams it from a worker thread. The Anthropic and BigQuery calls block, and a blocking call inside `async def` would freeze every request on the server. Writing everything sync removes that risk and keeps the loop easy to read and test. The thread pool handles far more concurrent chats than this app will see.
- **Vue 3 + Vite + TypeScript frontend,** with hand-written components and no UI kit. Vue is the framework I know best, which matters for the live extension.
- **Sonnet 5 as the default model; Haiku only during development.** The model is set by `ANTHROPIC_MODEL`. Answer quality depends on correct SQL over GA4's nested schema. Haiku's cost savings (~$4 across all testing) weren't worth the extra risk of wrong numbers.
- **No service-account keys.** Locally, the app uses ADC with service-account impersonation. On Cloud Run, the service account is attached to the service. Either way no credential file can leak, and the app always runs as a least-privilege account that has only BigQuery Job User.
- **SQL is the only analysis tool.** It covers descriptive and diagnostic questions on this dataset and is simple to guard (read-only, SELECT-only, byte cap).

## Cut or deprioritized

- **No Python execution (pandas/stats sandbox).** A vendor sandbox would be allowed, but moving query results into it and handling its outputs adds a second analysis path to build and test. Given the time-box, I chose a smaller scope done well. That rules out statistical tests and forecasting.

## Where I got stuck

_Filled in during the build._

## With another 40 hours

- Statistical analysis (significance tests, forecasting) through a vendor code-execution sandbox fed with query results.
