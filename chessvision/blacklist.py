"""Чёрный список браузеров: если включён, доска в окнах браузеров не распознаётся.

Сейчас выключен (ENABLED = False) — программа работает с любыми окнами.
Чтобы включить: ENABLED = True. Тогда окна браузеров (и программ со встроенным
браузерным движком) пропускаются всегда, и при поиске доски, и на каждом кадре.

Окно считается браузерным, если:
  * его процесс — известный браузер (по имени exe);
  * окно или его дочерние окна — Chromium / Firefox / Internet Explorer
    (по классу окна: ловит и переименованные exe, и Electron-приложения);
  * в нём встроен браузерный движок (процессы msedgewebview2.exe и т.п.).
"""
import ctypes
import os
import time

from . import winutil
from .i18n import tr

BROWSER_EXES = frozenset(name.lower() for name in (
    # Chromium
    "chrome.exe", "chromium.exe", "msedge.exe", "msedgewebview2.exe", "opera.exe", "opera_gx.exe",
    "browser.exe", "yandex.exe", "brave.exe", "vivaldi.exe", "arc.exe", "thorium.exe",
    "iron.exe", "dragon.exe", "epic.exe", "slimjet.exe", "torch.exe", "centbrowser.exe", "coccoc.exe",
    "atom.exe", "sputnik.exe", "amigo.exe", "orbitum.exe", "uran.exe", "chromodo.exe", "maxthon.exe",
    "avastbrowser.exe", "avgbrowser.exe", "ccleanerbrowser.exe", "nortonbrowser.exe", "duckduckgo.exe",
    "ucbrowser.exe", "360chrome.exe", "360se.exe", "qqbrowser.exe", "sogouexplorer.exe",
    "2345explorer.exe", "liebao.exe", "min.exe", "sidekick.exe", "wavebox.exe", "ghostbrowser.exe",
    "srwareiron.exe", "superbird.exe", "blisk.exe", "colibri.exe", "naver whale.exe", "whale.exe",
    "cefsharp.browsersubprocess.exe", "qtwebengineprocess.exe",
    # Firefox и Gecko
    "firefox.exe", "waterfox.exe", "librewolf.exe", "floorp.exe", "zen.exe", "palemoon.exe",
    "basilisk.exe", "seamonkey.exe", "k-meleon.exe", "mullvadbrowser.exe", "tor.exe", "mercury.exe",
    # прочие
    "iexplore.exe", "microsoftedge.exe", "microsoftedgecp.exe", "safari.exe", "falkon.exe",
    "otter-browser.exe", "midori.exe", "netscape.exe", "lunascape.exe",
))
# Классы окон браузерных движков
BROWSER_CLASS_PREFIXES = ("Chrome_WidgetWin_", "Chrome_RenderWidgetHostHWND", "MozillaWindowClass",
                          "MozillaDialogClass", "IEFrame", "Internet Explorer_Server",
                          "Intermediate D3D Window", "CefBrowserWindow")

ENABLED = False      # True — доска в окнах браузеров не распознаётся

MESSAGE = ("Доска в окне браузера: Chess Vision не работает с браузерами и сайтами — "
           "только шахматные программы на компьютере, PGN и Virtual Game Review.")
UNSUPPORTED = "Распознавание доски на экране поддерживается только в Windows."

_CACHE_TTL = 2.0
_cache = {}          # hwnd -> (время, имя браузера или "")
_exe_cache = {}      # pid -> имя exe

if winutil.IS_WIN:
    from ctypes import wintypes

    _k32 = ctypes.windll.kernel32
    _u32 = winutil.user32
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _u32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _u32.EnumChildWindows.argtypes = [wintypes.HWND, winutil.WNDENUMPROC, wintypes.LPARAM]


def process_exe(pid) -> str:
    """Имя exe процесса в нижнем регистре ("" — не удалось узнать)."""
    if pid in _exe_cache:
        return _exe_cache[pid]
    name = ""
    h = _k32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
    if h:
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                name = os.path.basename(buf.value).lower()
        finally:
            _k32.CloseHandle(h)
    if len(_exe_cache) > 512:
        _exe_cache.clear()
    _exe_cache[pid] = name
    return name


def window_class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    _u32.GetClassNameW(hwnd, buf, len(buf))
    return buf.value


def _browser_window(hwnd):
    """Имя браузера/движка, если само окно браузерное, иначе None."""
    exe = process_exe(winutil.window_pid(hwnd))
    if exe in BROWSER_EXES:
        return exe
    cls = window_class(hwnd)
    if cls.startswith(BROWSER_CLASS_PREFIXES):
        return f"{exe or 'window'} ({cls})"
    return None


def blocked_window(hwnd):
    """Окно верхнего уровня hwnd браузерное (или со встроенным браузером)? -> причина или None."""
    if not ENABLED or not winutil.IS_WIN or not hwnd:
        return None
    root = _u32.GetAncestor(hwnd, 2) or hwnd       # GA_ROOT
    now = time.time()
    hit = _cache.get(root)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1] or None
    reason = _browser_window(root)
    if reason is None:
        found = []

        def cb(child, _):
            r = _browser_window(child)
            if r:
                found.append(r)
                return False                        # дальше можно не искать
            return True

        _u32.EnumChildWindows(root, winutil.WNDENUMPROC(cb), 0)
        reason = found[0] if found else None
    if len(_cache) > 256:
        _cache.clear()
    _cache[root] = (now, reason or "")
    return reason


def blocked_region(region):
    """Доска на экране (left, top, size, size) лежит в окне браузера? -> причина или None.
    Окна перебираются по Z-порядку, свои окна (оверлей подсветки) пропускаются.
    Не Windows: окна не определить — при включённом списке распознавание с экрана запрещено."""
    if not ENABLED:
        return None
    if not winutil.IS_WIN:
        return tr(UNSUPPORTED)
    x, y, s, _ = region
    points = [(x + s * fx, y + s * fy) for fx, fy in ((.5, .5), (.2, .2), (.8, .2), (.2, .8), (.8, .8))]
    tops = winutil.top_windows_at(points)
    reasons = [blocked_window(h) for h in tops if h]
    hits = [r for r in reasons if r]
    if tops[0] and blocked_window(tops[0]) or len(hits) >= 3:
        return hits[0]
    return None
