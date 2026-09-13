"""Deterministic visual QA over every page, two themes, and minimum size."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QObject, QTimer


class ScreenshotSession(QObject):
    def __init__(self, application, model, window, directory: Path) -> None:
        super().__init__(application)
        self.application, self.model, self.window, self.directory = application, model, window, directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._index = 0
        self._previous = (model.dark, model.reducedMotion)
        self._cases = [(name, page, dark, width, height) for dark in (True, False)
                       for page, name in enumerate(('overview', 'connections', 'discovery', 'mapping', 'validation', 'history', 'settings', 'result'))
                       for width, height in ((1280, 800), (1024, 700))]
        self.timer = QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.ready)

    def start(self) -> None:
        self.timer.start()

    def ready(self) -> None:
        if self.model.state['busy']:
            return
        if not self.model.state['hasResult']:
            (self.directory / 'failure.txt').write_text(self.model.state['error'] + '\n' + self.model.state['details'], encoding='utf-8')
            self.timer.stop()
            self.application.exit(2)
            return
        self.timer.stop()
        self.model.setReducedMotion(True)
        self.next()

    def next(self) -> None:
        if self._index == len(self._cases):
            self.model.setDark(self._previous[0])
            self.model.setReducedMotion(self._previous[1])
            self.application.quit()
            return
        name, page, dark, width, height = self._cases[self._index]
        self.model.setDark(dark)
        self.window.setWidth(width)
        self.window.setHeight(height)
        self.model.navigate(page)
        QTimer.singleShot(250, self.capture)

    def capture(self) -> None:
        name, page, dark, width, height = self._cases[self._index]
        path = self.directory / f'{name}-{"dark" if dark else "light"}-{width}.png'
        picture = self.window.grabWindow()
        if picture.isNull() or not picture.save(str(path)):
            self.application.exit(3)
            return
        self._index += 1
        self.next()
