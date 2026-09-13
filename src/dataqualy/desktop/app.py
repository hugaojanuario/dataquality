"""Qt Quick entry point. QML resources are located relative to this package."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QFont, QFontDatabase, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .viewmodel import AppViewModel

QML_DIRECTORY = Path(__file__).parent / 'qml'


def create_engine(model: AppViewModel) -> QQmlApplicationEngine:
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('appModel', model)
    engine.load(QUrl.fromLocalFile(str(QML_DIRECTORY / 'Main.qml')))
    if not engine.rootObjects():
        raise RuntimeError('Não foi possível carregar a interface QML do DataQuality.')
    return engine


def launch_gui(*, demo: bool = False, project: str = '', screenshots: str = '') -> int:
    QQuickStyle.setStyle('Basic')
    application = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    family = 'Segoe UI' if sys.platform == 'win32' else 'Helvetica Neue' if sys.platform == 'darwin' else QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
    application.setFont(QFont(family, 11))
    application.setOrganizationName('DataQuality')
    application.setApplicationName('DataQuality')
    icon_name = 'sailboat.svg' if sys.platform == 'win32' else 'app-icon.png'
    application.setWindowIcon(QIcon(str(Path(__file__).parent / 'assets' / icon_name)))
    model = AppViewModel(demo=demo, directory=project)
    engine = create_engine(model)
    window = engine.rootObjects()[0]
    from .native import apply_backdrop
    model._native_backdrop = apply_backdrop(int(window.winId()), model.dark)
    model.appearanceChanged.emit()
    model.appearanceChanged.connect(lambda: apply_backdrop(int(window.winId()), model.dark))
    QTimer.singleShot(0, lambda: model.execute('demo' if demo else 'load'))
    if screenshots:
        if not demo:
            raise ValueError('Screenshots automáticos exigem --demo.')
        from .screenshots import ScreenshotSession
        session = ScreenshotSession(application, model, window, Path(screenshots))
        session.start()
    result = application.exec()
    # Delete QML before its context model, avoiding teardown binding warnings.
    import shiboken6
    shiboken6.delete(engine)
    model.shutdown()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='DataQuality · desktop Qt Quick')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--project', default='')
    parser.add_argument('--screenshots', default='', help='Captura as telas sintéticas e encerra (exige --demo).')
    args = parser.parse_args()
    return launch_gui(demo=args.demo, project=args.project, screenshots=args.screenshots)


if __name__ == '__main__':
    raise SystemExit(main())
