"""--gdi: подсветка рисуется средствами GDI (перья, кисти, Polygon, TextOut).

Основной режим — нативное Win32 layered-окно (без Tk):
  * GDI рисует рамки/стрелки/номера в битмап в памяти, окно выводит его в WM_PAINT;
  * прозрачность — цветовым ключом (SetLayeredWindowAttributes);
  * DWM сам компонует окно, поэтому рисунок НЕ стирается, когда браузер
    под ним перерисовывается, и не мерцает;
  * окно исключено из захвата экрана (SetWindowDisplayAffinity), поэтому
    стрелки не мешают распознаванию и рисуются всегда;
  * мышь проходит сквозь окно (WS_EX_TRANSPARENT).

Запасной режим (если окно создать не удалось) — рисование прямо на экране
через GetDC(NULL) с постоянной перерисовкой.
"""
import ctypes
import threading
import time
from ctypes import wintypes

from .config import BANNER_BG, GREENS, banner_height, banner_layout

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

HDC, HGDIOBJ, HWND = wintypes.HDC, wintypes.HGDIOBJ, wintypes.HWND
LRESULT = ctypes.c_ssize_t

gdi32.CreatePen.restype = HGDIOBJ
gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.COLORREF]
gdi32.CreateSolidBrush.restype = HGDIOBJ
gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
gdi32.GetStockObject.restype = HGDIOBJ
gdi32.GetStockObject.argtypes = [ctypes.c_int]
gdi32.SelectObject.restype = HGDIOBJ
gdi32.SelectObject.argtypes = [HDC, HGDIOBJ]
gdi32.DeleteObject.argtypes = [HGDIOBJ]
gdi32.Rectangle.argtypes = [HDC] + [ctypes.c_int] * 4
gdi32.Ellipse.argtypes = [HDC] + [ctypes.c_int] * 4
gdi32.MoveToEx.argtypes = [HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
gdi32.LineTo.argtypes = [HDC, ctypes.c_int, ctypes.c_int]
gdi32.Polygon.argtypes = [HDC, ctypes.POINTER(wintypes.POINT), ctypes.c_int]
gdi32.SetBkMode.argtypes = [HDC, ctypes.c_int]
gdi32.SetTextColor.argtypes = [HDC, wintypes.COLORREF]
gdi32.SetTextAlign.argtypes = [HDC, wintypes.UINT]
gdi32.GetTextExtentPoint32W.argtypes = [HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.SIZE)]
gdi32.TextOutW.argtypes = [HDC, ctypes.c_int, ctypes.c_int, wintypes.LPCWSTR, ctypes.c_int]
gdi32.CreateFontW.restype = HGDIOBJ
gdi32.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
gdi32.CreateCompatibleDC.restype = HDC
gdi32.CreateCompatibleDC.argtypes = [HDC]
gdi32.DeleteDC.argtypes = [HDC]
user32.GetDC.restype = HDC
user32.GetDC.argtypes = [HWND]
user32.ReleaseDC.argtypes = [HWND, HDC]
user32.RedrawWindow.argtypes = [HWND, ctypes.POINTER(wintypes.RECT), wintypes.HANDLE, wintypes.UINT]
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.CreateWindowExW.restype = HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.DestroyWindow.argtypes = [HWND]
user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
user32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                wintypes.UINT]
user32.SetWindowDisplayAffinity.argtypes = [HWND, wintypes.DWORD]
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]


user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]

PS_SOLID, PS_GEOMETRIC, PS_ENDCAP_ROUND = 0, 0x00010000, 0
NULL_BRUSH, NULL_PEN = 5, 8
RDW = 0x0001 | 0x0004 | 0x0080 | 0x0100     # INVALIDATE | ERASE | ALLCHILDREN | UPDATENOW
WS_POPUP = 0x80000000
WS_EX = 0x00080000 | 0x00000020 | 0x00000008 | 0x00000080 | 0x08000000  # LAYERED|TRANSPARENT|TOPMOST|TOOLWINDOW|NOACTIVATE
HWND_TOPMOST = HWND(-1)
SWP_FLAGS = 0x0001 | 0x0002 | 0x0010        # NOSIZE | NOMOVE | NOACTIVATE
CLASS_NAME = "ChessVisionGdiOverlay"
KEY = 0xFE00FF                              # COLORREF прозрачного цвета (#ff00fe)
LWA_COLORKEY = 0x1
WM_PAINT, WM_ERASEBKGND, WM_NCHITTEST, HTTRANSPARENT = 0x000F, 0x0014, 0x0084, -1
SRCCOPY = 0x00CC0020


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", HDC), ("fErase", wintypes.BOOL), ("rcPaint", wintypes.RECT),
                ("fRestore", wintypes.BOOL), ("fIncUpdate", wintypes.BOOL), ("rgbReserved", ctypes.c_byte * 32)]


user32.BeginPaint.restype = HDC
user32.BeginPaint.argtypes = [HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.EndPaint.argtypes = [HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.InvalidateRect.argtypes = [HWND, ctypes.c_void_p, wintypes.BOOL]
user32.UpdateWindow.argtypes = [HWND]
user32.SetLayeredWindowAttributes.argtypes = [HWND, wintypes.COLORREF, ctypes.c_ubyte, wintypes.DWORD]
user32.FillRect.argtypes = [HDC, ctypes.POINTER(wintypes.RECT), HGDIOBJ]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [HDC, ctypes.c_int, ctypes.c_int]
gdi32.BitBlt.argtypes = [HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
OUTLINE = "#0b3d0b"


def _rgb(hexcolor: str) -> int:
    h = hexcolor.lstrip("#")
    return int(h[0:2], 16) | (int(h[2:4], 16) << 8) | (int(h[4:6], 16) << 16)


def paint(hdc, x0, y0, s, flipped, moves, arrows, marks=()):
    """Рисует подсветку GDI-примитивами в hdc; доска занимает квадрат (x0, y0, s)."""
    cs = s / 8
    objs = []
    orig_pen = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_PEN))
    orig_brush = gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_BRUSH))
    # Segoe UI Symbol: в нём есть и цифры, и значки вердиктов (★ ≡)
    font = gdi32.CreateFontW(-max(9, int(cs * 0.2)), 0, 0, 0, 700, 0, 0, 0, 1, 0, 0, 3, 0, "Segoe UI Symbol")
    objs.append(font)
    orig_font = gdi32.SelectObject(hdc, font)
    try:
        gdi32.SetBkMode(hdc, 1)   # TRANSPARENT

        def center(sq):
            f, r = sq % 8, sq // 8
            col, row = (7 - f, r) if flipped else (f, 7 - r)
            return x0 + (col + 0.5) * cs, y0 + (row + 0.5) * cs

        def pen(width, color, geometric=False):
            p = gdi32.CreatePen((PS_GEOMETRIC | PS_ENDCAP_ROUND) if geometric else PS_SOLID, width, color)
            objs.append(p)
            return p

        def brush(color):
            b = gdi32.CreateSolidBrush(color)
            objs.append(b)
            return b

        # (ход, цвет, толщина рамки, толщина линии, полуширина наконечника, метка, цвет метки,
        #  угол метки, стрелка?) — вердикты рисуются первыми, под зелёными подсказками.
        # Ошибка/зевок — стрелкой; лучший/блестящий/теория — только значком на поле хода.
        items = [(m, _rgb(col), 0.05, 0.12, 0.19, sign, _rgb("#ffffff"), -1, arrow)
                 for m, col, sign, arrow in marks]
        for i in reversed(range(len(moves))):
            items.append((moves[i], _rgb(GREENS[min(i, len(GREENS) - 1)]),
                          0.07 if i == 0 else 0.045, 0.17 if i == 0 else 0.1, 0.24 if i == 0 else 0.19,
                          str(i + 1), _rgb(OUTLINE), 1, True))
        gdi32.SetTextAlign(hdc, 6)        # TA_CENTER | TA_TOP
        for m, color, fw, lw, hw, label, label_color, corner, has_arrow in items:
            # рамки клеток «откуда» и «куда» (у значков — только «куда»)
            w = max(3, int(cs * fw)) if arrows else max(2, int(cs * 0.035))
            gdi32.SelectObject(hdc, pen(w, color))
            gdi32.SelectObject(hdc, gdi32.GetStockObject(NULL_BRUSH))
            for sq in ((m.from_square, m.to_square) if has_arrow else (m.to_square,)):
                cx, cy = center(sq)
                h = cs / 2 - w / 2
                gdi32.Rectangle(hdc, int(cx - h), int(cy - h), int(cx + h) + 1, int(cy + h) + 1)
            if not arrows:
                continue
            (ax, ay), (bx, by) = center(m.from_square), center(m.to_square)
            if has_arrow:
                # стрелка: толстая линия + треугольный наконечник
                dx, dy = bx - ax, by - ay
                ln = max(1.0, (dx * dx + dy * dy) ** 0.5)
                ux, uy = dx / ln, dy / ln
                head = cs * 0.4
                hx, hy = bx - ux * head * 0.9, by - uy * head * 0.9
                gdi32.SelectObject(hdc, pen(max(3, int(cs * lw)), color, geometric=True))
                gdi32.MoveToEx(hdc, int(ax), int(ay), None)
                gdi32.LineTo(hdc, int(hx), int(hy))
                half = cs * hw
                bx2, by2 = bx - ux * cs * 0.05, by - uy * cs * 0.05
                hx, hy = bx - ux * head, by - uy * head
                pts = (wintypes.POINT * 3)(wintypes.POINT(int(bx2), int(by2)),
                                           wintypes.POINT(int(hx - uy * half), int(hy + ux * half)),
                                           wintypes.POINT(int(hx + uy * half), int(hy - ux * half)))
                gdi32.SelectObject(hdc, pen(1, color))
                gdi32.SelectObject(hdc, brush(color))
                gdi32.Polygon(hdc, pts, 3)
            # метка в кружке в углу клетки назначения: номер подсказки или значок вердикта
            r0 = cs * 0.16
            cx, cy = bx + corner * cs * 0.3, by - corner * cs * 0.3   # подсказки — вверху справа, вердикты — внизу слева
            gdi32.SelectObject(hdc, pen(max(1, int(cs * 0.02)), _rgb(OUTLINE)))
            gdi32.SelectObject(hdc, brush(color))
            gdi32.Ellipse(hdc, int(cx - r0), int(cy - r0), int(cx + r0), int(cy + r0))
            gdi32.SetTextColor(hdc, label_color)
            gdi32.TextOutW(hdc, int(cx), int(cy - cs * 0.1), label, len(label))
    finally:
        gdi32.SelectObject(hdc, orig_pen)
        gdi32.SelectObject(hdc, orig_brush)
        gdi32.SelectObject(hdc, orig_font)
        for o in objs:
            gdi32.DeleteObject(o)


def _banner_font(h):
    return gdi32.CreateFontW(-max(12, int(h * 0.6)), 0, 0, 0, 700, 0, 0, 0, 1, 0, 0, 3, 0, "Segoe UI Symbol")


def banner_text_width(hdc, h, segments) -> int:
    font = _banner_font(h)
    old = gdi32.SelectObject(hdc, font)
    size, total = wintypes.SIZE(), 0
    for text, _ in segments:
        gdi32.GetTextExtentPoint32W(hdc, text, len(text), ctypes.byref(size))
        total += size.cx
    gdi32.SelectObject(hdc, old)
    gdi32.DeleteObject(font)
    return total


def paint_banner(hdc, x, y, w, h, segments):
    """Строка «Running Live analysis... Bestmove is ...» на тёмной плашке."""
    objs = []
    bg = gdi32.CreateSolidBrush(_rgb(BANNER_BG))
    objs.append(bg)
    user32.FillRect(hdc, ctypes.byref(wintypes.RECT(int(x), int(y), int(x + w), int(y + h))), bg)
    font = _banner_font(h)
    objs.append(font)
    old_font = gdi32.SelectObject(hdc, font)
    try:
        gdi32.SetBkMode(hdc, 1)
        gdi32.SetTextAlign(hdc, 0 | 24)            # TA_LEFT | TA_BASELINE
        size = wintypes.SIZE()
        tx = x + 8
        for text, color in segments:
            gdi32.SetTextColor(hdc, _rgb(color))
            gdi32.TextOutW(hdc, int(tx), int(y + h * 0.72), text, len(text))
            gdi32.GetTextExtentPoint32W(hdc, text, len(text), ctypes.byref(size))
            tx += size.cx
    finally:
        gdi32.SelectObject(hdc, old_font)
        for o in objs:
            gdi32.DeleteObject(o)


class GdiOverlay:
    def __init__(self, arrows_allowed):
        """arrows_allowed() -> bool: можно ли рисовать стрелки в запасном режиме
        (рисунок прямо на экране попадает в скриншоты)."""
        self.arrows_allowed = arrows_allowed
        self.safe = False
        self.mode = "?"
        self._lock = threading.Lock()
        self._state = None          # (region, flipped, moves, marks)
        self._stop = False
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="gdi-overlay")
        self._thread.start()
        self._ready.wait(3)

    def show(self, region, flipped, moves, marks=(), banner=None):
        """moves — лучшие ходы (зелёные); marks — [(ход, цвет, знак)] вердикты сделанным ходам;
        banner — строка над доской [(текст, цвет), ...]."""
        with self._lock:
            self._state = ((tuple(region), flipped, tuple(moves), tuple(marks), banner)
                           if region and (moves or marks or banner) else None)

    def hide(self):
        with self._lock:
            self._state = None

    def destroy(self):
        self._stop = True
        self._thread.join(1.5)

    def _get_state(self):
        with self._lock:
            return self._state

    def _run(self):
        hwnd = None
        try:
            hwnd = self._create_window()
        except Exception:
            hwnd = None
        if hwnd:
            self.mode = "layered"
            self._ready.set()
            try:
                self._layered_loop(hwnd)
            finally:
                user32.DestroyWindow(hwnd)
        else:
            self.mode = "screen"
            self._ready.set()
            self._screen_loop()

    # ---------------------------------------------------------------- layered-окно
    def _create_window(self):
        hinst = kernel32.GetModuleHandleW(None)
        self._cache = None              # (mem_dc, bitmap, old_obj, size) — готовый GDI-рисунок

        def wndproc(h, m, w, l):
            if m == WM_ERASEBKGND:
                return 1
            if m == WM_NCHITTEST:
                return HTTRANSPARENT
            if m == WM_PAINT:
                ps = PAINTSTRUCT()
                hdc = user32.BeginPaint(h, ctypes.byref(ps))
                if self._cache:
                    mdc, _, _, (cw, ch) = self._cache
                    gdi32.BitBlt(hdc, 0, 0, cw, ch, mdc, 0, 0, SRCCOPY)
                user32.EndPaint(h, ctypes.byref(ps))
                return 0
            return user32.DefWindowProcW(h, m, w, l)

        self._wndproc = WNDPROC(wndproc)          # держим ссылку, иначе её съест GC
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = CLASS_NAME
        user32.RegisterClassExW(ctypes.byref(wc))     # повторная регистрация просто вернёт ошибку
        hwnd = user32.CreateWindowExW(WS_EX, CLASS_NAME, "Chess Vision overlay", WS_POPUP,
                                      0, 0, 1, 1, None, None, hinst, None)
        if hwnd:
            # цветовой ключ: всё цвета KEY становится прозрачным (так окно можно исключить из захвата)
            user32.SetLayeredWindowAttributes(hwnd, KEY, 0, LWA_COLORKEY)
        return hwnd

    def _layered_loop(self, hwnd):
        msg = wintypes.MSG()
        drawn, shown, last_top = None, False, 0.0
        excluded = False
        while not self._stop:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):   # PM_REMOVE
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            state = self._get_state()
            # окно исключено из захвата -> стрелки не мешают распознаванию, рисуем всегда
            arrows = excluded or bool(self.arrows_allowed())
            self.safe = arrows
            key = (state, arrows)
            if key != drawn:
                drawn = key
                if state is None:
                    user32.ShowWindow(hwnd, 0)                  # SW_HIDE
                    shown = False
                else:
                    try:
                        self._render(hwnd, *state, arrows=arrows)
                        if not shown:
                            user32.ShowWindow(hwnd, 4)          # SW_SHOWNOACTIVATE
                            shown = True
                        if not excluded and user32.SetWindowDisplayAffinity(hwnd, 0x11):
                            excluded = True                     # WDA_EXCLUDEFROMCAPTURE
                            drawn = None                        # перерисовать уже со стрелками
                    except Exception:
                        drawn = None
            if shown and time.time() - last_top > 0.5:          # не дать другим окнам «поверх всех» перекрыть нас
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_FLAGS)
                last_top = time.time()
            time.sleep(0.02)
        user32.ShowWindow(hwnd, 0)
        self._free_cache()

    def _free_cache(self):
        if self._cache:
            mdc, bmp, old, _ = self._cache
            gdi32.SelectObject(mdc, old)
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mdc)
            self._cache = None

    def _render(self, hwnd, region, flipped, moves, marks, banner, arrows):
        s = int(region[2])
        screen_dc = user32.GetDC(None)
        text_w = banner_text_width(screen_dc, banner_height(s), banner) if banner else 0
        wx, wy, ww, wh, off, bar_y, bar_h = banner_layout(region, bool(banner), text_w)
        try:
            mdc = gdi32.CreateCompatibleDC(screen_dc)
            bmp = gdi32.CreateCompatibleBitmap(screen_dc, ww, wh)
        finally:
            user32.ReleaseDC(None, screen_dc)
        old = gdi32.SelectObject(mdc, bmp)
        bg = gdi32.CreateSolidBrush(KEY)
        user32.FillRect(mdc, ctypes.byref(wintypes.RECT(0, 0, ww, wh)), bg)
        gdi32.DeleteObject(bg)
        paint(mdc, 0, off, s, flipped, moves, arrows, marks)
        if banner:
            paint_banner(mdc, 0, bar_y, ww, bar_h, banner)
        self._free_cache()
        self._cache = (mdc, bmp, old, (ww, wh))
        user32.SetWindowPos(hwnd, HWND_TOPMOST, wx, wy, ww, wh, 0x0010)   # SWP_NOACTIVATE
        user32.InvalidateRect(hwnd, None, False)
        user32.UpdateWindow(hwnd)

    # ---------------------------------------------------------------- запасной режим
    def _screen_loop(self):
        """Рисование прямо на экране. Стирается перерисовкой окон, поэтому повторяется
        ~60 раз в секунду; в скриншот попадает, поэтому стрелки — только если можно."""
        drawn = None
        while not self._stop:
            state = self._get_state()
            arrows = bool(self.arrows_allowed())
            self.safe = arrows
            key = (state, arrows)
            if key != drawn:
                if drawn and drawn[0]:
                    self._erase(drawn[0][0])
                    time.sleep(0.03)
                drawn = key
            if state:
                region, flipped, moves, marks, banner = state
                hdc = user32.GetDC(None)
                if hdc:
                    try:
                        paint(hdc, region[0], region[1], region[2], flipped, moves, arrows, marks)
                        if banner:
                            tw = banner_text_width(hdc, banner_height(region[2]), banner)
                            wx, wy, ww, wh, off, bar_y, bar_h = banner_layout(region, True, tw)
                            paint_banner(hdc, wx, wy + bar_y, ww, bar_h, banner)
                    except Exception:
                        pass
                    finally:
                        user32.ReleaseDC(None, hdc)
            time.sleep(0.016)
        if drawn and drawn[0]:
            self._erase(drawn[0][0])

    @staticmethod
    def _erase(region):
        x, y, s, _ = region
        pad = int(s * 0.12)
        r = wintypes.RECT(x - pad, y - pad, x + s + pad, y + s + pad)
        user32.RedrawWindow(None, ctypes.byref(r), None, RDW)
