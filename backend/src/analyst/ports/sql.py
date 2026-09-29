"""SQL port: result types and the runner interface. Adapters implement `SqlRunner`."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


class QueryError(Exception):
    """A query was rejected or failed. The message is written for the model to act on."""


@dataclass(frozen=True)
class DryRun:
    statement_type: str
    referenced_tables: tuple[str, ...]  # fully qualified: project.dataset.table
    bytes_processed: int


@dataclass(frozen=True)
class Column:
    name: str
    type: str


@dataclass(frozen=True)
class QueryResult:
    columns: list[Column]
    rows: list[dict[str, Any]]  # JSON-safe values, at most the runner's row cap
    total_rows: int  # rows the query produced, before the cap
    bytes_processed: int


# Values bound to @name placeholders. Values are never pasted into SQL text.
QueryParams = Mapping[str, str | int | date | list[str]]


class SqlRunner(Protocol):
    def run(self, sql: str, params: QueryParams | None = None) -> QueryResult:
        """Validate and execute a query. Raises QueryError for anything the model should fix."""
        ...
