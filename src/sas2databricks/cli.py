"""`s2db` command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .llm import CopilotProvider, Model, NullProvider
from .pipeline import MigrationResult, migrate_file


def _force_utf8() -> None:
    """Ensure non-ASCII (report tables, notes) print on legacy Windows code pages."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


_force_utf8()
console = Console()

_MODEL_CHOICE = click.Choice([m.value for m in Model], case_sensitive=False)
_TARGET_CHOICE = click.Choice(["pyspark", "sparksql", "dlt", "workflow"], case_sensitive=False)


@click.group(help="sas2databricks — migrate SAS analytics, transforms & reports to Databricks.")
@click.version_option(__version__, prog_name="s2db")
def main() -> None:  # pragma: no cover - entry point
    pass


@main.command(help="Convert a single SAS file and print (or write) the result.")
@click.argument("source", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--target", "-t", type=_TARGET_CHOICE, default="pyspark", show_default=True)
@click.option("--model", "-m", type=_MODEL_CHOICE, default="opus-4.8", show_default=True,
              help="LLM used for low-confidence steps.")
@click.option("--out", "-o", type=click.Path(path_type=Path), default=None,
              help="Write output here instead of stdout.")
@click.option("--copilot", is_flag=True,
              help="Delegate low-confidence steps to the host Copilot model.")
@click.option("--threshold", type=float, default=0.8, show_default=True)
def convert(
    source: Path, target: str, model: str, out: Path | None, copilot: bool, threshold: float
) -> None:
    provider = CopilotProvider() if copilot else NullProvider()
    result = migrate_file(
        source, target=target, model=model, provider=provider, threshold=threshold
    )
    if out:
        out.write_text(result.code, encoding="utf-8")
        console.print(f"[green]Wrote[/] {out}")
    else:
        click.echo(result.code)
    _print_summary(result)


@main.command(help="Migrate a whole SAS project (directory of .sas files).")
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option("--target", "-t", type=_TARGET_CHOICE, default="pyspark", show_default=True)
@click.option("--model", "-m", type=_MODEL_CHOICE, default="opus-4.8", show_default=True)
@click.option("--out", "-o", type=click.Path(path_type=Path), default=Path("out"),
              show_default=True)
@click.option("--copilot", is_flag=True,
              help="Delegate low-confidence steps to the host Copilot model.")
@click.option("--threshold", type=float, default=0.8, show_default=True)
def migrate_cmd(
    source: Path, target: str, model: str, out: Path, copilot: bool, threshold: float
) -> None:
    files = [source] if source.is_file() else sorted(source.rglob("*.sas"))
    if not files:
        console.print("[red]No .sas files found.[/]")
        raise SystemExit(1)

    out.mkdir(parents=True, exist_ok=True)
    provider_factory = (lambda: CopilotProvider()) if copilot else (lambda: NullProvider())
    results: list[MigrationResult] = []
    for f in files:
        result = migrate_file(f, target=target, model=model, provider=provider_factory(),
                              threshold=threshold)
        dest = out / f"{f.stem}_{result.filename}"
        dest.write_text(result.code, encoding="utf-8")
        (out / f"{f.stem}_report.md").write_text(result.report_markdown(), encoding="utf-8")
        results.append(result)
        console.print(f"[green]✓[/] {f.name} → {dest.name}  "
                      f"({result.review_count} step(s) need review)")

    total_review = sum(r.review_count for r in results)
    console.print(f"\n[bold]Migrated {len(results)} file(s)[/] → {out}/  "
                  f"| {total_review} step(s) flagged for review")


# register under the friendlier name `migrate`
main.add_command(migrate_cmd, name="migrate")


@main.command(help="Parse a SAS file and show the detected steps (no conversion).")
@click.argument("source", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def parse_cmd(source: Path) -> None:
    from .parser import parse as parse_sas

    parsed = parse_sas(source.read_text(encoding="utf-8"), source_path=str(source))
    table = Table(title=f"Steps in {source.name}")
    table.add_column("#", justify="right")
    table.add_column("Kind")
    table.add_column("Proc")
    table.add_column("Lines")
    for i, step in enumerate(parsed.steps, 1):
        table.add_row(str(i), step.kind, step.proc or "-", f"{step.start_line}-{step.end_line}")
    console.print(table)
    if parsed.macro_vars:
        console.print(f"[dim]macro vars:[/] {parsed.macro_vars}")


main.add_command(parse_cmd, name="parse")


@main.command(help="Show the migration report for a SAS file (review hotspots).")
@click.argument("source", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--target", "-t", type=_TARGET_CHOICE, default="pyspark", show_default=True)
@click.option("--model", "-m", type=_MODEL_CHOICE, default="opus-4.8", show_default=True)
def report(source: Path, target: str, model: str) -> None:
    result = migrate_file(source, target=target, model=model)
    click.echo(result.report_markdown())


@main.command(help="Run the MCP server (stdio) so GitHub Copilot can call the tools.")
def mcp() -> None:
    try:
        from .mcp.server import run
    except ImportError as exc:
        console.print("[red]MCP extras not installed.[/] Run: pip install \"sas2databricks[mcp]\"")
        raise SystemExit(1) from exc
    run()


def _print_summary(result: MigrationResult) -> None:
    review = result.review_count
    color = "yellow" if review else "green"
    console.print(
        f"[{color}]model={result.model.value} target={result.target} "
        f"steps={len(result.reports)} review={review} "
        f"llm_escalations={len(result.llm_requests)}[/]"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
