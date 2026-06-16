"""Deterministic %MACRO body conversion.

Runs the normal parse -> transpile -> Spark SQL pipeline over a macro body (with
``&param`` references rewritten to Python ``{param}`` f-string slots) and wraps the
result in a runnable parameterized Python function. SAS macro-language control flow
(``%IF/%THEN/%DO/%ELSE/%END`` and iterative ``%DO i = a %TO b``) is lowered to Python
``if``/``elif``/``else``/``for`` blocks, with the SQL between control tokens converted
the same way as a plain macro body. Kept in its own module (rather than in
``transpilers/macro.py``) so it can import the emitters without creating an import cycle.
"""

from __future__ import annotations

import re

from .emitters import sparksql_emitter
from .ir import Engine, MacroDef
from .parser import parse
from .parser.lexer import _parse_macro_params  # noqa: PLC2701 - internal reuse
from .transpilers import dispatch

_MACRO_HEADER = re.compile(r"(?is)%macro\s+([A-Za-z_]\w*)\s*(?:\((.*?)\))?\s*;(.*)%mend", re.DOTALL)

# Macro-language control-flow tokens. Order matters: `%else %if` before `%else %do`.
_CTRL = re.compile(
    r"(?is)"
    r"%if\s+(?P<ifcond>.*?)\s+%then\s+%do\s*;"
    r"|%else\s+%if\s+(?P<elifcond>.*?)\s+%then\s+%do\s*;"
    r"|%else\s+%do\s*;"
    r"|%do\s+(?P<idx>[A-Za-z_]\w*)\s*=\s*(?P<start>.*?)\s+%to\s+(?P<stop>.*?)"
    r"(?:\s+%by\s+(?P<step>.*?))?\s*;"
    r"|%end\s*;"
)

_AMP_REF = re.compile(r"&([A-Za-z_]\w*)\.?")

# Word/operator keywords inside a macro condition -> Python operators.
_COND_WORDS = {
    "eq": "==", "ne": "!=", "ge": ">=", "le": "<=", "gt": ">", "lt": "<",
    "and": "and", "or": "or", "not": "not", "in": "in",
}
_COND_TOKEN = re.compile(
    r"""(?ix)
      (?P<amp>&[A-Za-z_]\w*\.?)                  # &macrovar (optional trailing dot)
    | (?P<num>\d+(?:\.\d+)?)                      # numeric literal
    | (?P<dq>"[^"]*")                             # double-quoted string
    | (?P<sq>'[^']*')                             # single-quoted string
    | (?P<op>>=|<=|!=|\^=|~=|<>|==|=|>|<|\(|\))   # symbolic operators
    | (?P<word>[A-Za-z_]\w*)                      # bareword (keyword op or literal text)
    | (?P<ws>\s+)
    """
)
_SYM_OPS = {"=": "==", "^=": "!=", "~=": "!=", "<>": "!="}


def _translate_macro_cond(cond: str) -> str:
    """Translate a SAS macro condition to a Python boolean expression.

    ``&var`` becomes a Python variable, numeric literals stay numeric, and a bare word
    operand (which is *literal text* in SAS macro language) is quoted as a string, so
    ``%if &grain = region`` lowers to ``grain == "region"`` rather than a NameError.
    """
    out: list[str] = []
    for m in _COND_TOKEN.finditer(cond.strip()):
        kind = m.lastgroup
        tok = m.group()
        if kind == "amp":
            out.append(tok[1:].rstrip("."))
        elif kind in ("num", "ws"):
            out.append(tok)
        elif kind == "dq":
            out.append(tok)
        elif kind == "sq":
            out.append('"' + tok[1:-1] + '"')
        elif kind == "op":
            out.append(_SYM_OPS.get(tok, tok))
        elif kind == "word":
            low = tok.lower()
            out.append(_COND_WORDS.get(low, '"' + tok + '"'))
    return "".join(out).strip()


def _translate_macro_value(expr: str) -> str:
    """Translate a SAS macro value/bound (``&n``, ``&n-1``, ``3``) to a Python expr."""
    return _AMP_REF.sub(r"\1", expr.strip())


def _macro_range(start: str, stop: str, stepv: str) -> str:
    """Build a Python ``range(...)`` for a SAS ``%DO i = start %TO stop [%BY step]`` loop.

    SAS ``%TO`` bounds are inclusive. A literal negative ``%BY`` counts down, so the stop is
    adjusted to ``stop - 1``; otherwise (ascending, or a non-literal step we cannot sign-check
    statically) the inclusive upper bound is ``stop + 1``.
    """
    if not stepv:
        return f"range({start}, {stop} + 1)"
    descending = re.fullmatch(r"\s*-\s*\d+\s*", stepv) is not None
    bound = f"{stop} - 1" if descending else f"{stop} + 1"
    return f"range({start}, {bound}, {stepv})"


def _lower_sql_segment(seg: str) -> tuple[list[str], bool]:
    """Lower a SAS fragment to Spark SQL statements, templating ``&name`` -> ``{name}``."""
    templated = _AMP_REF.sub(r"{\1}", seg)
    parsed = parse(templated, expand_macros=False, expand_calls=False)
    stmts: list[str] = []
    clean = True
    for raw in parsed.steps:
        for sub in dispatch(raw):
            stmt = sparksql_emitter._emit_step(sub)
            if not stmt or stmt.lstrip().startswith("--"):
                clean = False
            stmts.append(stmt)
    return stmts, clean


def convert_macro(step: MacroDef) -> None:
    """Populate ``step.generated`` with a parameterized Python function for the body.

    Mutates ``step`` in place: sets ``generated`` and adjusts provenance confidence /
    notes based on how cleanly the body lowered. SAS macro control flow is rendered as
    Python ``if``/``elif``/``else``/``for`` blocks; the SQL between control tokens is
    converted the same way as a plain macro body.
    """
    header = _MACRO_HEADER.search(step.prov.source or "")
    body = header.group(3).strip() if header else step.body
    params = _parse_macro_params(header.group(2) or "") if header else []

    sig = ", ".join(p if not d else f"{p}={d!r}" for p, d in params) if params else ""
    has_control = bool(_CTRL.search(body))

    lines: list[str] = [
        f"def {step.name}({sig}):",
        f'    """Converted from SAS macro %{step.name}."""',
    ]
    stack: list[bool] = []  # one has-body flag per open control block
    state = {"indent": 1, "clean": True, "emitted": False}

    def _append(text: str) -> None:
        lines.append("    " * state["indent"] + text)
        if stack:
            stack[-1] = True
        state["emitted"] = True

    def _open(opener: str) -> None:
        _append(opener)  # the opener line is body of the enclosing block
        stack.append(False)
        state["indent"] += 1

    def _close() -> None:
        if stack and not stack[-1]:
            lines.append("    " * state["indent"] + "pass")
        if stack:
            stack.pop()
        state["indent"] = max(1, state["indent"] - 1)

    def _emit_sql(seg: str) -> None:
        if not seg.strip():
            return
        stmts, seg_clean = _lower_sql_segment(seg)
        state["clean"] = state["clean"] and seg_clean
        for stmt in stmts:
            esc = stmt.replace("\\", "\\\\")
            _append(f'spark.sql(f"""{esc}""")')

    pos = 0
    for m in _CTRL.finditer(body):
        _emit_sql(body[pos : m.start()])
        pos = m.end()
        token = m.group(0).lower().lstrip()
        if m.group("ifcond") is not None:
            _open(f"if ({_translate_macro_cond(m.group('ifcond'))}):")
        elif m.group("elifcond") is not None:
            # the preceding %end already closed the %if's %do block
            _open(f"elif ({_translate_macro_cond(m.group('elifcond'))}):")
        elif token.startswith("%else"):
            _open("else:")
        elif m.group("idx") is not None:
            start = _translate_macro_value(m.group("start"))
            stop = _translate_macro_value(m.group("stop"))
            stepv = _translate_macro_value(m.group("step")) if m.group("step") else ""
            _open(f"for {m.group('idx')} in {_macro_range(start, stop, stepv)}:")
        else:  # %end
            _close()
    _emit_sql(body[pos:])

    while stack:  # unbalanced %end -> not clean, but still emit valid Python
        state["clean"] = False
        _close()

    if not state["emitted"]:
        lines.append("    pass  # MANUAL REVIEW: empty macro body")

    step.generated = "\n".join(lines)

    if has_control:
        step.prov.notes.append(
            f"macro `{step.name}` %IF/%DO control flow lowered to Python if/elif/else/for; "
            "verify conditions, loop bounds, and any &-references inside data= sources"
        )
    if state["clean"] and state["emitted"]:
        step.prov.engine = Engine.RULE
        step.prov.confidence = max(step.prov.confidence, 0.85)
        step.prov.notes.append(
            f"macro `{step.name}` body converted deterministically to a parameterized "
            "Python function (Spark SQL)"
        )
    else:
        step.prov.notes.append(
            f"macro `{step.name}` body partially converted; review generated function"
        )
