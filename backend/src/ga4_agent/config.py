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

    # TODO(security-hardening): Add a per-client rate limit setting and enforce it in the API layer
    # WHY: the deployed link is public; every question spends Anthropic credits and BigQuery quota
    # DONE-WHEN: an API test posting 21 questions within a minute from one client gets HTTP 429 on the 21st

    # TODO(security-hardening): Add a max question length setting and reject longer questions in the API layer
    # WHY: unbounded input inflates token cost on every later turn of the conversation
    # DONE-WHEN: an API test posting a 4,001-character question gets HTTP 422 and the model is never called

    # TODO(security-hardening): Cap turns per conversation and start a new one past the limit
    # WHY: the full history is resent on every step, so long conversations get expensive and slow
    # DONE-WHEN: an API test posting message 31 to a 30-turn conversation gets HTTP 409 with a "start a new conversation" message
