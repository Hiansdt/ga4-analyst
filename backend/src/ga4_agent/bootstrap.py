"""Composition root: the only place that picks concrete adapters and wires them together."""

import anthropic
from fastapi import FastAPI
from google.cloud import bigquery

from ga4_agent.adapters.anthropic import AnthropicModel
from ga4_agent.adapters.bigquery import BigQueryRunner
from ga4_agent.agent import Agent
from ga4_agent.api import create_app
from ga4_agent.config import Settings
from ga4_agent.datasets import ga4, ga4_metrics
from ga4_agent.prompt import build_system_prompt
from ga4_agent.ratelimit import RateLimiter
from ga4_agent.store import InMemoryStore
from ga4_agent.tools import (
    ToolRegistry,
    compiled_query_tool,
    create_chart_tool,
    run_sql_tool,
    suggest_follow_ups_tool,
)


def build_agent(settings: Settings) -> Agent:
    runner = BigQueryRunner(
        bigquery.Client(project=settings.gcp_project_id),
        allowed_dataset=ga4.DATASET,
        max_bytes=settings.max_bytes_per_query,
        max_rows=settings.max_rows_per_result,
        timeout_s=settings.query_timeout_s,
    )
    model = AnthropicModel(
        anthropic.Anthropic(),
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
        effort=settings.anthropic_effort,
    )
    metrics = compiled_query_tool(
        runner,
        name="query_metrics",
        description=ga4_metrics.DESCRIPTION,
        input_model=ga4_metrics.MetricsQuery,
        compile=ga4_metrics.compile_query,
        label=ga4_metrics.describe,
        preview_rows=settings.preview_rows,
    )
    return Agent(
        model=model,
        tools=ToolRegistry(
            [
                metrics,
                run_sql_tool(runner, preview_rows=settings.preview_rows),
                create_chart_tool(),
                suggest_follow_ups_tool(),
            ]
        ),
        system_prompt=build_system_prompt(ga4.CONTEXT),
        max_steps=settings.max_agent_steps,
    )


def build_app() -> FastAPI:
    """Uvicorn factory: uvicorn ga4_agent.bootstrap:build_app --factory"""
    settings = Settings()
    return create_app(
        build_agent(settings),
        InMemoryStore(),
        limiter=RateLimiter(limit=settings.questions_per_minute, window_s=60),
        max_question_chars=settings.max_question_chars,
        max_turns=settings.max_turns_per_conversation,
        web_dir=settings.web_dir,
    )
