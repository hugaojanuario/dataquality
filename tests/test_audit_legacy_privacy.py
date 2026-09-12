from unittest.mock import Mock, patch

from pyspark.sql import Row

from dataqualy.cli import main
from dataqualy.validator import _evaluate, run_validation
from dataqualy.package_validator import run_package_validation


def test_legacy_samples_mask_personal_values():
    frame = Mock()
    frame.count.return_value = 1
    frame.limit.return_value.collect.return_value = [Row(email='private@example.invalid', password='SECRET')]
    result = _evaluate(frame, name='test', rule='test', sample_size=1)
    assert result.sample == [{'email': '[redigido]', 'password': '[redigido]'}]


def test_legacy_connection_error_does_not_leak(tmp_path, capsys):
    config = {'source': {'path': 'x'}, 'target': {'path': 'y'}, 'checks': {}}
    with patch('dataqualy.validator.create_spark_session', side_effect=RuntimeError('password=SECRET private@example.invalid')):
        report = run_validation(config)
    assert not report.passed
    assert report.results[0].status == 'error'
    assert 'SECRET' not in report.results[0].message
    with patch('dataqualy.cli.load_config', side_effect=ValueError('SECRET')):
        assert main(['validate', '--config', 'invalid']) == 2
    assert 'SECRET' not in capsys.readouterr().out


def test_package_report_default_has_no_samples(tmp_path):
    report = run_package_validation({'package': {'files': [{'path': str(tmp_path / 'missing-personal-name.csv')}]}})
    assert report.results and not report.results[0].sample
