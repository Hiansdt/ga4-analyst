"""TheLook eval questions with independently computed answers.

Expected values come from hand-written queries on the raw snapshot tables, not through the building
blocks (see tests/test_thelook_dataset.py). "Today" is 2026-09-27, so last month is August 2026.
"""

from evals.cases import Case
from evals.checks import amounts_at_most, mentions, mentions_amount, mentions_percent, percentages_at_most_100

FULL_PERIOD_REVENUE = 8057059.49

CASES = (
    Case(
        "last_month_revenue",
        "What was revenue last month?",
        (mentions_amount(351981.62),),
    ),
    Case(
        "revenue_this_year",
        "How much revenue have we made so far this year?",
        (mentions_amount(2666874.54),),
    ),
    Case(
        "top_profit_category",
        "Which product category brings in the most gross profit?",
        (mentions("Outerwear"), mentions_amount(537838.72)),
    ),
    Case(
        "returns_by_category",
        "Which product categories get returned the most?",
        (mentions("Jumpsuits"), mentions_percent(13.22), percentages_at_most_100),
    ),
    Case(
        # Visits have their own traffic source; the customer's signup channel is a different thing.
        "visit_conversion_by_source",
        "Which traffic source has the best visit conversion rate?",
        (mentions("Adwords"), mentions_percent(26.675), percentages_at_most_100),
    ),
    Case(
        "monthly_revenue_chart",
        "Show me the monthly revenue trend for 2026 as a line chart.",
        (),
        chart=("line", 9),
    ),
    Case(
        "outside_date_range",
        "How did sales go in 2018?",
        (
            mentions("2019"),
            mentions("don't have", "do not have", "not cover", "only cover", "no data", "outside", "not available"),
        ),
    ),
    Case(
        "overview",
        "How are we doing?",
        (amounts_at_most(FULL_PERIOD_REVENUE), percentages_at_most_100),
    ),
)
