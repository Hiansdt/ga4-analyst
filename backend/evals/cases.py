"""Eval questions with independently computed answers.

Expected values come from queries over the verified building blocks (datasets/ga4.yaml), run
outside the agent. Most answers are deliberately absent from the system prompt, so passing
requires correct SQL, not recall of the reference totals.
"""

from dataclasses import dataclass

from evals.checks import (
    Check,
    amounts_at_most,
    mentions,
    mentions_amount,
    mentions_percent,
    percentages_at_most_100,
)

FULL_PERIOD_REVENUE = 339457


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    checks: tuple[Check, ...]
    chart: tuple[str, int] | None = None  # expected (chart type, number of points)


CASES = (
    Case(
        "december_revenue",
        "What was total revenue in December 2020?",
        (mentions_amount(158166),),
    ),
    Case(
        "daily_revenue_chart",
        "Show me daily revenue in December 2020.",
        (),
        chart=("line", 31),
    ),
    Case(
        # With "today" at 2021-01-31, December (previous calendar month) and January are both fair readings.
        "last_month_revenue",
        "How much revenue did we make last month?",
        (mentions_amount(56510, 158166),),
    ),
    Case(
        "month_over_month_orders",
        "How many orders did we get in January 2021 compared with December 2020?",
        (mentions_amount(889), mentions_amount(2304)),
    ),
    Case(
        "device_conversion",
        "Which device type converts best?",
        (mentions("mobile"), mentions_percent(1.393), percentages_at_most_100),
    ),
    Case(
        # Products appear under several categories; grouping by category too splits their sales.
        "top_product_december",
        "What was our best-selling product in December 2020 by revenue?",
        (mentions("Crewneck Sweatshirt Navy"), mentions_amount(5621)),
    ),
    Case(
        # google / organic ($90,376) or the whole organic medium ($98,024) are both fair readings.
        "top_channel",
        "Which acquisition channel brings in the most revenue?",
        (mentions("organic"), mentions_amount(90376, 98024)),
    ),
    Case(
        "us_conversion",
        "What is the conversion rate for visitors from the United States?",
        (mentions_percent(1.339), percentages_at_most_100),
    ),
    Case(
        "funnel",
        "Where do customers drop off before buying?",
        (mentions_percent(20.5, 79.5), percentages_at_most_100),
    ),
    Case(
        "outside_date_range",
        "How did sales go in 2023?",
        (
            mentions("2021"),
            mentions("don't have", "do not have", "not cover", "only cover", "no data", "outside", "not available"),
        ),
    ),
    Case(
        # Regression for the visits-to-orders join that reported $1.45M. A full total or the monthly
        # figures are both fine; inflated money is not.
        "overview",
        "How are we doing?",
        (
            mentions_amount(FULL_PERIOD_REVENUE, 124781, 158166, 56510),
            amounts_at_most(FULL_PERIOD_REVENUE),
            percentages_at_most_100,
        ),
    ),
)
