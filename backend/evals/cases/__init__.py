"""Eval cases per dataset. Each dataset has its own questions and independently verified answers."""

from dataclasses import dataclass

from evals.checks import Check


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    checks: tuple[Check, ...]
    chart: tuple[str, int] | None = None  # expected (chart type, number of points)


def cases_for(dataset: str) -> tuple[Case, ...]:
    from evals.cases import ga4, thelook

    return {"ga4": ga4.CASES, "thelook": thelook.CASES}[dataset]
