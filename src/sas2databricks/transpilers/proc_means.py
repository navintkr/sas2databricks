"""PROC MEANS / SUMMARY / FREQ / TABULATE → group-by aggregation IR."""

from __future__ import annotations

import re

from ..ir import Aggregation, AggStep
from ..parser import RawStep
from .base import prov_for

_DATA = re.compile(r"(?is)proc\s+\w+\s+data\s*=\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)")
_CLASS = re.compile(r"(?is)\bclass\s+(.*?);")
_VAR = re.compile(r"(?is)\bvar\s+(.*?);")
_TABLES = re.compile(r"(?is)\btables\s+(.*?);")
_OUTPUT = re.compile(r"(?is)\boutput\s+out\s*=\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)")
_STATS = re.compile(
    r"(?im)\b(n|nmiss|mean|median|sum|min|max|std|stddev|var|range|p25|p50|p75|count)\b"
)

# SAS stat keyword → Spark SQL aggregate function
_STAT_MAP = {
    "n": "count",
    "count": "count",
    "nmiss": "count_if_null",
    "mean": "avg",
    "median": "percentile_approx_50",
    "sum": "sum",
    "min": "min",
    "max": "max",
    "std": "stddev",
    "stddev": "stddev",
    "var": "variance",
    "range": "range",
    "p25": "percentile_approx_25",
    "p50": "percentile_approx_50",
    "p75": "percentile_approx_75",
}


def transpile(raw: RawStep) -> AggStep:
    prov = prov_for(raw, confidence=0.85)

    dm = _DATA.search(raw.text)
    source = dm.group(1) if dm else ""

    group_by = _names(_CLASS.search(raw.text))
    if not group_by and raw.proc.lower() == "freq":
        # PROC FREQ tables -> group by the listed vars
        group_by = _names(_TABLES.search(raw.text), split_star=True)

    vars_ = _names(_VAR.search(raw.text))
    stats = [_STAT_MAP.get(s.lower(), s.lower()) for s in _STATS.findall(raw.text)]
    if not stats:
        stats = ["count"] if raw.proc.lower() == "freq" else ["avg"]

    measures: list[Aggregation] = []
    if raw.proc.lower() == "freq":
        measures.append(Aggregation(func="count", column="*", alias="freq"))
        prov.notes.append("PROC FREQ lowered to count by group")
    else:
        cols = vars_ or ["*"]
        for col in cols:
            for stat in stats:
                alias = f"{col}_{stat}".replace("*", "all")
                measures.append(Aggregation(func=stat, column=col, alias=alias))

    out = _OUTPUT.search(raw.text)
    name = out.group(1) if out else f"{source or 'data'}_summary"

    return AggStep(
        name=name,
        prov=prov,
        inputs=[source] if source else [],
        source=source,
        group_by=group_by,
        measures=measures,
    )


def _names(m: re.Match | None, *, split_star: bool = False) -> list[str]:
    if not m:
        return []
    raw = m.group(1).strip()
    if split_star:
        raw = raw.replace("*", " ")
    return [w for w in re.split(r"[\s,]+", raw) if w]
