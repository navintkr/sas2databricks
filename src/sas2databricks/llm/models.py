"""Model selection and routing policy for the LLM-assisted conversion layer."""

from __future__ import annotations

from enum import Enum


class Model(str, Enum):
    """LLM choices exposed to the user.

    ``OPUS_4_8`` is the default — strongest reasoning for complex macros and business
    logic. ``CODEX`` is fast and code-focused. ``AUTO`` lets the router decide per node.
    """

    OPUS_4_8 = "opus-4.8"
    CODEX = "codex"
    AUTO = "auto"

    @classmethod
    def parse(cls, value: str | None) -> Model:
        if not value:
            return cls.OPUS_4_8
        normalized = value.strip().lower().replace("_", "-")
        aliases = {
            "opus": cls.OPUS_4_8,
            "opus-4.8": cls.OPUS_4_8,
            "claude": cls.OPUS_4_8,
            "default": cls.OPUS_4_8,
            "codex": cls.CODEX,
            "gpt-codex": cls.CODEX,
            "auto": cls.AUTO,
        }
        if normalized not in aliases:
            raise ValueError(
                f"Unknown model '{value}'. Choose one of: "
                + ", ".join(m.value for m in cls)
            )
        return aliases[normalized]


# Node kinds that benefit most from heavy reasoning (Opus) vs. mechanical rewrite (Codex).
_HEAVY_REASONING = {"macro", "report", "raw"}


def route(model: Model, node_kind: str) -> Model:
    """Resolve ``AUTO`` to a concrete model for a given IR node kind."""
    if model is not Model.AUTO:
        return model
    return Model.OPUS_4_8 if node_kind in _HEAVY_REASONING else Model.CODEX
