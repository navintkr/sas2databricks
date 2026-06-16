"""Emit a Databricks Workflows (Jobs) JSON wiring each step as a notebook task.

Task dependencies are derived from IR ``inputs`` (which upstream datasets a step reads),
so the generated job runs steps in the right order.
"""

from __future__ import annotations

import json

from ..ir import Program
from .base import safe_name


def build_tasks(prog: Program, *, notebook_base: str = "/Workspace/sas_migration") -> list[dict]:
    """Build the ordered list of notebook tasks (with dependencies) for a program.

    Shared by the Workflows JSON emitter and the Databricks Asset Bundle emitter so the
    two targets agree on task keys and the step dependency graph.

    Dependencies are matched on both the full dataset name and its unqualified tail, so a
    ``proc sql`` reading ``enriched`` still links to a DATA step named ``work.enriched``.
    """
    alias_to_key: dict[str, str] = {}
    for step in prog.steps:
        key = safe_name(step.name)
        for alias in (key, safe_name(step.name.split(".")[-1])):
            alias_to_key.setdefault(alias, key)

    def resolve(name: str) -> str | None:
        for alias in (safe_name(name), safe_name(name.split(".")[-1])):
            if alias in alias_to_key:
                return alias_to_key[alias]
        return None

    tasks: list[dict] = []
    for step in prog.steps:
        key = safe_name(step.name)
        deps = sorted(
            {dep for i in step.inputs if (dep := resolve(i)) is not None and dep != key}
        )
        task: dict = {
            "task_key": key,
            "notebook_task": {
                "notebook_path": f"{notebook_base}/{key}",
                "source": "WORKSPACE",
            },
        }
        if deps:
            task["depends_on"] = [{"task_key": d} for d in deps]
        tasks.append(task)
    return tasks


def emit(
    prog: Program,
    *,
    source_path: str = "",
    notebook_base: str = "/Workspace/sas_migration",
) -> str:
    job = {
        "name": "sas_migration_job",
        "tasks": build_tasks(prog, notebook_base=notebook_base),
        "format": "MULTI_TASK",
        "tags": {"generated_by": "sas2databricks", "source": source_path or "in-memory"},
    }
    return json.dumps(job, indent=2)
