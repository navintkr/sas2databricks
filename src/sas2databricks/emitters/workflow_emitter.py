"""Emit a Databricks Workflows (Jobs) JSON wiring each step as a notebook task.

Task dependencies are derived from IR ``inputs`` (which upstream datasets a step reads),
so the generated job runs steps in the right order.
"""

from __future__ import annotations

import json

from ..ir import Program
from .base import safe_name


def emit(
    prog: Program,
    *,
    source_path: str = "",
    notebook_base: str = "/Workspace/sas_migration",
) -> str:
    produced: dict[str, str] = {}
    for step in prog.steps:
        produced[safe_name(step.name)] = safe_name(step.name)

    tasks = []
    for step in prog.steps:
        key = safe_name(step.name)
        deps = sorted(
            {safe_name(i) for i in step.inputs if safe_name(i) in produced and safe_name(i) != key}
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

    job = {
        "name": "sas_migration_job",
        "tasks": tasks,
        "format": "MULTI_TASK",
        "tags": {"generated_by": "sas2databricks", "source": source_path or "in-memory"},
    }
    return json.dumps(job, indent=2)
