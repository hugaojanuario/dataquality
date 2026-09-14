import pytest

from sincro.spark import create_spark_session

"""
essa notacao abaixo cria uma unica sessao Spark para todos os teste e finaliza eles no final
"""
@pytest.fixture(scope="session")
def spark():
    session = create_spark_session()
    session.sparkContext.setLogLevel("ERROR")

    yield session

    session.stop()
