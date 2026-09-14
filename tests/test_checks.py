from sincro.checks import find_duplicate_keys, find_missing_records, find_value_differences

def test_find_duplicate_keys(spark):
    dataframe = spark.createDataFrame(
        [(1,), (1,), (2,)],
        ["id"]
    )

    result = find_duplicate_keys(dataframe, "id").collect()

    assert len(result) == 1
    assert result[0]["id"] == 1
    assert result[0]["count"] == 2

def test_find_missing_records(spark):
    source = spark.createDataFrame(
        [(1, "Ana"), (2, "Bruno")],
        ["id", "name"],
    )
    target = spark.createDataFrame(
        [(1, "Ana")],
        ["id", "name"],
    )

    result = find_missing_records(source, target, "id").collect()

    assert len(result) == 1
    assert result[0]["id"] == 2

def test_find_value_differences(spark):
    source = spark.createDataFrame(
        [(1, "inactive")],
        ["id", "status"],
    )
    target = spark.createDataFrame(
        [(1, "active")],
        ["id", "status"],
    )

    result = find_value_differences(
        source,
        target,
        key="id",
        column="status",
    ).collect()

    assert len(result) == 1
    assert result[0]["id"] == 1
    assert result[0]["source_value"] == "inactive"
    assert result[0]["target_value"] == "active"