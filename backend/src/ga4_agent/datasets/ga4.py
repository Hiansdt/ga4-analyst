"""Knowledge about the GA4 ecommerce demo dataset: dialect, tables, metric definitions.

Everything BigQuery- or GA4-specific that the model needs lives here. The text is static
so the system prompt can be cached across turns and conversations.
"""

from datetime import date

DATASET = "bigquery-public-data.ga4_obfuscated_sample_ecommerce"
DATASET_START = date(2020, 11, 1)
DATASET_END = date(2021, 1, 31)

# Canonical CTEs. They encode the metric definitions (deduplicated orders, sessions),
# so every query reuses them instead of re-deriving the metrics. Verified against
# independently computed totals in tests/test_ga4_building_blocks.py.
# session_key is derived inside `sessions` only: BigQuery skips unused plain columns
# but still bills an unused expression over event_params (~1 GB per query).
BUILDING_BLOCKS = f"""\
events AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    TIMESTAMP_MICROS(event_timestamp) AS event_ts,
    event_name,
    user_pseudo_id,
    device.category AS device_category,
    geo.country AS country,
    traffic_source.source AS acquisition_source,
    traffic_source.medium AS acquisition_medium,
    NULLIF(ecommerce.transaction_id, '(not set)') AS transaction_id,
    ecommerce.purchase_revenue AS purchase_revenue,
    items,
    event_params
  FROM `{DATASET}.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '{DATASET_START:%Y%m%d}' AND '{DATASET_END:%Y%m%d}'
),
sessions AS (
  SELECT
    session_key,
    ANY_VALUE(user_pseudo_id) AS user_pseudo_id,
    MIN(event_date) AS session_date,
    ANY_VALUE(device_category) AS device_category,
    ANY_VALUE(country) AS country,
    ANY_VALUE(acquisition_source) AS acquisition_source,
    ANY_VALUE(acquisition_medium) AS acquisition_medium,
    LOGICAL_OR(event_name = 'purchase') AS converted
  FROM (
    SELECT
      *,
      CONCAT(user_pseudo_id, '.', CAST((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING)) AS session_key
    FROM events
  )
  GROUP BY session_key
),
orders AS (
  SELECT
    COALESCE(transaction_id, CONCAT('untracked.', user_pseudo_id, '.', CAST(event_ts AS STRING))) AS order_id,
    event_date AS order_date,
    event_ts,
    user_pseudo_id,
    device_category,
    country,
    acquisition_source,
    acquisition_medium,
    purchase_revenue AS revenue,
    items
  FROM events
  WHERE event_name = 'purchase'
    AND (transaction_id IS NOT NULL OR purchase_revenue IS NOT NULL)
  QUALIFY transaction_id IS NULL
    OR ROW_NUMBER() OVER (PARTITION BY transaction_id ORDER BY event_ts) = 1
),
order_items AS (
  SELECT
    o.order_id,
    o.order_date,
    i.item_name,
    i.item_category,
    i.quantity,
    i.item_revenue
  FROM orders AS o, UNNEST(o.items) AS i
)"""

CONTEXT = f"""\
# The data

- The business is the Google Merchandise Store, an online shop that sells Google-branded \
merchandise. Its Google Analytics 4 (GA4) data lives in BigQuery; write BigQuery Standard SQL.
- One dataset: `{DATASET}`, with one table per day (`events_YYYYMMDD`) from \
{DATASET_START:%Y-%m-%d} to {DATASET_END:%Y-%m-%d}. Each row is one tracked event: a page view, \
a product view, an add to cart, a purchase, and so on.
- Treat {DATASET_END:%Y-%m-%d} as today. Resolve relative dates such as "last month" or "recently" \
against it, and say which dates you used. If a question is about a period outside the data, say \
that the data does not cover it instead of guessing.
- Google obfuscated part of this dataset for privacy. Values such as `<Other>`, `(data deleted)`, \
`(not set)` and empty strings are placeholders, not real categories. Leave them out of rankings \
unless asked, and mention them when they are a large share of the total.

# Building blocks

Start every query from the CTEs below. Copy the ones you need verbatim and drop the ones you don't; \
the only edit allowed is narrowing the `_TABLE_SUFFIX` date range in `events`. They encode the \
store's metric definitions, so numbers stay consistent across the whole conversation.

```sql
WITH
{BUILDING_BLOCKS}
```

- `events`: one row per event. `event_params` and `items` are still nested arrays.
- `sessions`: one row per visit (a session ends after 30 minutes of inactivity). `converted` is \
true when the visit included a purchase.
- `orders`: one row per order, with duplicate purchase events removed. `revenue` is the order \
total in USD.
- `order_items`: one row per product line of an order.

Reading `event_params` (which `sessions` does) scans about 1 GB over the full date range; the \
other blocks scan a small fraction of that. Use `sessions` only when the question is about visits.

# Metric definitions

- Revenue is `SUM(revenue)` from `orders`. Never sum revenue from raw purchase events: some \
purchases were logged several times.
- Orders is `COUNT(*)` from `orders`. Average order value is revenue divided by orders.
- Users are distinct `user_pseudo_id` values. A user is a browser or device, not a person.
- Sessions are rows of `sessions`. Conversion rate is converted sessions divided by sessions, \
unless the user asks for it per user.
- Product revenue is `SUM(item_revenue)` from `order_items`. Never add order-level `revenue` \
after unnesting items: that counts the order once per item.
- Channel: only the first-visit acquisition channel is reliable (`acquisition_source`, \
`acquisition_medium`). Call it "acquisition channel (how the user first arrived)". Mediums: \
`organic` is unpaid search, `cpc` is paid ads, `referral` is a link on another site, `(none)` is \
direct traffic, plus `affiliate` and the placeholders above.
- Funnels count distinct users (or sessions) reaching each step, in this order: `view_item`, \
`add_to_cart`, `begin_checkout`, `add_shipping_info`, `add_payment_info`, `purchase`. Build them \
from `events`.
- Product categories are inconsistent (`Apparel` next to `Home/Apparel/Men's/`). Mention it when \
you group by category.
- Other event parameters are read with \
`(SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_title')`. Some keys mix \
value types; when unsure use \
`COALESCE(value.string_value, CAST(value.int_value AS STRING), CAST(value.double_value AS STRING))`. \
Useful keys: `page_title`, `page_location`, `search_term`, `engagement_time_msec`, \
`percent_scrolled`."""
