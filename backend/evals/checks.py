"""Deterministic checks on an answer's text. Each returns None on success or a failure reason."""

import re
from collections.abc import Callable

Check = Callable[[str], str | None]

# "$158,166", "$158.2K", "$1.45M", "2,304", "1.4%". A K/M suffix must not start a word ("5 more").
_NUMBER = re.compile(r"(\$?)(\d[\d,]*(?:\.\d+)?)(?:\s?([KkMm])(?![A-Za-z]))?(%?)")
_SCALE = {"k": 1e3, "m": 1e6}


def numbers(text: str) -> list[tuple[float, str]]:
    """Every number in the text as (value, unit), unit being "$", "%" or "", with K/M expanded."""
    found = []
    for dollar, digits, suffix, percent in _NUMBER.findall(text):
        value = float(digits.replace(",", "")) * _SCALE.get(suffix.lower(), 1)
        found.append((value, percent or dollar))
    return found


def mentions_amount(*expected: float, rel_tol: float = 0.001) -> Check:
    """At least one number within rel_tol of any expected value ($158.2K matches 158,166; $158,726 does not)."""

    def check(answer: str) -> str | None:
        for value, unit in numbers(answer):
            if unit != "%" and any(abs(value - e) <= rel_tol * e for e in expected):
                return None
        return f"no amount close to {' or '.join(f'{e:,.0f}' for e in expected)}"

    return check


def mentions_percent(*expected: float, abs_tol: float = 0.06) -> Check:
    """At least one percentage within abs_tol points of any expected value (1.393 matches 1.4%)."""

    def check(answer: str) -> str | None:
        for value, unit in numbers(answer):
            if unit == "%" and any(abs(value - e) <= abs_tol for e in expected):
                return None
        return f"no percentage close to {' or '.join(f'{e}%' for e in expected)}"

    return check


def mentions(*alternatives: str) -> Check:
    """At least one of the phrases appears, case-insensitive."""

    def check(answer: str) -> str | None:
        lowered = answer.lower()
        if any(a.lower() in lowered for a in alternatives):
            return None
        return f"mentions none of {list(alternatives)}"

    return check


def percentages_at_most_100(answer: str) -> str | None:
    """Shares and rates can't exceed 100%; one that does means a broken query."""
    too_big = [value for value, unit in numbers(answer) if unit == "%" and value > 100]
    return f"impossible percentages {too_big}" if too_big else None


def amounts_at_most(limit: float, rel_tol: float = 0.005) -> Check:
    """No dollar amount above limit: the full-period revenue caps every revenue figure."""

    def check(answer: str) -> str | None:
        too_big = [value for value, unit in numbers(answer) if unit == "$" and value > limit * (1 + rel_tol)]
        return f"dollar amounts above {limit:,.0f}: {too_big}" if too_big else None

    return check
