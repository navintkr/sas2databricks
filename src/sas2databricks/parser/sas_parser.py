"""Top-level SAS parser: preprocess → extract macro vars → split into steps."""

from __future__ import annotations

from dataclasses import dataclass, field

from .lexer import (
    RawStep,
    expand_macro_vars,
    extract_macro_vars,
    split_steps,
    strip_comments,
)


@dataclass
class ParsedProgram:
    """Result of parsing a SAS source file."""

    steps: list[RawStep]
    macro_vars: dict[str, str] = field(default_factory=dict)
    source_path: str = ""


def parse(text: str, *, source_path: str = "", expand_macros: bool = True) -> ParsedProgram:
    """Parse raw SAS ``text`` into a :class:`ParsedProgram`."""
    cleaned = strip_comments(text)
    macro_vars = extract_macro_vars(cleaned)
    if expand_macros:
        cleaned = expand_macro_vars(cleaned, macro_vars)
    steps = split_steps(cleaned)
    return ParsedProgram(steps=steps, macro_vars=macro_vars, source_path=source_path)
