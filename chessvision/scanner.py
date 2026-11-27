"""Фоновый поток: захват -> поиск доски -> распознавание -> трекер.

Два источника картинки:
  * экран целиком (mss), по умолчанию;
  * --external-window: любое окно верхнего уровня, снимок через GDI PrintWindow
    (доска видна, даже если окно перекрыто), подсветка ездит вместе с окном.

Чёрный список браузеров — chessvision/blacklist.py (по умолчанию выключен).
"""
import queue
import threading
import time

import chess

from . import blacklist, config, winutil
from .capture import ScreenGrabber
from .detector import find_board
from .recognizer import CalibrationError, Recognizer
from .tracker import PositionTracker


class Scanner(threading.Thread):
    def __init__(self, on_position, auto_find=False, auto_find_time=5.0,
                 external=False, window_filter=None):
        super().__init__(daemon=True, name="scanner")
        self.on_position = on_position          # вызывается с chess.Board или None
        self.auto_find = auto_find
        self.auto_find_time = max(0.5, float(auto_find_time))
        self.external = external and winutil.IS_WIN
        self.window_filter = window_filter
        self.cmds = queue.Queue()
        self.lock = threading.Lock()
        self.region = None                      # (left, top, size, size) на экране
        self.visible = True                     # доска не перекрыта чужим окном
        self.auto_region = True
        self.hwnd = None                        # окно с доской (--external-window)
        self.win_size = None
        self.board_rel = None                   # (x, y, size) доски внутри окна
        self.recognizer = None
        self.flipped = False
        self.status = "Запуск..."
        self.tracker = PositionTracker()
        self.paused = False
        self.fails = 0
        self.last_detect = 0.0
        self.blocked = None                     # почему последняя найденная доска отклонена
        self._halt = False
        if config.CALIB_FILE.exists():
            try:
                self.recognizer, self.flipped = Recognizer.load(config.CALIB_FILE)
            except Exception:
                self.recognizer = None
        self.tracker.default_turn = chess.BLACK if self.flipped else chess.WHITE

    # ---------- API для GUI ----------
    def command(self, name, *args):
        self.cmds.put((name, args))

    def snapshot(self):
        with self.lock:
            b = self.tracker.board.copy(stack=False) if self.tracker.board is not None else None
            region = self.region if self.visible else None
            return b, region, self.flipped, self.status

    def game(self):
        """-> (начальная позиция, ходы) отслеживаемой партии — для разбора; None, если доски нет."""
        with self.lock:
            b = self.tracker.board
            if b is None:
                return None
            return b.root(), list(b.move_stack)

    def stop(self):
        self._halt = True

    # ---------- поток ----------
    def run(self):
        self.grab = ScreenGrabber()
        self._detect()
        while not self._halt:
            t0 = time.time()
            try:
                while True:
                    name, args = self.cmds.get_nowait()
                    getattr(self, "_cmd_" + name)(*args)
            except queue.Empty:
                pass
            if not self.paused:
                # периодический автопоиск (--auto-find) или повтор, пока доска не найдена
                due = time.time() - self.last_detect >= self.auto_find_time
                if due and (self.region is None or (self.auto_find and self.auto_region)):
                    self._detect(quick=self.region is not None)
                if self.region is not None:
                    try:
                        self._scan()
                    except Exception as e:      # не роняем поток из-за одного кадра
                        self._set_status(f"Ошибка: {e}")
            time.sleep(max(0.02, config.SCAN_INTERVAL - (time.time() - t0)))

    def _set_status(self, s):
        with self.lock:
            self.status = s

    # ---------- поиск доски ----------
    def _detect(self, quick=False):
        """quick=True: при автопоиске сначала проверяем текущее окно (быстро)."""
        self.last_detect = time.time()
        if not quick:
            self._set_status("Ищу доску..." if not self.external else "Ищу доску во всех окнах...")
        self.blocked = None
        found = self._detect_window(quick) if self.external else self._detect_screen()
        if not found and not quick:
            with self.lock:
                self.region = None
            if self.blocked:
                self._set_status(blacklist.MESSAGE)
            else:
                self._set_status("Доска не найдена. Откройте доску или выделите её вручную"
                                 + (f" (повтор каждые {self.auto_find_time:g} с)" if self.auto_find else "."))
        elif not found and quick:
            return self._detect(quick=False) if self.external else False
        return found

    def _detect_screen(self):
        left, top, _, _ = self.grab.virtual_screen()
        rect = find_board(self.grab.grab())
        if rect is None:
            return False
        x, y, s, _ = rect
        region = (left + x, top + y, s, s)
        self.blocked = blacklist.blocked_region(region)
        if self.blocked:
            return False
        prev = self.region
        self._set_region(region)
        if prev is None or max(abs(a - b) for a, b in zip(prev, region)) > 3:
            self._set_status(f"Доска найдена на экране: {s}x{s} px")
        return True

    def _detect_window(self, quick):
        if quick and winutil.window_usable(self.hwnd):
            candidates = [(self.hwnd, winutil.window_title(self.hwnd))]
        else:
            candidates = winutil.list_windows(self.window_filter)
        for hwnd, title in candidates:
            if blacklist.blocked_window(hwnd):      # браузеры даже не снимаем
                self.blocked = blacklist.MESSAGE
                continue
            img = winutil.capture_window(hwnd)
            if img is None:
                continue
            rect = find_board(img)
            if rect is None:
                continue
            x, y, s, _ = rect
            wr = winutil.window_rect(hwnd)
            with self.lock:
                if hwnd != self.hwnd:
                    self.tracker.reset()
                self.hwnd, self.win_size, self.board_rel = hwnd, wr[2:], (x, y, s)
                self.region = (wr[0] + x, wr[1] + y, s, s)
                self.auto_region = True
            self.fails = 0
            if not quick:
                self._set_status(f"Доска найдена в окне «{title[:40]}»: {s}x{s} px")
            return True
        return False

    def _set_region(self, region):
        with self.lock:
            self.region = region
            self.auto_region = True
            self.visible = True
        self.fails = 0

    # ---------- кадр ----------
    def _grab_board(self):
        if not self.external:
            return self.grab.grab(self.region)
        if not winutil.window_usable(self.hwnd):
            with self.lock:
                self.visible = False
            self._set_status("Окно с доской свёрнуто или закрыто")
            if not self.hwnd or not winutil.user32.IsWindow(self.hwnd):
                self._detect()
            return None
        wr = winutil.window_rect(self.hwnd)
        if wr is None:
            return None
        if tuple(wr[2:]) != tuple(self.win_size):   # размер окна изменился -> доска переехала
            self._detect(quick=True)
            return None
        img = winutil.capture_window(self.hwnd)
        if img is None:
            return None
        x, y, s = self.board_rel
        region = (wr[0] + x, wr[1] + y, s, s)
        with self.lock:
            self.region = region
            self.visible = winutil.region_visible(self.hwnd, region)
        return img[y:y + s, x:x + s]

    def _check_blacklist(self) -> bool:
        """Каждый кадр: доска не в окне браузера? Иначе забываем доску и партию."""
        if self.external:
            reason = blacklist.blocked_window(self.hwnd)
        else:
            reason = blacklist.blocked_region(self.region)
        if not reason:
            return True
        with self.lock:
            self.region = None
            self.hwnd = None
            self.tracker.reset()
        self.blocked = reason
        self.last_detect = time.time()
        self.on_position(None)
        self._set_status(blacklist.MESSAGE)
        return False

    def _scan(self):
        if not self._check_blacklist():
            return
        img = self._grab_board()
        if img is None:
            return
        if self.recognizer is None:
            try:
                self._calibrate(img)
            except CalibrationError:
                self._set_status("Нужна калибровка: поставьте начальную позицию "
                                 "(новая партия) — откалибруется автоматически")
            return
        placement, unknown = self.recognizer.read(img, self.flipped)
        b = chess.Board(placement)
        kings_ok = len(b.pieces(chess.KING, chess.WHITE)) == 1 and len(b.pieces(chess.KING, chess.BLACK)) == 1
        if unknown > 1 or not kings_ok:
            self.fails += 1
            self._set_status(f"Не распознаётся позиция ({self.fails})")
            if self.fails >= config.REDETECT_AFTER_FAILS and self.auto_region:
                self.fails = 0
                self._detect()
            return
        self.fails = 0
        with self.lock:
            changed = self.tracker.update(placement, self.recognizer.last_mover)
            board = self.tracker.board
        if changed:
            self._publish(board)

    def _publish(self, board):
        if board is None:
            return
        if not board.is_valid():
            self._set_status("Позиция невозможна по правилам (проверьте калибровку / чей ход)")
            self.on_position(None)
            return
        if board.is_game_over():
            self._set_status("Партия окончена: " + board.result())
            self.on_position(None)
            return
        side = "белых" if board.turn else "чёрных"
        self._set_status(f"Слежу за доской. Ход {side}.")
        self.on_position(board.copy())

    def _calibrate(self, img):
        rec, flipped = Recognizer.calibrate(img)
        rec.save(config.CALIB_FILE, flipped)
        with self.lock:
            self.recognizer, self.flipped = rec, flipped
            self.tracker.reset()
            self.tracker.default_turn = chess.BLACK if flipped else chess.WHITE
        self._set_status("Калибровка готова (" + ("чёрные" if flipped else "белые") + " снизу)")

    # ---------- команды ----------
    def _cmd_detect(self):
        self._detect()

    def _cmd_set_region(self, rect):
        """Ручное выделение: уточняем доску внутри выделенной области."""
        x, y, w, h = rect
        m = int(max(w, h) * 0.08)
        if self.external:
            hwnd = winutil.root_window_at(x + w / 2, y + h / 2)
            wr = winutil.window_rect(hwnd) if hwnd else None
            img = winutil.capture_window(hwnd) if wr else None
            if img is not None:
                cl, ct = max(0, x - m - wr[0]), max(0, y - m - wr[1])
                cr, cb = min(wr[2], x + w + m - wr[0]), min(wr[3], y + h + m - wr[1])
                found = find_board(img[ct:cb, cl:cr]) if cr > cl and cb > ct else None
                if found:
                    bx, by, bs = cl + found[0], ct + found[1], found[2]
                else:
                    bx, by, bs = x - wr[0], y - wr[1], min(w, h)
                with self.lock:
                    self.hwnd, self.win_size, self.board_rel = hwnd, wr[2:], (bx, by, bs)
                    self.region = (wr[0] + bx, wr[1] + by, bs, bs)
                    self.auto_region = False
                    self.tracker.reset()
                self.fails = 0
                self._set_status(f"Область задана вручную в окне «{winutil.window_title(hwnd)[:40]}»")
                return
        vl, vt, vw, vh = self.grab.virtual_screen()
        cl, ct = max(vl, x - m), max(vt, y - m)
        cr, cb = min(vl + vw, x + w + m), min(vt + vh, y + h + m)
        found = find_board(self.grab.grab((cl, ct, cr - cl, cb - ct)))
        if found:
            fx, fy, fs, _ = found
            region = (cl + fx, ct + fy, fs, fs)
        else:
            s = min(w, h)
            region = (x, y, s, s)
        self.external = False
        with self.lock:
            self.region = region
            self.visible = True
            self.auto_region = False
            self.tracker.reset()
        self.fails = 0
        self._set_status(f"Область задана вручную: {region[2]}x{region[2]} px")

    def _cmd_calibrate(self):
        if self.region is None and not self._detect():
            return
        if not self._check_blacklist():
            return
        img = self._grab_board()
        if img is None:
            return
        try:
            self._calibrate(img)
        except CalibrationError as e:
            self._set_status(str(e))

    def _cmd_flip(self):
        with self.lock:
            self.flipped = not self.flipped
            self.tracker.reset()
            self.tracker.default_turn = chess.BLACK if self.flipped else chess.WHITE
        if self.recognizer is not None:
            self.recognizer.save(config.CALIB_FILE, self.flipped)

    def _cmd_turn(self, color):
        with self.lock:
            changed = self.tracker.set_turn(color)
            board = self.tracker.board
        if changed:
            self._publish(board)

    def _cmd_pause(self, value):
        self.paused = bool(value)
        if self.paused:
            self._set_status("Пауза")
