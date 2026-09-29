"""Settings, read from environment variables (e.g. GCP_PROJECT_ID, ANTHROPIC_MODEL)."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gcp_project_id: str
    dataset: str = "ga4"  # a definition in datasets/, e.g. datasets/ga4.yaml

    anthropic_model: str = "claude-sonnet-5"
    anthropic_effort: str | None = None
    anthropic_max_tokens: int = 16000

    max_bytes_per_query: int = 5 * 10**9  # the whole dataset is ~3.6 GB
    max_rows_per_result: int = 1000  # rows kept server-side, e.g. for charts
    preview_rows: int = 50  # rows the model sees
    query_timeout_s: float = 60
    max_agent_steps: int = 10

    # The link is public and every question spends credits. The whole history is resent on every step,
    # so long questions and long chats cost more each turn.
    questions_per_minute: int = 20  # per client
    max_question_chars: int = 4000  # the frontend textarea uses the same limit
    max_turns_per_conversation: int = 30

    web_dir: Path | None = None  # built frontend (web/dist) to serve at "/"; None serves the API only
