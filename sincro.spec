"""Native macOS .app / Windows .exe, using the same Python and QML sources."""
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

is_macos = sys.platform == 'darwin'
pyspark_data, pyspark_binaries, pyspark_hiddenimports = collect_all('pyspark')
ui_data = collect_data_files('sincro.desktop', includes=['qml/**', 'assets/**'])

analysis = Analysis(
    ['src/sincro/gui_main.py'],
    pathex=['src'],
    hookspath=['scripts/pyinstaller-hooks'],
    binaries=pyspark_binaries,
    datas=pyspark_data + ui_data,
    hiddenimports=pyspark_hiddenimports + [
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickControls2',
        'PySide6.QtNetwork', 'PySide6.QtSvg', 'jpype',
    ],
    excludes=[
        'pandas', 'pyarrow', 'pyspark.sql.connect', 'pyspark.pandas',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineQuick',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtWebView',
        'PyQt5', 'PyQt6', 'PySide2',
    ],
)
pyz = PYZ(analysis.pure)
if is_macos:
    exe = EXE(
        pyz, analysis.scripts, [], exclude_binaries=True,
        name='Sincro', console=False,
        icon='src/sincro/desktop/assets/app-icon.icns',
    )
    collection = COLLECT(exe, analysis.binaries, analysis.datas, name='Sincro')
    app = BUNDLE(
        collection, name='Sincro.app',
        icon='src/sincro/desktop/assets/app-icon.icns',
        bundle_identifier='org.sincro.desktop',
        info_plist={
            'CFBundleDisplayName': 'Sincro',
            'CFBundleShortVersionString': '0.4.0',
            'CFBundleVersion': '4',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '12.0',
            'NSHumanReadableCopyright': 'Sincro contributors — MIT',
        },
    )
else:
    exe = EXE(
        pyz, analysis.scripts, analysis.binaries, analysis.datas, [],
        name='sincro', console=False,
        icon='src/sincro/desktop/assets/app-icon.ico',
    )
