"""PROC SQL → Spark SQL, using sqlglot for a real dialect transpile."""

from __future__ import annotations

import re

import sqlglot
from sqlglot.errors import ParseError

from ..ir import Engine, SqlStep
from ..parser import RawStep
from .base import prov_for

# strip the PROC SQL wrapper, keep the inner statements
_PROC_SQL_WRAPPER = re.compile(r"(?is)^\s*proc\s+sql\s*;(.*?)(?:\bquit\s*;|\brun\s*;|\Z)")
_CREATE_TABLE = re.compile(r"(?is)create\s+table\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s+as\s+(.*)")
# SAS-specific SQL keyword: `CALCULATED <alias>` references an alias from the SELECT list.
# Spark SQL allows referencing the alias directly, so the keyword is simply dropped.
_CALCULATED = re.compile(r"(?i)\bcalculated\s+")


def _normalize_sas_sql(sql: str) -> tuple[str, list[str]]:
    """Rewrite SAS-specific SQL idioms into standard SQL before handing to sqlglot."""
    notes: list[str] = []
    if _CALCULATED.search(sql):
        sql = _CALCULATED.sub("", sql)
        notes.append("removed SAS `CALCULATED` keyword (alias referenced directly)")
    return sql, notes


def transpile(raw: RawStep) -> SqlStep:
    """Translate a ``PROC SQL`` step into a :class:`SqlStep` with Spark-dialect SQL."""
    inner_match = _PROC_SQL_WRAPPER.search(raw.text)
    inner = inner_match.group(1).strip() if inner_match else raw.text
    inner = inner.rstrip(";").strip()

    target = "result"
    body = inner
    creates = False
    ct = _CREATE_TABLE.search(inner)
    if ct:
        target = ct.group(1)
        body = ct.group(2).strip()
        creates = True

    prov = prov_for(raw)
    body, sas_notes = _normalize_sas_sql(body)
    prov.notes += sas_notes
    try:
        # SAS SQL is closest to ANSI/T-SQL; read generically, write Spark.
        converted = sqlglot.transpile(body, read=None, write="spark", pretty=True)[0]
        confidence = 0.95
    except ParseError as exc:
        converted = body
        confidence = 0.4
        prov.engine = Engine.MANUAL
        prov.notes.append(f"sqlglot could not parse this SQL ({exc.__class__.__name__}); "
                          "emitted verbatim for review")

    prov.confidence = confidence
    inputs = _extract_tables(body)
    return SqlStep(
        name=target,
        prov=prov,
        inputs=inputs,
        sql=converted,
        creates_table=creates,
    )


def _extract_tables(sql: str) -> list[str]:
    try:
        expr = sqlglot.parse_one(sql)
    except Exception:
        return []
    return sorted({t.name for t in expr.find_all(sqlglot.exp.Table) if t.name})
