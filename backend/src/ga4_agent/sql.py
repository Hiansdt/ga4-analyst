"""SQL port: result types, the runner interface and the pure query guard.

Nothing here talks to a database; adapters implement `SqlRunner`.
"""

from dataclasses import dataclass
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


class SqlRunner(Protocol):
    def run(self, sql: str) -> QueryResult:
        """Validate and execute a query. Raises QueryError for anything the model should fix."""
        ...


def validate(dry_run: DryRun, *, allowed_dataset: str, max_bytes: int) -> None:
    """Reject anything but a single read-only query over the allowed dataset, within budget."""
    if dry_run.statement_type != "SELECT":
        raise QueryError(f"Only single SELECT statements are allowed; got {dry_run.statement_type}.")

    outside = [t for t in dry_run.referenced_tables if not t.startswith(f"{allowed_dataset}.")]
    if outside:
        raise QueryError(f"Only tables in {allowed_dataset} can be queried; got {', '.join(outside)}.")

    if dry_run.bytes_processed > max_bytes:
        raise QueryError(
            f"The query would scan {dry_run.bytes_processed / 1e9:.1f} GB, over the "
            f"{max_bytes / 1e9:.1f} GB limit. Narrow the date range or read fewer columns."
        )
