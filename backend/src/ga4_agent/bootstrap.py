"""Composition root: the only place that picks concrete adapters and wires them together."""

import anthropic
from google.cloud import bigquery

from ga4_agent.adapters.anthropic import AnthropicModel
from ga4_agent.adapters.bigquery import BigQueryRunner
from ga4_agent.agent import Agent
from ga4_agent.config import Settings
from ga4_agent.datasets import ga4
from ga4_agent.prompt import build_system_prompt
from ga4_agent.tools import ToolRegistry, run_sql_tool


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
    return Agent(
        model=model,
        tools=ToolRegistry([run_sql_tool(runner, preview_rows=settings.preview_rows)]),
        system_prompt=build_system_prompt(ga4.CONTEXT),
        max_steps=settings.max_agent_steps,
    )
