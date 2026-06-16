"""SAS lexer / preprocessor.

SAS is not cleanly context-free, so rather than a single grammar we preprocess the
source (strip comments, expand ``%let`` macro variables) and split it into *steps*
(``DATA ...; run;``, ``PROC ...; run/quit;``, ``%macro ...; %mend;``). Each step is then
handed to a construct-specific transpiler.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---- comment stripping ----------------------------------------------------------------

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
# `* ... ;` statement comments (only when `*` starts a statement)
_STAR_COMMENT = re.compile(r"(?m)^\s*\*[^;]*;")
_MACRO_COMMENT = re.compile(r"%\*[^;]*;")


def strip_comments(text: str) -> str:
    text = _BLOCK_COMMENT.sub(" ", text)
    text = _MACRO_COMMENT.sub(" ", text)
    text = _STAR_COMMENT.sub(" ", text)
    return text


# ---- macro variable expansion ---------------------------------------------------------

_LET = re.compile(r"%let\s+([A-Za-z_]\w*)\s*=\s*([^;]*);", re.IGNORECASE)


def extract_macro_vars(text: str) -> dict[str, str]:
    """Collect ``%let`` assignments. Returns {name: value} (last write wins)."""
    out: dict[str, str] = {}
    for m in _LET.finditer(text):
        out[m.group(1).lower()] = m.group(2).strip()
    return out


def expand_macro_vars(text: str, variables: dict[str, str]) -> str:
    """Resolve ``&name`` / ``&name.`` references using ``variables`` (iteratively)."""
    if not variables:
        return text
    prev = None
    cur = text
    # iterate to resolve nested references, bounded to avoid infinite loops
    for _ in range(10):
        if cur == prev:
            break
        prev = cur
        for name, value in variables.items():
            cur = re.sub(rf"&{name}\.?", value, cur, flags=re.IGNORECASE)
    return cur


# ---- step splitting -------------------------------------------------------------------


@dataclass
class RawStep:
    """A raw SAS step (pre-transpilation)."""

    text: str
    kind: str  # data | proc_sql | proc_means | proc_format | proc_report | proc | macro | unknown
    proc: str = ""  # PROC name when kind == proc*
    start_line: int = 0
    end_line: int = 0
    extra: dict = field(default_factory=dict)


_STEP_START = re.compile(
    r"(?im)^\s*(data\b|proc\s+\w+|%macro\b)",
)
_BOUNDARY = re.compile(r"(?im)\b(run|quit|%mend)\s*;")


def _classify(header: str) -> tuple[str, str]:
    h = header.strip().lower()
    if h.startswith("data"):
        return "data", ""
    if h.startswith("%macro"):
        return "macro", ""
    m = re.match(r"proc\s+(\w+)", h)
    if m:
        proc = m.group(1)
        mapping = {
            "sql": "proc_sql",
            "means": "proc_means",
            "summary": "proc_means",
            "freq": "proc_means",
            "tabulate": "proc_means",
            "format": "proc_format",
            "report": "proc_report",
            "print": "proc_report",
        }
        return mapping.get(proc, "proc"), proc
    return "unknown", ""


def split_steps(text: str) -> list[RawStep]:
    """Split preprocessed SAS text into a list of :class:`RawStep`."""
    steps: list[RawStep] = []
    starts = [m.start() for m in _STEP_START.finditer(text)]
    starts.append(len(text))
    line_index = _line_starts(text)

    for i in range(len(starts) - 1):
        chunk = text[starts[i] : starts[i + 1]]
        # trim the chunk at its closing boundary (run; / quit; / %mend;) if present
        boundary = _BOUNDARY.search(chunk)
        if boundary:
            chunk = chunk[: boundary.end()]
        chunk = chunk.strip()
        if not chunk:
            continue
        header = chunk.splitlines()[0]
        kind, proc = _classify(header)
        start_line = _line_of(line_index, starts[i])
        steps.append(
            RawStep(
                text=chunk,
                kind=kind,
                proc=proc,
                start_line=start_line,
                end_line=start_line + chunk.count("\n"),
            )
        )
    return steps


def _line_starts(text: str) -> list[int]:
    idx = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            idx.append(i + 1)
    return idx


def _line_of(line_starts: list[int], pos: int) -> int:
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1
