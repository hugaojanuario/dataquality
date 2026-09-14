import pytest

from sincro.checks import (
    find_invalid_dates,
    find_invalid_pattern,
    find_invalid_values,
    find_null_values,
)


def test_find_null_values_detects_null_and_blank(spark):
    dataframe = spark.createDataFrame(
        [(1, "Ana"), (2, ""), (3, None)],
        ["id", "name"],
    )

    ids = {
        row["id"]
        for row in find_null_values(dataframe, ["name"]).collect()
    }

    assert ids == {2, 3}


def test_find_invalid_values_detects_domain_error(spark):
    dataframe = spark.createDataFrame(
        [(1, "TD"), (2, "PJ"), (3, "UNKNOWN")],
        ["id", "type"],
    )

    result = find_invalid_values(
        dataframe,
        "type",
        ["TD", "PJ"],
    ).collect()

    assert [row["id"] for row in result] == [3]


def test_find_invalid_pattern_detects_document_format(spark):
    dataframe = spark.createDataFrame(
        [(1, "12345678901"), (2, "123.456"), (3, None)],
        ["id", "document"],
    )

    result = find_invalid_pattern(
        dataframe,
        "document",
        r"^[0-9]{11}$",
    ).collect()

    assert [row["id"] for row in result] == [2]


def test_find_invalid_dates(spark):
    dataframe = spark.createDataFrame(
        [(1, "31/08/2026 10:30:00"), (2, "31/99/2026 10:30:00")],
        ["id", "date"],
    )

    result = find_invalid_dates(
        dataframe,
        "date",
        "dd/MM/yyyy HH:mm:ss",
    ).collect()

    assert [row["id"] for row in result] == [2]


# @hugaojanuario
