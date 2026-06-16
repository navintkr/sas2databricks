"""DATA step → IR.

Handles the common deterministic subset: ``set``, assignments, ``if/then/else``,
``where``, ``keep``/``drop``/``rename``, and ``by``. Unknown statements lower the
confidence so the orchestrator can escalate to the LLM.
"""

from __future__ import annotations

import re

from ..ir import Assignment, DataStep, Engine
from ..parser import RawStep
from .base import prov_for, translate_expr

_DATA_HEADER = re.compile(r"(?is)^\s*data\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*;")
_SET = re.compile(r"(?is)\bset\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)")
_WHERE = re.compile(r"(?is)\bwhere\s+(.*?);")
_KEEP = re.compile(r"(?is)\bkeep\s+(.*?);")
_DROP = re.compile(r"(?is)\bdrop\s+(.*?);")
_BY = re.compile(r"(?is)\bby\s+(.*?);")
_RENAME = re.compile(r"(?is)\brename\s+(.*?);")
_IF_THEN = re.compile(
    r"(?is)\bif\s+(.*?)\s+then\s+([A-Za-z_]\w*)\s*=\s*(.*?);"
)
_ASSIGN = re.compile(r"(?im)^\s*([A-Za-z_]\w*)\s*=\s*(.*?);")

# statements we knowingly consume so we can detect "leftover" unknown logic
_KNOWN = re.compile(
    r"(?is)\b(data|set|where|keep|drop|by|rename|if|run|format|label|length|retain|array|do|end|output)\b"
)


def transpile(raw: RawStep) -> DataStep:
    text = raw.text
    header = _DATA_HEADER.search(text)
    name = header.group(1) if header else "result"

    prov = prov_for(raw)
    notes: list[str] = []

    set_m = _SET.search(text)
    source = set_m.group(1) if set_m else ""
    inputs = [source] if source else []

    where = None
    wm = _WHERE.search(text)
    if wm:
        where, wnotes = translate_expr(wm.group(1))
        notes += wnotes

    keep = _split_names(_KEEP.search(text))
    drop = _split_names(_DROP.search(text))
    by = _split_names(_BY.search(text))
    rename = _parse_rename(_RENAME.search(text))

    assignments: list[Assignment] = []
    consumed_spans: list[tuple[int, int]] = []

    for m in _IF_THEN.finditer(text):
        cond, cnotes = translate_expr(m.group(1))
        expr, enotes = translate_expr(m.group(3))
        assignments.append(Assignment(target=m.group(2), expr=expr, condition=cond))
        notes += cnotes + enotes
        consumed_spans.append(m.span())

    for m in _ASSIGN.finditer(text):
        if _overlaps(m.span(), consumed_spans):
            continue
        target = m.group(1).lower()
        if target in {"set", "by", "where", "keep", "drop", "rename"}:
            continue
        expr, enotes = translate_expr(m.group(2))
        assignments.append(Assignment(target=m.group(1), expr=expr))
        notes += enotes

    confidence = 0.9
    if _has_unknown_logic(text):
        confidence = 0.6
        prov.engine = Engine.LLM
        notes.append(
            "DATA step contains constructs (retain/array/do/lag/first.-last.) not fully "
            "lowered deterministically — flagged for LLM assist / review"
        )

    prov.confidence = confidence
    prov.notes += notes
    return DataStep(
        name=name,
        prov=prov,
        inputs=inputs,
        source=source,
        assignments=assignments,
        where=where,
        keep=keep,
        drop=drop,
        rename=rename,
        by=by,
    )


def _split_names(m: re.Match | None) -> list[str]:
    if not m:
        return []
    return [w for w in re.split(r"[\s,]+", m.group(1).strip()) if w]


def _parse_rename(m: re.Match | None) -> dict[str, str]:
    if not m:
        return {}
    out: dict[str, str] = {}
    for pair in re.split(r"[\s,]+", m.group(1).strip()):
        if "=" in pair:
            old, new = pair.split("=", 1)
            out[old.strip()] = new.strip()
    return out


def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(span[0] >= s and span[1] <= e for s, e in spans)


def _has_unknown_logic(text: str) -> bool:
    return bool(
        re.search(
            r"(?is)\b(retain|array|lag\d*|dif\d*|first\.|last\.|do\s+while|do\s+until)\b",
            text,
        )
    )
