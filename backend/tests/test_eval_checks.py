from evals.checks import (
    amounts_at_most,
    mentions,
    mentions_amount,
    mentions_percent,
    numbers,
    percentages_at_most_100,
)


def test_numbers_understands_money_thousands_and_percentages():
    assert numbers("Revenue was $158,166 ($158.2K) from 2,304 orders, up 26.8%.") == [
        (158166.0, "$"),
        (158200.0, "$"),
        (2304.0, ""),
        (26.8, "%"),
    ]


def test_amount_matches_within_tolerance_but_not_percentages():
    check = mentions_amount(158166)

    assert check("December brought in $158.2K.") is None
    assert check("December brought in $150,000.") is not None
    assert check("A 158166% increase") is not None


def test_amount_matches_plain_counts():
    assert mentions_amount(889)("We had 889 orders.") is None


def test_percent_matches_rounded_values():
    assert mentions_percent(1.393)("Mobile converts at 1.4%.") is None
    assert mentions_percent(1.393)("Mobile converts at 1.8%.") is not None


def test_mentions_is_case_insensitive():
    assert mentions("mobile", "phone")("MOBILE wins") is None
    assert mentions("mobile")("desktop wins") is not None


def test_percentages_over_100_fail():
    assert percentages_at_most_100("Conversion 1.3%, share 26.6%") is None
    assert percentages_at_most_100("Orders per session 116.8%") is not None


def test_money_above_the_limit_fails_but_plain_counts_do_not():
    check = amounts_at_most(339457)

    assert check("Revenue $339,457 from 360,129 sessions.") is None
    assert check("Revenue was $1.45M.") is not None


def test_amount_tolerance_catches_small_miscounts():
    # 158,726 was a real bug: orders leaking across a month boundary (+0.35%).
    assert mentions_amount(158166)("December: $158,726") is not None
