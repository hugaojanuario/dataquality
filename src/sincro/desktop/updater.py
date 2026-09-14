"""Background release checks and platform-specific self-update staging."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable
import hashlib
import json
import os
import platform
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request


REPOSITORY = 'hugaojanuario/sincro'
LATEST_RELEASE_API = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
DOWNLOAD_PREFIX = f'https://github.com/{REPOSITORY}/releases/download/'
ASSETS = {
    'darwin': 'Sincro-macOS-arm64.zip',
    'win32': 'Sincro-Windows-x64.exe',
}


class UpdateError(Exception):
    pass


class UpdateCancelled(UpdateError):
    pass


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    tag: str
    asset_name: str
    url: str
    digest: str
    size: int
    release_url: str


def version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value.strip())
    if not match:
        raise UpdateError('Versão publicada inválida.')
    return tuple(map(int, match.groups()))


def platform_asset(platform_name: str | None = None, machine: str | None = None) -> str | None:
    platform_name = platform_name or sys.platform
    machine = (machine or platform.machine()).lower()
    if platform_name == 'darwin' and machine not in ('arm64', 'aarch64'):
        return None
    return ASSETS.get(platform_name)


def check_for_update(current_version: str, *, platform_name: str | None = None,
                     machine: str | None = None, timeout: float = 4,
                     opener=None) -> UpdateInfo | None:
    asset_name = platform_asset(platform_name, machine)
    if not asset_name:
        return None
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': f'Sincro/{current_version}',
        },
    )
    with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise UpdateError('Resposta de atualização inválida.')
    payload = json.loads(raw)
    tag = str(payload.get('tag_name', ''))
    if version_tuple(tag) <= version_tuple(current_version):
        return None
    asset = next((item for item in payload.get('assets', [])
                  if item.get('name') == asset_name and item.get('state') == 'uploaded'), None)
    if not asset:
        raise UpdateError('A nova versão ainda não possui instalador para este computador.')
    url = str(asset.get('browser_download_url', ''))
    digest = str(asset.get('digest', ''))
    size = int(asset.get('size', 0))
    if not url.startswith(DOWNLOAD_PREFIX) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest) or size <= 0:
        raise UpdateError('Os dados de verificação da atualização são inválidos.')
    return UpdateInfo(tag.removeprefix('v'), tag, asset_name, url, digest, size,
                      str(payload.get('html_url', '')))


def download_update(info: UpdateInfo, *, cancel: Event | None = None,
                    progress: Callable[[int], None] | None = None,
                    opener=None) -> Path:
    directory = Path(tempfile.mkdtemp(prefix='sincro-update-'))
    directory.mkdir(parents=True, exist_ok=True)
    partial = directory / (info.asset_name + '.part')
    destination = directory / info.asset_name
    digest = hashlib.sha256()
    received = 0
    last_percent = -1
    try:
        request = urllib.request.Request(info.url, headers={'User-Agent': f'Sincro/{info.version}'})
        with (opener or urllib.request.urlopen)(request, timeout=20) as response, partial.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                if cancel and cancel.is_set():
                    raise UpdateCancelled('Atualização cancelada.')
                received += len(chunk)
                if received > info.size:
                    raise UpdateError('O arquivo baixado possui tamanho inesperado.')
                digest.update(chunk)
                output.write(chunk)
                percent = int(received * 100 / info.size)
                if progress and percent != last_percent:
                    progress(percent)
                    last_percent = percent
        if received != info.size or f'sha256:{digest.hexdigest()}' != info.digest:
            raise UpdateError('A verificação de integridade da atualização falhou.')
        partial.replace(destination)
        return destination
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


def _current_macos_bundle(executable: str) -> Path:
    path = Path(executable).absolute()
    bundle = next((parent for parent in path.parents if parent.suffix == '.app'), None)
    if bundle is None:
        raise UpdateError('Não foi possível localizar o aplicativo instalado.')
    return bundle


def _powershell_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _prepare_windows(info: UpdateInfo, downloaded: Path, executable: str, pid: int) -> None:
    target = Path(executable).absolute()
    if target.suffix.lower() != '.exe':
        raise UpdateError('Não foi possível localizar o executável instalado.')
    script = downloaded.parent / 'install-update.ps1'
    target_literal = _powershell_literal(str(target))
    source_literal = _powershell_literal(str(downloaded))
    script.write_text(f"""$ErrorActionPreference = 'Stop'
$appPid = {pid}
$target = {target_literal}
$source = {source_literal}
$backup = $target + '.sincro-backup'
while (Get-Process -Id $appPid -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 500 }}
try {{
    if (Test-Path -LiteralPath $backup) {{ Remove-Item -LiteralPath $backup -Force }}
    Move-Item -LiteralPath $target -Destination $backup -Force
    Move-Item -LiteralPath $source -Destination $target -Force
    Start-Process -FilePath $target
    Remove-Item -LiteralPath $backup -Force
}} catch {{
    if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $target)) {{
        Move-Item -LiteralPath $backup -Destination $target -Force
    }}
    if (Test-Path -LiteralPath $target) {{ Start-Process -FilePath $target }}
    exit 1
}}
""", encoding='utf-8')
    creationflags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)
    subprocess.Popen(
        ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def _prepare_macos(info: UpdateInfo, downloaded: Path, executable: str, pid: int) -> None:
    target = _current_macos_bundle(executable)
    unpacked = downloaded.parent / 'unpacked'
    subprocess.run(['/usr/bin/ditto', '-x', '-k', str(downloaded), str(unpacked)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    source = unpacked / 'Sincro.app'
    plist_path = source / 'Contents' / 'Info.plist'
    if not plist_path.is_file():
        raise UpdateError('O pacote da atualização é inválido.')
    subprocess.run(['/usr/bin/xattr', '-cr', str(source)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(source)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with plist_path.open('rb') as stream:
        bundle_version = str(plistlib.load(stream).get('CFBundleShortVersionString', ''))
    if version_tuple(bundle_version) != version_tuple(info.version):
        raise UpdateError('A versão do aplicativo baixado não corresponde à versão publicada.')

    root = downloaded.parent
    backup = target.with_name(target.name + '.sincro-backup')
    installer = root / 'install-update.sh'
    installer.write_text(f"""#!/bin/sh
set -eu
target={shlex.quote(str(target))}
source={shlex.quote(str(source))}
backup={shlex.quote(str(backup))}
root={shlex.quote(str(root))}
/bin/rm -rf "$backup"
/bin/mv "$target" "$backup"
if /usr/bin/ditto "$source" "$target"; then
    /usr/bin/open "$target"
    /bin/rm -rf "$backup" "$root"
    exit 0
fi
/bin/rm -rf "$target"
/bin/mv "$backup" "$target"
/usr/bin/open "$target"
exit 1
""", encoding='utf-8')
    installer.chmod(0o700)
    apple_script = f'do shell script "/bin/sh " & quoted form of {json.dumps(str(installer))} with administrator privileges'
    bootstrap = root / 'wait-and-update.sh'
    bootstrap.write_text(f"""#!/bin/sh
while /bin/kill -0 {pid} 2>/dev/null; do /bin/sleep 0.5; done
if [ -w {shlex.quote(str(target.parent))} ]; then
    exec /bin/sh {shlex.quote(str(installer))}
fi
exec /usr/bin/osascript -e {shlex.quote(apple_script)}
""", encoding='utf-8')
    bootstrap.chmod(0o700)
    subprocess.Popen(['/bin/sh', str(bootstrap)], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def prepare_update(info: UpdateInfo, downloaded: Path, *, executable: str | None = None,
                   platform_name: str | None = None, pid: int | None = None) -> None:
    executable = executable or sys.executable
    platform_name = platform_name or sys.platform
    pid = pid or os.getpid()
    if platform_name == 'darwin':
        _prepare_macos(info, downloaded, executable, pid)
    elif platform_name == 'win32':
        _prepare_windows(info, downloaded, executable, pid)
    else:
        raise UpdateError('Atualização automática indisponível neste sistema.')
