import pytest

from ga4_agent.sql import DryRun, QueryError, validate

DATASET = "bigquery-public-data.ga4_obfuscated_sample_ecommerce"
EVENTS = f"{DATASET}.events_*"
MAX_BYTES = 5 * 10**9


def dry_run(statement_type="SELECT", tables=(EVENTS,), bytes_processed=10**6) -> DryRun:
    return DryRun(statement_type=statement_type, referenced_tables=tables, bytes_processed=bytes_processed)


def test_accepts_select_on_allowed_dataset():
    validate(dry_run(), allowed_dataset=DATASET, max_bytes=MAX_BYTES)


def test_accepts_select_without_tables():
    validate(dry_run(tables=()), allowed_dataset=DATASET, max_bytes=MAX_BYTES)


@pytest.mark.parametrize("statement_type", ["SCRIPT", "INSERT", "DELETE", "MERGE", "CREATE_TABLE", "DROP_TABLE"])
def test_rejects_anything_but_a_single_select(statement_type):
    with pytest.raises(QueryError, match="Only single SELECT"):
        validate(dry_run(statement_type=statement_type), allowed_dataset=DATASET, max_bytes=MAX_BYTES)


@pytest.mark.parametrize(
    "table",
    [
        "bigquery-public-data.samples.shakespeare",
        # Same prefix, different dataset: must not pass a naive startswith check.
        f"{DATASET}_copy.events_20201101",
    ],
)
def test_rejects_tables_outside_the_allowed_dataset(table):
    with pytest.raises(QueryError, match=table):
        validate(dry_run(tables=(EVENTS, table)), allowed_dataset=DATASET, max_bytes=MAX_BYTES)


def test_rejects_queries_over_the_byte_limit_with_a_hint():
    with pytest.raises(QueryError, match="date range"):
        validate(dry_run(bytes_processed=MAX_BYTES + 1), allowed_dataset=DATASET, max_bytes=MAX_BYTES)
