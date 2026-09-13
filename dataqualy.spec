"""Native macOS .app / Windows .exe, using the same Python and QML sources."""
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

is_macos = sys.platform == 'darwin'
pyspark_data, pyspark_binaries, pyspark_hiddenimports = collect_all('pyspark')
ui_data = collect_data_files('dataqualy.desktop', includes=['qml/**', 'assets/**'])

analysis = Analysis(
    ['src/dataqualy/gui_main.py'],
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
        name='DataQuality', console=False,
        icon='src/dataqualy/desktop/assets/app-icon.icns',
    )
    collection = COLLECT(exe, analysis.binaries, analysis.datas, name='DataQuality')
    app = BUNDLE(
        collection, name='DataQuality.app',
        icon='src/dataqualy/desktop/assets/app-icon.icns',
        bundle_identifier='org.dataquality.desktop',
        info_plist={
            'CFBundleDisplayName': 'DataQuality',
            'CFBundleShortVersionString': '0.2.0',
            'CFBundleVersion': '2',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '12.0',
            'NSHumanReadableCopyright': 'DataQuality contributors — MIT',
        },
    )
else:
    exe = EXE(
        pyz, analysis.scripts, analysis.binaries, analysis.datas, [],
        name='dataqualy', console=False,
        icon='src/dataqualy/desktop/assets/app-icon.ico',
    )
