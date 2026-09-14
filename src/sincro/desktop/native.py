"""Optional Windows 11 system backdrop. Every other platform uses QML fallback."""
from __future__ import annotations
import sys


def apply_backdrop(window_id: int, dark: bool) -> bool:
    if sys.platform != 'win32' or sys.getwindowsversion().build < 22621:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class Margins(ctypes.Structure):
            _fields_ = [('left', ctypes.c_int), ('right', ctypes.c_int),
                        ('top', ctypes.c_int), ('bottom', ctypes.c_int)]

        dwm = ctypes.WinDLL('dwmapi')
        set_attribute = dwm.DwmSetWindowAttribute
        set_attribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        set_attribute.restype = ctypes.c_long
        extend = dwm.DwmExtendFrameIntoClientArea
        extend.argtypes = [wintypes.HWND, ctypes.POINTER(Margins)]
        extend.restype = ctypes.c_long
        dark_value, material = ctypes.c_int(int(dark)), ctypes.c_int(2)  # DWMSBT_MAINWINDOW (Mica)
        set_attribute(window_id, 20, ctypes.byref(dark_value), ctypes.sizeof(dark_value))
        if set_attribute(window_id, 38, ctypes.byref(material), ctypes.sizeof(material)) != 0:
            return False
        return extend(window_id, ctypes.byref(Margins(-1, -1, -1, -1))) == 0
    except (AttributeError, OSError):
        return False
