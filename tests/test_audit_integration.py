"""Opt-in, read-only tests. No real instance is assumed or created automatically."""
import os

import pytest

from sincro.audit.cli import read_connection
from sincro.audit.connectors import JDBCConnector
from sincro.audit.domain import CaptureOptions
from sincro.audit.inventory import capture


@pytest.mark.integration
@pytest.mark.parametrize('engine', ['firebird', 'postgresql', 'sqlserver', 'mysql'])
def test_real_discovery_and_profiles(engine, tmp_path):
    config_path = os.getenv(f'SINCRO_INTEGRATION_{engine.upper()}_CONFIG')
    if not config_path:
        pytest.skip('Instância/JAR/perfil não disponibilizados para ' + engine)
    profile = read_connection(config_path)
    assert profile.engine == engine
    connector = JDBCConnector(profile)
    try:
        snapshot = capture(connector, run_id='integration', role='source', path=tmp_path / 'source.json', options=CaptureOptions('balanced'))
        assert snapshot.complete, snapshot.findings
        assert snapshot.tables, 'Prepare tabelas sintéticas com PK/FK/índices na instância.'
        assert snapshot.profiles
    finally:
        connector.close()
