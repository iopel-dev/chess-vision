"""Обёртки над WinAPI: DPI, прозрачные окна, исключение из захвата,
перечисление окон и захват окна через GDI (PrintWindow)."""
import ctypes
import os
import sys

import numpy as np

IS_WIN = sys.platform == "win32"

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

if IS_WIN:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    dwmapi = ctypes.windll.dwmapi

    HWND, HDC, HBITMAP, HGDIOBJ = wintypes.HWND, wintypes.HDC, wintypes.HBITMAP, wintypes.HGDIOBJ
    user32.GetParent.restype = HWND
    user32.GetParent.argtypes = [HWND]
    user32.GetWindowLongW.argtypes = [HWND, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowDisplayAffinity.argtypes = [HWND, wintypes.DWORD]
    user32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowDC.restype = HDC
    user32.GetWindowDC.argtypes = [HWND]
    user32.GetDC.restype = HDC
    user32.GetDC.argtypes = [HWND]
    user32.ReleaseDC.argtypes = [HWND, HDC]
    user32.PrintWindow.argtypes = [HWND, HDC, wintypes.UINT]
    user32.IsWindow.argtypes = [HWND]
    user32.IsWindowVisible.argtypes = [HWND]
    user32.IsIconic.argtypes = [HWND]
    user32.GetWindowTextLengthW.argtypes = [HWND]
    user32.GetWindowTextW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetForegroundWindow.restype = HWND
    user32.WindowFromPoint.restype = HWND
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.GetAncestor.restype = HWND
    user32.GetAncestor.argtypes = [HWND, wintypes.UINT]
    gdi32.CreateCompatibleDC.restype = HDC
    gdi32.CreateCompatibleDC.argtypes = [HDC]
    gdi32.CreateCompatibleBitmap.restype = HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = [HDC, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = HGDIOBJ
    gdi32.SelectObject.argtypes = [HDC, HGDIOBJ]
    gdi32.DeleteObject.argtypes = [HGDIOBJ]
    gdi32.DeleteDC.argtypes = [HDC]
    gdi32.BitBlt.argtypes = [HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    gdi32.GetDIBits.argtypes = [HDC, HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                ctypes.c_void_p, wintypes.UINT]
    dwmapi.DwmGetWindowAttribute.argtypes = [HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

OWN_PID = os.getpid()


# ---------------------------------------------------------------- окна Tk
def set_dpi_aware():
    """Чтобы координаты Tk, GDI и скриншота совпадали в физических пикселях."""
    if not IS_WIN:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _hwnd(widget) -> int:
    widget.update_idletasks()
    hwnd = user32.GetParent(widget.winfo_id())
    return hwnd or widget.winfo_id()


def make_click_through(widget):
    """Мышь проходит сквозь окно (оверлей не мешает играть)."""
    if not IS_WIN:
        return
    hwnd = _hwnd(widget)
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                          style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)


def exclude_from_capture(widget) -> bool:
    """Окно не попадает в скриншоты (Windows 10 2004+). True, если получилось."""
    if not IS_WIN:
        return False
    try:
        return bool(user32.SetWindowDisplayAffinity(_hwnd(widget), WDA_EXCLUDEFROMCAPTURE))
    except Exception:
        return False


# ---------------------------------------------------------------- внешние окна
def window_pid(hwnd) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def window_title(hwnd) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def window_rect(hwnd):
    """(left, top, width, height) окна в экранных координатах."""
    r = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def window_usable(hwnd) -> bool:
    return bool(hwnd) and bool(user32.IsWindow(hwnd)) and bool(user32.IsWindowVisible(hwnd)) \
        and not user32.IsIconic(hwnd)


def _cloaked(hwnd) -> bool:
    val = ctypes.c_int(0)
    try:
        dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(val), ctypes.sizeof(val))  # DWMWA_CLOAKED
    except Exception:
        return False
    return val.value != 0


def list_windows(title_filter=None, min_size=200):
    """Видимые окна верхнего уровня (кроме своих), активное — первым, дальше по Z-порядку."""
    found = []

    def cb(hwnd, _):
        if not window_usable(hwnd) or window_pid(hwnd) == OWN_PID or _cloaked(hwnd):
            return True
        title = window_title(hwnd)
        if not title:
            return True
        if title_filter and title_filter.lower() not in title.lower():
            return True
        r = window_rect(hwnd)
        if r and r[2] >= min_size and r[3] >= min_size:
            found.append((hwnd, title))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    fg = user32.GetForegroundWindow()
    found.sort(key=lambda t: t[0] != fg)
    return found


def capture_window(hwnd):
    """Снимок окна через GDI PrintWindow — работает, даже если окно перекрыто другими.
    -> BGR numpy или None."""
    r = window_rect(hwnd)
    if r is None or r[2] <= 0 or r[3] <= 0:
        return None
    w, h = r[2], r[3]
    wdc = user32.GetWindowDC(hwnd)
    if not wdc:
        return None
    mdc = gdi32.CreateCompatibleDC(wdc)
    bmp = gdi32.CreateCompatibleBitmap(wdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    try:
        if not user32.PrintWindow(hwnd, mdc, 2):          # PW_RENDERFULLCONTENT (Chrome/Edge/GPU)
            gdi32.BitBlt(mdc, 0, 0, w, h, wdc, 0, 0, 0x00CC0020)
        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth, bmi.biHeight = w, -h                  # сверху вниз
        bmi.biPlanes, bmi.biBitCount = 1, 32
        buf = ctypes.create_string_buffer(w * h * 4)
        if not gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0):
            return None
        return np.frombuffer(buf, np.uint8).reshape(h, w, 4)[:, :, :3].copy()
    finally:
        gdi32.SelectObject(mdc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(hwnd, wdc)


def top_windows_at(points):
    """Для каждой точки экрана — видимое чужое окно верхнего уровня, которое её накрывает
    (по Z-порядку; свои окна и прозрачные для мыши оверлеи пропускаются). -> [hwnd или None]"""
    wins = []

    def cb(hwnd, _):
        if not window_usable(hwnd) or window_pid(hwnd) == OWN_PID or _cloaked(hwnd):
            return True
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if ex & WS_EX_TRANSPARENT and ex & WS_EX_LAYERED:
            return True
        r = window_rect(hwnd)
        if r and r[2] > 0 and r[3] > 0:
            wins.append((hwnd, r))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    out = []
    for px, py in points:
        out.append(next((h for h, (x, y, w, hh) in wins if x <= px < x + w and y <= py < y + hh), None))
    return out


def root_window_at(x, y):
    hwnd = user32.WindowFromPoint(wintypes.POINT(int(x), int(y)))
    return user32.GetAncestor(hwnd, 2) if hwnd else None   # GA_ROOT


def region_visible(hwnd, region) -> bool:
    """Видна ли область доски окна hwnd на экране (не перекрыта чужими окнами)."""
    x, y, s, _ = region
    pts = [(x + s * fx, y + s * fy) for fx, fy in ((.5, .5), (.15, .15), (.85, .15), (.15, .85), (.85, .85))]
    ok = 0
    for px, py in pts:
        root = root_window_at(px, py)
        if root == hwnd or (root and window_pid(root) == OWN_PID):
            ok += 1
    return ok >= 3
