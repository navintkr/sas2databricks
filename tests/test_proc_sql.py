"""Tests for the PROC SQL transpiler and Spark SQL emission."""

from __future__ import annotations

from sas2databricks import Model, migrate
from sas2databricks.parser import parse


def test_proc_sql_converts_to_spark_view():
    sas = """
    proc sql;
      create table out1 as
      select a, sum(b) as total from src group by a;
    quit;
    """
    result = migrate(sas, target="pyspark")
    assert "spark.sql(" in result.code
    assert "out1" in result.code
    # PROC SQL is deterministic and high-confidence → no review needed
    assert result.review_count == 0
    assert result.model == Model.OPUS_4_8


def test_macro_var_expansion():
    sas = """
    %let threshold = 100;
    proc sql;
      create table big as select * from t where amount >= &threshold;
    quit;
    """
    parsed = parse(sas)
    assert parsed.macro_vars["threshold"] == "100"
    result = migrate(sas, target="sparksql")
    assert "100" in result.code


def test_sparksql_target_emits_create_view():
    sas = "proc sql; create table v as select id from src; quit;"
    result = migrate(sas, target="sparksql")
    assert "CREATE OR REPLACE TEMP VIEW v" in result.code


def test_unknown_model_rejected():
    import pytest

    with pytest.raises(ValueError):
        migrate("proc sql; select 1; quit;", model="not-a-model")
