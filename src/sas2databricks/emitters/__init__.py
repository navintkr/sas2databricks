"""IR → Databricks target emitters."""

from __future__ import annotations

from ..ir import Program
from . import dlt_emitter, pyspark_emitter, sparksql_emitter, workflow_emitter

TARGETS = {
    "pyspark": ("notebook.py", pyspark_emitter.emit),
    "sparksql": ("queries.sql", sparksql_emitter.emit),
    "dlt": ("dlt_pipeline.py", dlt_emitter.emit),
    "workflow": ("job.json", workflow_emitter.emit),
}


def emit(prog: Program, target: str, *, source_path: str = "") -> tuple[str, str]:
    """Return (filename, content) for the given target."""
    if target not in TARGETS:
        raise ValueError(f"Unknown target '{target}'. Choose from: {', '.join(TARGETS)}")
    filename, fn = TARGETS[target]
    return filename, fn(prog, source_path=source_path)


__all__ = ["emit", "TARGETS"]
