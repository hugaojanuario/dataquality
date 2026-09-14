import io
import json
from pathlib import Path
import hashlib
import plistlib

import pytest

from sincro.desktop import updater


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def release_payload(version: str, content: bytes = b'update') -> bytes:
    digest = hashlib.sha256(content).hexdigest()
    return json.dumps({
        'tag_name': f'v{version}',
        'html_url': f'https://github.com/hugaojanuario/sincro/releases/tag/v{version}',
        'assets': [{
            'name': 'Sincro-Windows-x64.exe',
            'state': 'uploaded',
            'browser_download_url': f'https://github.com/hugaojanuario/sincro/releases/download/v{version}/Sincro-Windows-x64.exe',
            'digest': f'sha256:{digest}',
            'size': len(content),
        }],
    }).encode()


def test_update_check_selects_only_a_newer_platform_asset():
    payload = release_payload('0.5.0')
    opener = lambda request, timeout: Response(payload)

    info = updater.check_for_update('0.4.0', platform_name='win32', opener=opener)

    assert info is not None
    assert info.version == '0.5.0'
    assert info.asset_name == 'Sincro-Windows-x64.exe'
    assert updater.check_for_update('0.5.0', platform_name='win32', opener=opener) is None
    assert updater.platform_asset('darwin', 'x86_64') is None


def test_download_requires_the_published_size_and_sha256(tmp_path, monkeypatch):
    content = b'signed release bytes'
    info = updater.UpdateInfo(
        '0.5.0', 'v0.5.0', 'Sincro-Windows-x64.exe',
        'https://github.com/hugaojanuario/sincro/releases/download/v0.5.0/Sincro-Windows-x64.exe',
        f'sha256:{hashlib.sha256(content).hexdigest()}', len(content), '',
    )
    directory = tmp_path / 'download'
    monkeypatch.setattr(updater.tempfile, 'mkdtemp', lambda **kwargs: str(directory))

    downloaded = updater.download_update(info, opener=lambda request, timeout: Response(content))

    assert downloaded.read_bytes() == content

    bad = updater.UpdateInfo(**{**info.__dict__, 'digest': 'sha256:' + '0' * 64})
    directory = tmp_path / 'bad-download'
    with pytest.raises(updater.UpdateError):
        updater.download_update(bad, opener=lambda request, timeout: Response(content))
    assert not directory.exists()


def test_windows_update_stages_a_waiting_replacement_script(tmp_path, monkeypatch):
    target = tmp_path / 'Sincro.exe'
    downloaded = tmp_path / 'update' / 'Sincro-Windows-x64.exe'
    target.write_bytes(b'old')
    downloaded.parent.mkdir()
    downloaded.write_bytes(b'new')
    calls = []
    monkeypatch.setattr(updater.subprocess, 'Popen', lambda *args, **kwargs: calls.append((args, kwargs)))
    info = updater.UpdateInfo('0.5.0', 'v0.5.0', downloaded.name, '', 'sha256:' + '0' * 64, 3, '')

    updater.prepare_update(info, downloaded, executable=str(target), platform_name='win32', pid=321)

    script = (downloaded.parent / 'install-update.ps1').read_text()
    assert '$appPid = 321' in script
    assert str(target) in script
    assert calls[0][0][0][0] == 'powershell.exe'


def test_macos_update_validates_bundle_and_stages_restart(tmp_path, monkeypatch):
    target = tmp_path / 'Applications' / 'Sincro.app'
    executable = target / 'Contents' / 'MacOS' / 'Sincro'
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b'old')
    downloaded = tmp_path / 'update' / 'Sincro-macOS-arm64.zip'
    downloaded.parent.mkdir()
    downloaded.write_bytes(b'zip')
    calls = []

    def extract(*args, **kwargs):
        source = downloaded.parent / 'unpacked' / 'Sincro.app' / 'Contents'
        source.mkdir(parents=True, exist_ok=True)
        with (source / 'Info.plist').open('wb') as stream:
            plistlib.dump({'CFBundleShortVersionString': '0.5.0'}, stream)

    monkeypatch.setattr(updater.subprocess, 'run', extract)
    monkeypatch.setattr(updater.subprocess, 'Popen', lambda *args, **kwargs: calls.append((args, kwargs)))
    info = updater.UpdateInfo('0.5.0', 'v0.5.0', downloaded.name, '', 'sha256:' + '0' * 64, 3, '')

    updater.prepare_update(info, downloaded, executable=str(executable), platform_name='darwin', pid=654)

    bootstrap = (downloaded.parent / 'wait-and-update.sh').read_text()
    installer = (downloaded.parent / 'install-update.sh').read_text()
    assert 'kill -0 654' in bootstrap
    assert str(target) in installer
    assert calls[0][0][0][0] == '/bin/sh'
