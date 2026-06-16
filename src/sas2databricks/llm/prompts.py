"""Prompt templates for LLM-assisted SAS → Databricks conversion."""

from __future__ import annotations

SYSTEM_PROMPT = """\
You are a senior data engineer who migrates SAS code to Databricks. You convert SAS to \
idiomatic {target} for Databricks (Spark 3.5+, Unity Catalog). Rules:
- Preserve exact business logic and SAS semantics (missing-value handling, BY-group \
  processing, RETAIN accumulation, FIRST./LAST. flags, numeric/character coercion).
- Use window functions for LAG/DIF/RETAIN/FIRST.-LAST.; never row-by-row Python loops.
- Keep output deterministic and reviewable. Add a short comment citing the SAS construct.
- If something cannot be faithfully translated, emit a clearly marked `# MANUAL REVIEW:` \
  comment explaining why, rather than guessing silently.
Return ONLY the {target} code block, no prose."""

CONVERT_PROMPT = """\
Convert this SAS step to {target} for Databricks.

SAS source (lines {start}-{end}):
```sas
{sas}
```

Context (already-converted upstream datasets available as DataFrames/views): {context}

Output target dataset name: `{output_name}`
"""

EXPLAIN_PROMPT = """\
Explain, in 3-5 bullet points, how the following SAS step was converted to {target}, \
calling out any semantic risks a reviewer must verify (missing values, joins, ordering).

SAS:
```sas
{sas}
```

Generated {target}:
```python
{generated}
```
"""

VALIDATE_PROMPT = """\
You are reviewing a SAS→Databricks conversion. List any correctness risks where the \
{target} output could differ from SAS, as a JSON array of short strings. Empty array if none.

SAS:
```sas
{sas}
```
{target}:
```
{generated}
```
"""
