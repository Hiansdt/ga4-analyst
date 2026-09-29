"""Renders a dataset definition into the dataset section of the system prompt."""

from analyst.semantic.dataset import Dataset
from analyst.semantic.layer import SemanticLayer


def render_context(dataset: Dataset) -> str:
    date_columns = list(dict.fromkeys(f"`{b.date_column}`" for b in dataset.blocks if b.date_column))
    blocks = "\n".join(f"- `{block.name}`: {block.description.strip()}" for block in dataset.blocks)
    sections = [
        f"# The data\n\n{dataset.description.strip()}",
        "# Building blocks\n\n"
        "Start every query from the CTEs below. Copy the ones you need verbatim, without any edits, and drop "
        "the ones you don't. They encode the metric definitions, so numbers stay consistent across the whole "
        f"conversation. Filter dates on the blocks' own date columns ({', '.join(date_columns)}), not inside "
        f"the blocks they are built from.\n\n```sql\n{SemanticLayer(dataset).with_clause()}\n```\n\n{blocks}"
        + (f"\n\n{dataset.block_notes.strip()}" if dataset.block_notes.strip() else ""),
    ]
    if dataset.reference_totals.strip():
        sections.append(f"# Reference totals\n\n{dataset.reference_totals.strip()}")
    if dataset.metric_notes.strip():
        sections.append(f"# Metric definitions\n\n{dataset.metric_notes.strip()}")
    return "\n\n".join(sections)
