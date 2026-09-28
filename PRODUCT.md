# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary persona:** a non-technical business user at the Google Merchandise Store, such as a marketing or operations manager. They ask plain-language questions about the store's performance ("How are we doing?", "Where do customers drop off?") and need answers they can trust and act on, without writing SQL.
- **First real visitors:** the hiring company's technical reviewers. They use the app as the persona would, then probe it: they inspect the generated SQL, check numbers, ask follow-ups and edge cases, and try to break it. Design for the persona first, with transparency that holds up to their scrutiny.

## Product Purpose

GA4 Analyst is a conversational data analyst over the public GA4 ecommerce demo dataset in BigQuery. Each question gets a written narrative, charts where they help, and the exact queries behind the numbers. Follow-up questions keep the context of the conversation. Success means answers that are correct, clearly explained, and verifiable.

## Positioning

The agent loop is hand-written, and every number is traceable: charts are drawn from stored query results rather than figures the model types, metric definitions are fixed SQL building blocks, and an eval with independently computed answers checks correctness.

## Operating Context

- Used in a desktop browser, as a single chat session, often for a few minutes at a time.
- A take-home technical assessment: the code is reviewed closely and extended live during a 30 to 45 minute call.
- Deployed as a public link on Cloud Run that scales to zero; a chat left idle for about 15 minutes is lost.

## Capabilities and Constraints

- The data covers 2020-11-01 to 2021-01-31 only. "Today" is 2021-01-31, and questions outside that range are answered as not covered.
- Part of the dataset is obfuscated by Google (`<Other>`, `(data deleted)`, `(not set)`).
- Analysis is SQL only (no Python execution). Charts: line, bar, funnel, pie.
- Task rule: the UI is implemented by hand. Frontend frameworks are allowed; component or chat UI kits are not. Visualization libraries are allowed.
- Visual polish is not the primary evaluation criterion; functionality and thoughtful implementation are.
- Each question costs about $0.03 in model usage.

## Brand Commitments

- Name: GA4 Analyst. No logo or other brand assets.
- Voice: plain, clear business language; terms like "conversion rate" are explained briefly.

## Evidence on Hand

- The public dataset and the verified figures in `DECISIONS.md` (for example $339,457 revenue from 4,907 deduplicated orders).
- The eval in `backend/evals/`: 11 questions with independently computed answers.
- No testimonials, customers or usage data exist; none may be invented.

## Product Principles

- **Correct before impressive.** A wrong number costs more trust than a missing chart.
- **Show the work.** Every answer can be traced to the queries that produced it.
- **Plain language first.** Lead with the answer a manager needs; technical detail stays one click away.
- **Honest about the data's limits.** Coverage gaps, obfuscated values and tracking gaps are stated, not hidden.

## Accessibility & Inclusion

WCAG 2.2 AA baseline: full keyboard use, sufficient contrast, screen-reader labels, and reduced-motion support. No specific user needs are known.
