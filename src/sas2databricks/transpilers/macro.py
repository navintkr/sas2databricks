"""SAS macro (%MACRO/%MEND) capture → parameterized definition IR."""

from __future__ import annotations

import re

from ..ir import Engine, MacroDef
from ..parser import RawStep
from .base import prov_for

_MACRO = re.compile(r"(?is)%macro\s+([A-Za-z_]\w*)\s*(?:\((.*?)\))?\s*;(.*?)%mend", re.DOTALL)


def transpile(raw: RawStep) -> MacroDef:
    m = _MACRO.search(raw.text)
    prov = prov_for(raw, engine=Engine.LLM, confidence=0.5)
    if not m:
        prov.engine = Engine.MANUAL
        prov.notes.append("could not parse %macro definition; preserved for review")
        return MacroDef(name="macro", prov=prov, body=raw.text)

    name = m.group(1)
    params_raw = (m.group(2) or "").strip()
    params = [p.split("=")[0].strip() for p in params_raw.split(",") if p.strip()]
    body = m.group(3).strip()

    prov.notes.append(
        f"macro `{name}` captured with params {params or '[]'}; body should be converted "
        "to a parameterized Python function / Jinja template (LLM-assisted)"
    )
    return MacroDef(name=name, prov=prov, params=params, body=body)
