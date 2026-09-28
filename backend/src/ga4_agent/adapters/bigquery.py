"""BigQuery adapter for the SQL port: dry run, guard, then a capped execution."""

import datetime
from decimal import Decimal
from typing import Any

from google.api_core.exceptions import BadRequest, Forbidden
from google.cloud import bigquery

from ga4_agent.sql import Column, DryRun, QueryError, QueryResult, validate


class BigQueryRunner:
    def __init__(
        self,
        client: bigquery.Client,
        *,
        allowed_dataset: str,
        max_bytes: int,
        max_rows: int,
        timeout_s: float,
    ) -> None:
        self._client = client
        self._allowed_dataset = allowed_dataset
        self._max_bytes = max_bytes
        self._max_rows = max_rows
        self._timeout_s = timeout_s

    def run(self, sql: str) -> QueryResult:
        validate(self._dry_run(sql), allowed_dataset=self._allowed_dataset, max_bytes=self._max_bytes)

        # The guard already checked the estimate; maximum_bytes_billed enforces it on the real job.
        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=self._max_bytes,
            job_timeout_ms=int(self._timeout_s * 1000),
        )
        try:
            job = self._client.query(sql, job_config=job_config)
            rows = job.result(max_results=self._max_rows, timeout=self._timeout_s)
            columns = [Column(field.name, field.field_type) for field in rows.schema]
            records = [{c.name: to_json_value(row[c.name]) for c in columns} for row in rows]
        except (BadRequest, Forbidden) as error:
            raise QueryError(error.message) from error

        return QueryResult(
            columns=columns,
            rows=records,
            total_rows=rows.total_rows or 0,
            bytes_processed=job.total_bytes_processed or 0,
        )

    def _dry_run(self, sql: str) -> DryRun:
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        try:
            job = self._client.query(sql, job_config=job_config)
        except (BadRequest, Forbidden) as error:
            raise QueryError(error.message) from error

        return DryRun(
            statement_type=job.statement_type,
            referenced_tables=tuple(f"{t.project}.{t.dataset_id}.{t.table_id}" for t in job.referenced_tables),
            bytes_processed=job.total_bytes_processed or 0,
        )


def to_json_value(value: Any) -> Any:
    """Convert BigQuery row values (dates, decimals, nested records) into JSON-safe values."""
    if isinstance(value, dict):
        return {key: to_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_json_value(item) for item in value]
    if isinstance(value, datetime.date | datetime.time):  # datetime is a date subclass
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value
