"""End-to-end migration pipeline: parse → transpile → (LLM escalate) → emit."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .emitters import emit as emit_target
from .ir import FormatStep, Program, Step
from .llm import Model, NullProvider, Orchestrator
from .llm.orchestrator import ConversionRequest, LLMProvider
from .parser import parse
from .transpilers import dispatch


@dataclass
class StepReport:
    name: str
    kind: str
    engine: str
    confidence: float
    needs_review: bool
    notes: list[str]
    start_line: int
    end_line: int


@dataclass
class MigrationResult:
    """Outcome of a migration run."""

    target: str
    model: Model
    filename: str
    code: str
    program: Program
    reports: list[StepReport] = field(default_factory=list)
    llm_requests: list[ConversionRequest] = field(default_factory=list)
    source_path: str = ""

    @property
    def review_count(self) -> int:
        return sum(1 for r in self.reports if r.needs_review)

    def report_markdown(self) -> str:
        lines = [
            f"# Migration report — {Path(self.source_path).name or 'in-memory'}",
            "",
            f"- Target: **{self.target}**",
            f"- Model: **{self.model.value}**",
            f"- Steps: **{len(self.reports)}**  |  Needs review: **{self.review_count}**",
            f"- LLM escalations: **{len(self.llm_requests)}**",
            "",
            "| Step | Kind | Engine | Conf | Review | SAS lines |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in self.reports:
            flag = "⚠️ yes" if r.needs_review else "ok"
            lines.append(
                f"| `{r.name}` | {r.kind} | {r.engine} | {r.confidence:.2f} | {flag} "
                f"| {r.start_line}-{r.end_line} |"
            )
        notes = [r for r in self.reports if r.notes]
        if notes:
            lines += ["", "## Notes"]
            for r in notes:
                lines.append(f"- **{r.name}**: " + "; ".join(r.notes))
        return "\n".join(lines) + "\n"


def _build_program(text: str, *, source_path: str) -> Program:
    parsed = parse(text, source_path=source_path)
    prog = Program(macro_vars=parsed.macro_vars)
    for raw in parsed.steps:
        for step in dispatch(raw):
            if isinstance(step, FormatStep):
                prog.formats[step.format_name] = step
            prog.steps.append(step)
    return prog


def migrate(
    text: str,
    *,
    target: str = "pyspark",
    model: str | Model = Model.OPUS_4_8,
    source_path: str = "",
    provider: LLMProvider | None = None,
    threshold: float = 0.8,
) -> MigrationResult:
    """Migrate SAS ``text`` to a Databricks ``target``.

    ``provider`` defaults to :class:`NullProvider` (offline stubs). Pass
    :class:`CopilotProvider` when running inside GitHub Copilot / MCP so low-confidence
    steps are delegated to the host model.
    """
    resolved_model = Model.parse(model) if isinstance(model, str) else model
    prog = _build_program(text, source_path=source_path)

    provider = provider or NullProvider()
    orch = Orchestrator(provider, model=resolved_model, target=target, threshold=threshold)

    converted: list[str] = []
    for step in prog.steps:
        orch.maybe_escalate(step, context=converted)
        converted.append(step.name)

    filename, code = emit_target(prog, target, source_path=source_path)

    reports = [_step_report(s, threshold) for s in prog.steps]
    return MigrationResult(
        target=target,
        model=resolved_model,
        filename=filename,
        code=code,
        program=prog,
        reports=reports,
        llm_requests=orch.requests,
        source_path=source_path,
    )


def migrate_file(path: str | Path, **kwargs) -> MigrationResult:
    p = Path(path)
    return migrate(p.read_text(encoding="utf-8"), source_path=str(p), **kwargs)


def _step_report(step: Step, threshold: float) -> StepReport:
    p = step.prov
    return StepReport(
        name=step.name,
        kind=step.kind,
        engine=p.engine.value,
        confidence=p.confidence,
        needs_review=p.needs_review(threshold),
        notes=p.notes,
        start_line=p.start_line,
        end_line=p.end_line,
    )
