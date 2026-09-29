"""BigQuery adapter for the SQL port: dry run, guard, then a capped execution."""

import datetime
from decimal import Decimal
from typing import Any

from google.api_core.exceptions import BadRequest, Forbidden, GoogleAPICallError
from google.cloud import bigquery

from analyst.core.sql_guard import validate
from analyst.ports.sql import Column, DryRun, QueryError, QueryParams, QueryResult


class BigQueryRunner:
    def __init__(
        self,
        client: bigquery.Client,
        *,
        allowed_datasets: list[str],
        max_bytes: int,
        max_rows: int,
        timeout_s: float,
    ) -> None:
        self._client = client
        self._allowed_datasets = allowed_datasets
        self._max_bytes = max_bytes
        self._max_rows = max_rows
        self._timeout_s = timeout_s

    def run(self, sql: str, params: QueryParams | None = None) -> QueryResult:
        parameters = [_parameter(name, value) for name, value in (params or {}).items()]
        validate(self._dry_run(sql, parameters), allowed_datasets=self._allowed_datasets, max_bytes=self._max_bytes)

        # The guard already checked the estimate; maximum_bytes_billed enforces it on the real job.
        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=self._max_bytes,
            job_timeout_ms=int(self._timeout_s * 1000),
            query_parameters=parameters,
        )
        try:
            job = self._client.query(sql, job_config=job_config)
            rows = job.result(max_results=self._max_rows, timeout=self._timeout_s)
            columns = [Column(field.name, field.field_type) for field in rows.schema]
            records = [{c.name: to_json_value(row[c.name]) for c in columns} for row in rows]
        except (BadRequest, Forbidden) as error:
            raise QueryError(_reason(error)) from error

        return QueryResult(
            columns=columns,
            rows=records,
            total_rows=rows.total_rows or 0,
            bytes_processed=job.total_bytes_processed or 0,
        )

    def _dry_run(self, sql: str, parameters: list) -> DryRun:
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False, query_parameters=parameters)
        try:
            job = self._client.query(sql, job_config=job_config)
        except (BadRequest, Forbidden) as error:
            raise QueryError(_reason(error)) from error

        return DryRun(
            statement_type=job.statement_type,
            referenced_tables=tuple(f"{t.project}.{t.dataset_id}.{t.table_id}" for t in job.referenced_tables),
            bytes_processed=job.total_bytes_processed or 0,
        )


def _parameter(name: str, value: str | int | datetime.date | list[str]):
    match value:
        case list():
            return bigquery.ArrayQueryParameter(name, "STRING", value)
        case bool():
            raise TypeError(f"Unsupported query parameter {name}={value!r}")
        case int():
            return bigquery.ScalarQueryParameter(name, "INT64", value)
        case datetime.date():
            return bigquery.ScalarQueryParameter(name, "DATE", value)
        case str():
            return bigquery.ScalarQueryParameter(name, "STRING", value)
    raise TypeError(f"Unsupported query parameter {name}={value!r}")


def _reason(error: GoogleAPICallError) -> str:
    """BigQuery's own explanation, without the request URL and job id around it."""
    return error.errors[0]["message"] if error.errors else error.message


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
