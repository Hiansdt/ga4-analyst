"""Settings, read from environment variables (e.g. GCP_PROJECT_ID, ANTHROPIC_MODEL)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gcp_project_id: str

    anthropic_model: str = "claude-sonnet-5"
    anthropic_effort: str | None = None
    anthropic_max_tokens: int = 16000

    max_bytes_per_query: int = 5 * 10**9  # the whole dataset is ~3.6 GB
    max_rows_per_result: int = 1000  # rows kept server-side, e.g. for charts
    preview_rows: int = 50  # rows the model sees
    query_timeout_s: float = 60
    max_agent_steps: int = 10
