"""Run the eval cases against the real agent and print a scorecard.

Usage (from backend/):
    uv run --env-file ../.env python -m evals.run --model claude-haiku-4-5 --model claude-sonnet-5
    uv run --env-file ../.env python -m evals.run --case funnel --case overview
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from analyst.bootstrap import build_agent
from analyst.config import Settings
from analyst.core.agent import Agent
from analyst.core.events import TextDelta, ToolFinished, ToolStarted, TurnCompleted, TurnFailed
from analyst.ports.llm import Usage
from evals.cases import CASES, Case

RESULTS_DIR = Path(__file__).parent / "results"

# USD per million tokens: (input, output). Cache reads cost 0.1x input, cache writes 1.25x.
PRICES = {"claude-haiku-4-5": (1.0, 5.0), "claude-sonnet-5": (2.0, 10.0)}


@dataclass
class Outcome:
    model: str
    case: str
    passed: bool
    failures: list[str]
    queries: int
    failed_queries: int
    tools: list[str]  # tools called, in order
    seconds: float
    cost_usd: float
    answer: str


def cost(model: str, usage: Usage) -> float:
    input_price, output_price = PRICES[model]
    return (
        usage.input_tokens * input_price
        + usage.cache_read_input_tokens * input_price * 0.1
        + usage.cache_creation_input_tokens * input_price * 1.25
        + usage.output_tokens * output_price
    ) / 1e6


def run_case(agent: Agent, model: str, case: Case) -> Outcome:
    started = time.monotonic()
    answer, failures, queries, failed_queries, usage = "", [], 0, 0, Usage()
    charts: list[tuple[str, int]] = []
    tools: list[str] = []
    for event in agent.run_turn([], case.question):
        match event:
            case ToolStarted(name=name):
                tools.append(name)
            case TextDelta(text):
                answer += text
            case ToolFinished(name="create_chart", is_error=False, display=chart):
                charts.append((chart["type"], len(chart["rows"])))
            case ToolFinished(name="run_sql" | "query_metrics", is_error=is_error):
                queries += 1
                failed_queries += is_error
            case TurnFailed(message):
                failures.append(f"turn failed: {message}")
            case TurnCompleted(usage=turn_usage):
                usage = turn_usage
    failures += [reason for check in case.checks if (reason := check(answer))]
    if case.chart and case.chart not in charts:
        failures.append(f"expected a {case.chart[0]} chart with {case.chart[1]} points, got {charts or 'none'}")
    return Outcome(
        model=model,
        case=case.id,
        passed=not failures,
        failures=failures,
        queries=queries,
        failed_queries=failed_queries,
        tools=tools,
        seconds=round(time.monotonic() - started, 1),
        cost_usd=round(cost(model, usage), 4),
        answer=answer,
    )


def print_scorecard(outcomes: list[Outcome]) -> None:
    print(
        f"\n{'model':<18} {'case':<26} {'result':<6} {'queries':>7} {'metrics':>7} {'follow':>6} {'secs':>6} {'cost':>7}  failures"
    )
    for o in outcomes:
        queries = f"{o.queries}" + (f" ({o.failed_queries}x)" if o.failed_queries else "")
        result = "PASS" if o.passed else "FAIL"
        print(
            f"{o.model:<18} {o.case:<26} {result:<6} {queries:>7} {o.tools.count('query_metrics'):>7} {'yes' if 'suggest_follow_ups' in o.tools else 'no':>6} {o.seconds:>6} "
            f"${o.cost_usd:>6.3f}  {'; '.join(o.failures)}"
        )
    for model in dict.fromkeys(o.model for o in outcomes):
        mine = [o for o in outcomes if o.model == model]
        passed = sum(o.passed for o in mine)
        print(
            f"{model}: {passed}/{len(mine)} passed, ${sum(o.cost_usd for o in mine):.2f} total, "
            f"{sum(o.seconds for o in mine) / len(mine):.0f}s average"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", action="append", help="repeatable; default claude-haiku-4-5")
    parser.add_argument("--case", action="append", help="repeatable; default all cases")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    models = args.model or ["claude-haiku-4-5"]
    cases = [c for c in CASES if not args.case or c.id in args.case]
    outcomes: list[Outcome] = []
    for model in models:
        agent = build_agent(Settings(anthropic_model=model))
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            outcomes += pool.map(lambda case, a=agent, m=model: run_case(a, m, case), cases)

    print_scorecard(outcomes)
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps([asdict(o) for o in outcomes], indent=2))
    print(f"\nFull answers: {path}")


if __name__ == "__main__":
    main()
