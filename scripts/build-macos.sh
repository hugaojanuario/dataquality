#!/bin/bash
# Build natively on Apple Silicon or Intel using that architecture's Python.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(uname -s)" != Darwin ]; then
    echo "Execute este script no macOS."
    exit 2
fi
dq_python="${SINCRO_PYTHON:-python3.11}"
"$dq_python" -m pip install -e '.[build,jdbc]'
"$dq_python" -m compileall -q src
"$dq_python" -m PyInstaller --clean --noconfirm sincro.spec
xattr -cr dist/Sincro.app
codesign --force --deep --sign - dist/Sincro.app
codesign --verify --deep --strict dist/Sincro.app
if [ "${1:-}" = '--smoke-test' ]; then
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
        dist/Sincro.app/Contents/MacOS/Sincro --demo --screenshots build/macos-smoke
    "$dq_python" - <<'PY'
from pathlib import Path
assert len(list(Path('build/macos-smoke').glob('*.png'))) == 32
assert not Path('build/macos-smoke/failure.txt').exists()
PY
fi
dq_stage="$(mktemp -d)"
trap 'rm -rf "$dq_stage"' EXIT
# ditto preserves the app bundle's frameworks, resource links and signatures.
ditto dist/Sincro.app "$dq_stage/Sincro.app"
ln -s /Applications "$dq_stage/Applications"
hdiutil create -volname Sincro -srcfolder "$dq_stage" -ov -format UDZO \
    "dist/Sincro-macos-$(uname -m).dmg"
echo "Aplicativo: dist/Sincro.app"
echo "Instalador: dist/Sincro-macos-$(uname -m).dmg"
