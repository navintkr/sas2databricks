# Model selection

sas2databricks is **deterministic-first**: the rules engine converts everything it
recognizes without any LLM call. A language model is invoked only for the *residue* —
low-confidence steps such as `%macro` bodies, `RETAIN`/array/`LAG` logic, complex
`PROC REPORT` computed columns, and statistical PROCs.

## Choices

| Value | When to use |
| --- | --- |
| `opus-4.8` *(default)* | Complex macros, intricate business logic, reports. Best reasoning. |
| `codex` | Fast, mechanical rewrites where the pattern is clear. |
| `auto` | Router: Opus for `macro`/`report`/unknown nodes, Codex for the rest. |

The routing policy lives in [`llm/models.py`](../src/sas2databricks/llm/models.py)
(`route()`), and the set of "heavy reasoning" node kinds is `_HEAVY_REASONING`.

## How each front-end sets the model

- **VS Code Copilot agent** — the chat **model picker** drives it. The
  `sas-migrator.agent.md` defaults to Opus 4.8; switching the picker to Codex (or Auto)
  changes which model fulfils `pending_llm_steps`.
- **MCP server** — every conversion tool takes a `model` argument
  (`convert_sas(..., model="codex")`).
- **CLI** — the `--model` flag: `s2db convert file.sas --model opus-4.8`.

## Provider model (no vendor lock-in)

The orchestrator talks to an `LLMProvider`, not a specific vendor:

- `CopilotProvider` *(default in MCP/agent)* — delegates conversion to the **host Copilot
  model** the user already selected. No API keys ship with the tool; the user's model
  picker is the source of truth.
- `NullProvider` *(default offline CLI)* — emits a `# MANUAL REVIEW` stub so the
  deterministic pipeline still produces runnable output without any model.

To add a direct API provider (Anthropic, Azure OpenAI), subclass `LLMProvider` and
implement `convert()`. See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Why deterministic-first matters

Routing only the hard nodes to the model keeps migrations **cheap, fast, and
reproducible**, and means a reviewer can trust that the bulk of the output came from
rules — with the model's contributions clearly tagged (`engine=llm`) in every migration
report.
