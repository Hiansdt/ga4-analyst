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
from analyst.semantic.context import render_context
from analyst.semantic.dataset import Dataset, load_dataset
from analyst.semantic.layer import SemanticLayer
from analyst.tools.charts import create_chart_tool
from analyst.tools.follow_ups import suggest_follow_ups_tool
from analyst.tools.queries import compiled_query_tool, run_sql_tool


def build_agent(settings: Settings, dataset: Dataset) -> Agent:
    """One agent for one dataset, e.g. for the terminal client and the eval."""
    return _agent(settings, dataset, bigquery.Client(project=settings.gcp_project_id), anthropic.Anthropic())


def _agent(settings: Settings, dataset: Dataset, bq: bigquery.Client, llm: anthropic.Anthropic) -> Agent:
    layer = SemanticLayer(dataset)
    # Each dataset gets its own runner, so its queries can only read its own tables.
    runner = BigQueryRunner(
        bq,
        allowed_datasets=dataset.tables,
        max_bytes=settings.max_bytes_per_query,
        max_rows=settings.max_rows_per_result,
        timeout_s=settings.query_timeout_s,
    )
    model = AnthropicModel(
        llm,
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
        effort=settings.anthropic_effort,
    )
    metrics = compiled_query_tool(
        runner,
        name="query_metrics",
        description=layer.tool_description(),
        input_model=layer.query_model,
        compile=layer.compile,
        label=layer.describe,
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
        system_prompt=build_system_prompt(render_context(dataset)),
        max_steps=settings.max_agent_steps,
    )


def build_app() -> FastAPI:
    """Uvicorn factory: uvicorn analyst.bootstrap:build_app --factory"""
    settings = Settings()
    datasets = {name: load_dataset(name) for name in settings.dataset_names()}
    bq, llm = bigquery.Client(project=settings.gcp_project_id), anthropic.Anthropic()
    return create_app(
        {name: _agent(settings, dataset, bq, llm) for name, dataset in datasets.items()},
        InMemoryStore(),
        datasets=[
            {
                "id": name,
                "name": dataset.name,
                "start": dataset.period.start.isoformat(),
                "end": dataset.period.end.isoformat(),
                "example_questions": dataset.example_questions,
            }
            for name, dataset in datasets.items()
        ],
        limiter=RateLimiter(limit=settings.questions_per_minute, window_s=60),
        max_question_chars=settings.max_question_chars,
        max_turns=settings.max_turns_per_conversation,
        web_dir=settings.web_dir,
    )
