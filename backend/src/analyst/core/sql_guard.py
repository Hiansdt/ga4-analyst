"""The SQL guard: a pure check of a dry run before any query executes."""

from analyst.ports.sql import DryRun, QueryError


def validate(dry_run: DryRun, *, allowed_datasets: list[str], max_bytes: int) -> None:
    """Reject anything but a single read-only query over the allowed datasets, within budget."""
    if dry_run.statement_type != "SELECT":
        raise QueryError(f"Only single SELECT statements are allowed; got {dry_run.statement_type}.")

    outside = [t for t in dry_run.referenced_tables if t.rsplit(".", 1)[0] not in allowed_datasets]
    if outside:
        raise QueryError(f"Only tables in {', '.join(allowed_datasets)} can be queried; got {', '.join(outside)}.")

    if dry_run.bytes_processed > max_bytes:
        raise QueryError(
            f"The query would scan {dry_run.bytes_processed / 1e9:.1f} GB, over the "
            f"{max_bytes / 1e9:.1f} GB limit. Narrow the date range or read fewer columns."
        )
