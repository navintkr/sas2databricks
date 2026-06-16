"""PROC FORMAT → mapping table IR (value → label)."""

from __future__ import annotations

import re

from ..ir import FormatStep
from ..parser import RawStep
from .base import prov_for

_VALUE = re.compile(r"(?is)\bvalue\s+\$?([A-Za-z_]\w*)\s*(.*?);")
_PAIR = re.compile(  # noqa: E501
    r"""(?is)('[^']*'|"[^"]*"|[^=\s]+)\s*=\s*('[^']*'|"[^"]*"|[^;]+?)(?=\s+[^=\s]+\s*=|$)"""
)


def transpile(raw: RawStep) -> list[FormatStep]:
    """A single PROC FORMAT can declare multiple VALUE formats."""
    steps: list[FormatStep] = []
    for vm in _VALUE.finditer(raw.text):
        name = vm.group(1)
        body = vm.group(2)
        mapping: dict[str, str] = {}
        default = None
        for pm in _PAIR.finditer(body):
            key = _unquote(pm.group(1).strip())
            label = _unquote(pm.group(2).strip())
            if key.lower() == "other":
                default = label
            else:
                mapping[key] = label
        prov = prov_for(raw, confidence=0.9)
        prov.notes.append(f"format `{name}` → mapping with {len(mapping)} entries")
        steps.append(
            FormatStep(
                name=f"fmt_{name}",
                prov=prov,
                format_name=name,
                mapping=mapping,
                default=default,
            )
        )
    return steps


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in "'\"" and s[-1] == s[0]:
        return s[1:-1]
    return s
