# Contributing

Thanks for helping migrate the world off SAS. 🎉

## Setup

```bash
git clone https://github.com/your-org/sas2databricks
cd sas2databricks
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev,mcp]"
pytest
```

## Where to add things

| You want to support a new… | Add code in… |
| --- | --- |
| SAS construct (PROC X, statement) | `src/sas2databricks/transpilers/` (one module) |
| Databricks target | `src/sas2databricks/emitters/` (one emitter) |
| LLM provider | `src/sas2databricks/llm/orchestrator.py` (`LLMProvider` subclass) |
| CLI command | `src/sas2databricks/cli.py` |
| MCP tool | `src/sas2databricks/mcp/server.py` |

## Conventions

- A transpiler takes a `RawStep` and returns IR node(s) with **provenance + confidence**.
  Never emit target code directly from a transpiler — that is the emitter's job.
- Prefer deterministic conversion. Only escalate to the LLM when a construct is genuinely
  ambiguous or unbounded, and always attach a validation check.
- Every new construct needs a fixture in `examples/` and a test in `tests/`.
- Run `ruff check . && pytest` before opening a PR.

## Adding a transpiler — checklist

1. Create `transpilers/proc_yourthing.py` with a `transpile(raw: RawStep) -> Step`.
2. Register it in `transpilers/__init__.py::dispatch()`.
3. Add an emitter branch in the relevant emitter(s).
4. Add `examples/sample_yourthing.sas` and `tests/test_yourthing.py`.
5. Update the coverage table in `README.md` and `ROADMAP.md`.
