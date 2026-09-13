"""Collect desktop QML families without pulling in QtWebEngine/QtWebView.

PyInstaller's default QtQml hook scans every installed QML module, including
unused browser plugins from the PySide6 Addons wheel. Filter before binary
analysis so those plugins cannot pull Chromium libraries into the application.
"""
from pathlib import PurePosixPath
from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
qml_binaries, qml_datas = pyside6_library_info.collect_qtqml_files()


def desktop_module(entry):
    parts = PurePosixPath(entry[1].replace('\\', '/')).parts
    try:
        module = parts[parts.index('qml') + 1]
    except (ValueError, IndexError):
        return False
    return module in {'QtQml', 'QtQuick', 'QtCore', 'Qt'}


binaries += [entry for entry in qml_binaries if desktop_module(entry)]
datas += [entry for entry in qml_datas if desktop_module(entry)]
