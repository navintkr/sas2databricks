"""MCP server exposing sas2databricks as tools for GitHub Copilot (and any MCP client).

Tools:
- ``parse_sas``           — list the SAS steps detected in a program.
- ``convert_sas``         — convert SAS text to a Databricks target.
- ``migrate_project``     — convert a directory of .sas files.
- ``explain_conversion``  — return the migration report (review hotspots).
- ``pending_llm_steps``   — list low-confidence steps the host model should convert.

Model selection (``opus-4.8`` / ``codex`` / ``auto``) is a parameter on the conversion
tools. When the client (Copilot) wants to fulfil low-confidence steps itself, it reads
``pending_llm_steps`` and writes the converted code back.

Run with: ``s2db mcp`` (requires the ``mcp`` extra).
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The MCP extra is required. Install with: pip install \"sas2databricks[mcp]\""
    ) from exc

from ..llm import CopilotProvider, Model
from ..pipeline import migrate

mcp = FastMCP("sas2databricks")

_MODELS = ", ".join(m.value for m in Model)
_TARGETS = "pyspark, sparksql, dlt, workflow, validate, bundle"


@mcp.tool()
def parse_sas(sas_code: str) -> str:
    """Parse SAS code and return the detected steps as JSON (kind, proc, line span)."""
    from ..parser import parse

    parsed = parse(sas_code)
    steps = [
        {"index": i, "kind": s.kind, "proc": s.proc,
         "start_line": s.start_line, "end_line": s.end_line}
        for i, s in enumerate(parsed.steps)
    ]
    return json.dumps({"steps": steps, "macro_vars": parsed.macro_vars}, indent=2)


@mcp.tool()
def convert_sas(sas_code: str, target: str = "pyspark", model: str = "opus-4.8") -> str:
    """Convert SAS code to a Databricks target.

    Args:
        sas_code: The SAS source.
        target: One of: {targets}.
        model: LLM for low-confidence steps. One of: {models} (default opus-4.8).
    """
    result = migrate(sas_code, target=target, model=model, provider=CopilotProvider())
    return json.dumps(
        {
            "filename": result.filename,
            "code": result.code,
            "model": result.model.value,
            "review_count": result.review_count,
            "pending_llm_steps": _pending(result),
        },
        indent=2,
    )


convert_sas.__doc__ = (convert_sas.__doc__ or "").format(targets=_TARGETS, models=_MODELS)


@mcp.tool()
def migrate_project(directory: str, target: str = "pyspark", model: str = "opus-4.8",
                    out_dir: str = "out", bundle: bool = False) -> str:
    """Migrate every .sas file under ``directory`` to ``target`` and write to ``out_dir``.

    Set ``bundle=True`` to assemble a deployable Databricks Asset Bundle (databricks.yml +
    src/ notebooks + reports/index.md). ``bundle`` requires a notebook target
    (pyspark, sparksql, dlt, validate).
    """
    from .. import project as project_mod

    src = Path(directory)
    files = [src] if src.is_file() else sorted(src.rglob("*.sas"))
    try:
        result = project_mod.migrate_project(
            files, out_dir, target=target, model=model, provider=CopilotProvider(),
            html=True, bundle=bundle,
        )
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, indent=2)

    summary = [
        {"source": e.source_name, "review_count": e.result.review_count}
        for e in result.entries
    ]
    return json.dumps(
        {
            "out_dir": str(result.out),
            "bundle": result.bundle,
            "files": summary,
            "total_review": result.review_count,
            "model": Model.parse(model).value,
        },
        indent=2,
    )


@mcp.tool()
def explain_conversion(sas_code: str, target: str = "pyspark", model: str = "opus-4.8") -> str:
    """Return the migration report (per-step engine, confidence, review flags, notes)."""
    result = migrate(sas_code, target=target, model=model, provider=CopilotProvider())
    return result.report_markdown()


@mcp.tool()
def pending_llm_steps(sas_code: str, target: str = "pyspark", model: str = "opus-4.8") -> str:
    """List low-confidence steps + their prompts so the host model can convert them."""
    result = migrate(sas_code, target=target, model=model, provider=CopilotProvider())
    return json.dumps(_pending(result), indent=2)


def _pending(result) -> list[dict]:
    return [
        {
            "output_name": r.output_name,
            "node_kind": r.node_kind,
            "model": r.model.value,
            "system": r.system,
            "prompt": r.prompt,
        }
        for r in result.llm_requests
    ]


def run() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    run()
