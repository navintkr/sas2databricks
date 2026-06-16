---
name: sas-migration
description: >-
  Convert SAS analytics, transformations, and reports to Databricks using the
  sas2databricks toolkit. USE WHEN the user wants to migrate SAS code (.sas files,
  PROC SQL, DATA steps, SAS macros, PROC MEANS/SUMMARY/FREQ/TABULATE, PROC FORMAT,
  PROC REPORT/PRINT) to PySpark, Spark SQL, Delta Live Tables, or Databricks Workflows.
  Triggers: "migrate SAS", "convert SAS to Databricks", "SAS to PySpark", "PROC SQL to
  Spark", "SAS DATA step", "SAS macro to Databricks", "convert .sas file".
---

# SAS → Databricks migration

This skill converts SAS to Databricks using a **deterministic-first** engine with an
**LLM fallback** for the hard parts. You choose the model; default is **Opus 4.8**.

## How the toolkit works

```
SAS → parse → deterministic transpilers → (low-confidence steps → LLM you fulfil) → emit
```

- **Deterministic** (no model needed, fully reviewable): PROC SQL, PROC MEANS/SUMMARY/FREQ,
  PROC FORMAT, macro variables (`%let`), most DATA-step assignments/filters.
- **LLM-assisted** (you convert these): `%macro` bodies, RETAIN/arrays/`LAG`/`FIRST.`-`LAST.`,
  PROC REPORT computed columns, statistical PROCs, and any unrecognized construct.

## Tools (MCP server `sas2databricks`)

| Tool | Purpose |
| --- | --- |
| `parse_sas(sas_code)` | List detected steps (kind, proc, line span). |
| `convert_sas(sas_code, target, model)` | Convert to a target; returns code + review count. |
| `migrate_project(directory, target, model, out_dir)` | Convert a folder of `.sas` files. |
| `pending_llm_steps(sas_code, target, model)` | The steps **you** must convert, with prompts. |
| `explain_conversion(sas_code, target, model)` | Migration report (review hotspots). |

`target` ∈ {`pyspark` (default), `sparksql`, `dlt`, `workflow`}.
`model` ∈ {`opus-4.8` (default), `codex`, `auto`}.

## Procedure

1. `parse_sas` to confirm scope.
2. `convert_sas` / `migrate_project` with the user's target + model.
3. `pending_llm_steps` → for each item, write idiomatic Databricks code that preserves
   exact SAS semantics. Use window functions for RETAIN/LAG/FIRST.-LAST.; never Python
   row loops. Convert `%macro` to a parameterized Python function.
4. `explain_conversion` → review every flagged step with the user.
5. Save outputs + the migration report.

## Semantic checklist (do not skip)

- SAS missing values (`.` / blank) → `NULL`, and verify they propagate through math/joins.
- BY-group processing → `Window.partitionBy(by).orderBy(...)`; `FIRST.`/`LAST.` → `row_number`.
- `RETAIN` accumulation → running aggregate over an ordered window.
- SAS implicit numeric↔character coercion → explicit `cast`.
- `MERGE` (SAS) semantics ≠ SQL MERGE — usually a full/left join with coalesce.
- `lib.table` → Unity Catalog `catalog.schema.table`; flag for the user to map.

## Fallback: CLI

If MCP tools are unavailable:

```bash
s2db convert path/to/file.sas --target pyspark --model opus-4.8 --copilot
s2db migrate ./sas_project --target dlt --out ./databricks
s2db report path/to/file.sas        # review hotspots
```
