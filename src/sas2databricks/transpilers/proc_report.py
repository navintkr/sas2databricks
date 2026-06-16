"""PROC REPORT / PRINT → projection + display IR."""

from __future__ import annotations

import re

from ..ir import ReportStep
from ..parser import RawStep
from .base import prov_for

_DATA = re.compile(r"(?is)proc\s+\w+\s+data\s*=\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)")
_COLUMN = re.compile(r"(?is)\bcolumns?\s+(.*?);")
_VAR = re.compile(r"(?is)\bvar\s+(.*?);")
_TITLE = re.compile(r"""(?is)\btitle\d?\s+(['"])(.*?)\1\s*;""")
_GROUP_DEFINE = re.compile(r"(?is)\bdefine\s+([A-Za-z_]\w*)\s*/\s*group")


def transpile(raw: RawStep) -> ReportStep:
    prov = prov_for(raw, confidence=0.8)

    dm = _DATA.search(raw.text)
    source = dm.group(1) if dm else ""

    cols = _names(_COLUMN.search(raw.text)) or _names(_VAR.search(raw.text))
    group_by = [m.group(1) for m in _GROUP_DEFINE.finditer(raw.text)]
    title_m = _TITLE.search(raw.text)
    title = title_m.group(2) if title_m else None

    prov.notes.append("PROC REPORT/PRINT lowered to projection + display; "
                      "verify ordering, computed columns, and ODS styling")

    return ReportStep(
        name=f"{source or 'report'}_report",
        prov=prov,
        inputs=[source] if source else [],
        source=source,
        columns=cols,
        group_by=group_by,
        title=title,
    )


def _names(m: re.Match | None) -> list[str]:
    if not m:
        return []
    body = re.sub(r"/[^,;]*", " ", m.group(1))  # strip define options
    return [w for w in re.split(r"[\s,]+", body.strip()) if w and not w.startswith("=")]
