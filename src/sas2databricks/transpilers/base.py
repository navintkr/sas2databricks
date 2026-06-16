"""Shared helpers for transpilers: SAS expression → Spark SQL expression translation."""

from __future__ import annotations

import re

from ..ir import Engine, Provenance
from ..parser import RawStep

# SAS scalar function → Spark SQL function (lowercased keys)
SAS_FUNC_MAP: dict[str, str] = {
    "upcase": "upper",
    "lowcase": "lower",
    "propcase": "initcap",
    "substr": "substring",
    "trim": "trim",
    "strip": "trim",
    "left": "ltrim",
    "length": "length",
    "scan": "split_part",  # approximate; reviewed
    "index": "instr",
    "tranwrd": "replace",
    "compress": "regexp_replace",
    "today": "current_date",
    "datepart": "to_date",
    "year": "year",
    "month": "month",
    "day": "day",
    "intck": "datediff",  # approximate
    "abs": "abs",
    "round": "round",
    "ceil": "ceil",
    "floor": "floor",
    "int": "int",
    "log": "log",
    "exp": "exp",
    "sqrt": "sqrt",
    "sum": "+",  # SAS sum() of args -> handled specially
    "max": "greatest",
    "min": "least",
    "coalesce": "coalesce",
    "put": "cast",  # approximate
    "input": "cast",  # approximate
}

# SAS operators → SQL operators
_OPERATOR_MAP = [
    (re.compile(r"\beq\b", re.IGNORECASE), "="),
    (re.compile(r"\bne\b", re.IGNORECASE), "!="),
    (re.compile(r"\bgt\b", re.IGNORECASE), ">"),
    (re.compile(r"\blt\b", re.IGNORECASE), "<"),
    (re.compile(r"\bge\b", re.IGNORECASE), ">="),
    (re.compile(r"\ble\b", re.IGNORECASE), "<="),
    (re.compile(r"\band\b", re.IGNORECASE), "AND"),
    (re.compile(r"\bor\b", re.IGNORECASE), "OR"),
    (re.compile(r"\bnot\b", re.IGNORECASE), "NOT"),
]

_FUNC_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_MISSING = re.compile(r"\.\s*(?=$|[\s),])")  # a lone `.` meaning SAS missing value


def translate_expr(expr: str) -> tuple[str, list[str]]:
    """Translate a SAS scalar expression to a Spark SQL expression.

    Returns the translated expression plus a list of warning notes for anything
    approximate that a reviewer should verify.
    """
    notes: list[str] = []
    out = expr.strip()

    # SAS uses `=` for equality in boolean context too; keep `=` but normalize `^=`/`~=`.
    out = out.replace("^=", "!=").replace("~=", "!=").replace("<>", "!=")

    # word operators -> sql
    for pattern, repl in _OPERATOR_MAP:
        out = pattern.sub(repl, out)

    # SAS string concat operator `||` is the same in Spark SQL — leave as is.

    # function name remap
    def _remap(m: re.Match) -> str:
        fn = m.group(1).lower()
        mapped = SAS_FUNC_MAP.get(fn)
        if mapped and mapped.isidentifier():
            if mapped in {"split_part", "datediff", "to_date", "cast"}:
                notes.append(f"function `{fn}()` mapped to `{mapped}()` — verify arguments")
            return f"{mapped}("
        if mapped == "+":
            notes.append("SAS sum() mapped to + — verify null handling")
        return m.group(0)

    out = _FUNC_CALL.sub(_remap, out)

    # SAS missing numeric `.` -> NULL (best effort, only for standalone dots)
    if _MISSING.search(out):
        out = _MISSING.sub("NULL", out)
        notes.append("SAS missing value `.` mapped to NULL")

    return out, notes


def prov_for(raw: RawStep, *, engine: Engine = Engine.RULE, confidence: float = 1.0) -> Provenance:
    return Provenance(
        source=raw.text,
        start_line=raw.start_line,
        end_line=raw.end_line,
        engine=engine,
        confidence=confidence,
    )


def output_name(raw: RawStep, default: str) -> str:
    """Best-effort extraction of the output dataset name from a step."""
    m = re.search(r"\bdata\s*=?\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)", raw.text, re.IGNORECASE)
    if m and raw.kind != "data":
        return m.group(1)
    m = re.match(r"\s*data\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)", raw.text, re.IGNORECASE)
    if m:
        return m.group(1)
    return default
