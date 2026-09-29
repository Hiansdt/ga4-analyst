"""The SQL guard: a pure check of a dry run before any query executes."""

from analyst.ports.sql import DryRun, QueryError


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
