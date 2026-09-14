"""Render our sailboat SVG into platform icons. Requires the project's PySide6."""
from __future__ import annotations

from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parents[1] / 'src/sincro/desktop/assets'


def render(name: str, size: int) -> QImage:
    renderer = QSvgRenderer(str(ASSETS / name))
    if not renderer.isValid():
        raise ValueError('Invalid icon SVG')
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'PNG'):
        raise RuntimeError('Unable to encode icon')
    return bytes(data)


def main() -> None:
    render('app-icon.svg', 1024).save(str(ASSETS / 'app-icon.png'))
    sizes = (16, 24, 32, 48, 64, 128, 256)
    # ICO supports PNG frames: transparent sailboat as in the supplied Windows concept.
    frames = [png_bytes(render('sailboat.svg', size)) for size in sizes]
    offset = 6 + len(sizes) * 16
    directory = bytearray(struct.pack('<HHH', 0, 1, len(sizes)))
    for size, data in zip(sizes, frames):
        directory += struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    (ASSETS / 'app-icon.ico').write_bytes(bytes(directory) + b''.join(frames))
    if sys.platform == 'darwin':
        with tempfile.TemporaryDirectory() as temporary:
            iconset = Path(temporary) / 'Sincro.iconset'
            iconset.mkdir()
            for size in (16, 32, 128, 256, 512):
                for scale in (1, 2):
                    suffix = '@2x' if scale == 2 else ''
                    render('app-icon.svg', size * scale).save(str(iconset / f'icon_{size}x{size}{suffix}.png'))
            subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(ASSETS / 'app-icon.icns')], check=True)
    print('Platform icons generated from the vector source.')


if __name__ == '__main__':
    main()
