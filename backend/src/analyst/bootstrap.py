"""Composition root: the only place that picks concrete adapters and wires them together."""

import anthropic
from fastapi import FastAPI
from google.cloud import bigquery

from analyst.adapters.anthropic import AnthropicModel
from analyst.adapters.bigquery import BigQueryRunner
from analyst.adapters.memory_store import InMemoryStore
from analyst.api.app import create_app
from analyst.api.ratelimit import RateLimiter
from analyst.config import Settings
from analyst.core.agent import Agent
from analyst.core.prompt import build_system_prompt
from analyst.core.registry import ToolRegistry
from analyst.datasets import ga4, ga4_metrics
from analyst.tools.charts import create_chart_tool
from analyst.tools.follow_ups import suggest_follow_ups_tool
from analyst.tools.queries import compiled_query_tool, run_sql_tool


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
    """Uvicorn factory: uvicorn analyst.bootstrap:build_app --factory"""
    settings = Settings()
    return create_app(
        build_agent(settings),
        InMemoryStore(),
        limiter=RateLimiter(limit=settings.questions_per_minute, window_s=60),
        max_question_chars=settings.max_question_chars,
        max_turns=settings.max_turns_per_conversation,
        web_dir=settings.web_dir,
    )
