# Roadmap

Status legend: ✅ working · 🚧 partial · 🔭 planned

## v0.1 — Foundation (current)
- ✅ Project scaffold, packaging, CLI, MCP server, Copilot agent + skill
- ✅ Lexer/preprocessor (comments, step splitting, `%let` expansion)
- ✅ IR model with provenance + confidence
- ✅ PROC SQL → Spark SQL / PySpark (deterministic, sqlglot)
- ✅ PROC MEANS/SUMMARY → group-by aggregations
- ✅ PROC FORMAT → mapping tables / CASE
- ✅ Macro variables (`%LET`)
- 🚧 DATA step (assignments, IF/THEN/ELSE, WHERE, KEEP/DROP/RENAME)
- 🚧 LLM orchestrator (Copilot + Null providers, model routing)
- ✅ PySpark + Spark SQL emitters; 🚧 DLT + Workflows emitters

## v0.2 — DATA step depth
- 🔭 BY-group processing, `FIRST.`/`LAST.`, `RETAIN`
- 🔭 Arrays + `DO` loops, `LAG()`/`DIF()` via window functions
- 🔭 `MERGE` (SAS join semantics) → DataFrame joins
- 🔭 Informats/formats applied inside DATA steps

## v0.3 — Macro facility
- 🔭 `%MACRO`/`%MEND` with positional + keyword params → Python functions / Jinja
- 🔭 `%IF/%DO/%END` control flow, `%DO` iterative loops
- 🔭 Macro-generated code expansion before parsing

## v0.4 — Reporting
- 🔭 PROC REPORT (COLUMN/DEFINE/COMPUTE) → Databricks SQL + notebook viz
- 🔭 PROC TABULATE → pivot tables
- 🔭 ODS output → notebook/dashboard scaffolds

## v0.5 — Statistics & ML
- 🔭 PROC REG/LOGISTIC/GLM → MLlib / pandas-API-on-Spark (LLM-assisted, rule hints)
- 🔭 PROC UNIVARIATE/CORR → descriptive stats helpers

## v0.6 — Orchestration & validation
- 🔭 DLT pipeline generation with expectations
- 🔭 Databricks Workflows job graph from step dependencies
- 🔭 Data-parity validation harness (run SAS output vs Spark output, diff)
- 🔭 Unity Catalog naming / lineage mapping

## Cross-cutting
- 🔭 VS Code extension wrapper around the MCP server
- 🔭 Web report (HTML) for migration results
- 🔭 Pluggable LLM providers (Azure OpenAI, Anthropic, local) behind `LLMProvider`
