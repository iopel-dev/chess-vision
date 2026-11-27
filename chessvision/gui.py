"""Главное окно: виртуальная копия доски + лучшие ходы Stockfish зелёным."""
import tkinter as tk
from tkinter import ttk

import chess

from . import __version__, config, winutil
from .engine import EngineWorker
from .overlay import Overlay
from .scanner import Scanner
from .explorer import BOOKS, Book
from .selfplay import SPEEDS, SelfPlay

SQ = 64
LIGHT, DARK = "#eeeed2", "#769656"
GLYPH = {"k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}
OUTLINE = {"k": "♔", "q": "♕", "r": "♖", "b": "♗", "n": "♘", "p": "♙"}
PIECE_FONT = ("Segoe UI Symbol", int(SQ * 0.62))


def verdict_text(j) -> str:
    who = "белые" if j["white"] else "чёрные"
    kind = j["kind"]
    text = f"{j['san']}{config.MARK_SIGNS[kind]} ({who}): {config.MARK_NAMES[kind]}"
    if kind in config.MARK_ARROW:
        text += ", допускает мат" if j.get("mate") else f", −{j['loss']:.1f}"
    elif kind == "brilliant" and j.get("sac"):
        text += f" — жертва {j['sac']} пешк{'и' if j['sac'] < 5 else 'ек'}"
    elif kind == "book" and j.get("opening"):
        text += f": {j['opening']}"
    return text


class RegionSelector:
    """Полупрозрачное окно на весь экран: протяните рамку вокруг доски."""

    def __init__(self, root, callback):
        self.callback = callback
        from .capture import ScreenGrabber
        left, top, w, h = ScreenGrabber().virtual_screen()
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.3)
        self.win.geometry(f"{w}x{h}+{left}+{top}")
        self.c = tk.Canvas(self.win, bg="black", highlightthickness=0, cursor="crosshair")
        self.c.pack(fill="both", expand=True)
        self.c.create_text(w // 2 - left if left < 0 else w // 2, 40, fill="white",
                           font=("Segoe UI", 20, "bold"),
                           text="Выделите доску мышью  (Esc — отмена)")
        self.start = None
        self.rect = None
        self.c.bind("<ButtonPress-1>", self._press)
        self.c.bind("<B1-Motion>", self._drag)
        self.c.bind("<ButtonRelease-1>", self._release)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.focus_force()

    def _press(self, e):
        self.start = (e.x, e.y, e.x_root, e.y_root)
        self.rect = self.c.create_rectangle(e.x, e.y, e.x, e.y, outline="#00ff40", width=3)

    def _drag(self, e):
        if self.start:
            self.c.coords(self.rect, self.start[0], self.start[1], e.x, e.y)

    def _release(self, e):
        if not self.start:
            return
        x0, y0 = min(self.start[2], e.x_root), min(self.start[3], e.y_root)
        w, h = abs(e.x_root - self.start[2]), abs(e.y_root - self.start[3])
        self.win.destroy()
        if w > 40 and h > 40:
            self.callback((x0, y0, w, h))


def apply_style(root):
    """Тёмная тема ttk для окон программы."""
    style = ttk.Style(root)
    style.theme_use("clam")
    bg, fg = "#262421", "#e8e6e3"
    style.configure(".", background=bg, foreground=fg, font=("Segoe UI", 10))
    style.configure("TButton", padding=6, background="#3c3a37", foreground=fg)
    style.map("TButton", background=[("active", "#4f4c48")])
    style.configure("TCheckbutton", background=bg, foreground=fg)
    style.map("TCheckbutton", background=[("active", bg)])
    style.configure("TCombobox", fieldbackground="#3c3a37", background="#3c3a37",
                    foreground=fg, arrowcolor=fg)
    style.map("TCombobox", fieldbackground=[("readonly", "#3c3a37")],
              foreground=[("readonly", fg)], selectbackground=[("readonly", "#3c3a37")],
              selectforeground=[("readonly", fg)])
    root.option_add("*TCombobox*Listbox.background", "#3c3a37")
    root.option_add("*TCombobox*Listbox.foreground", fg)
    style.configure("Eval.TLabel", font=("Segoe UI", 22, "bold"), foreground="#00e639")


class BoardView:
    """Рисование виртуальной доски; нужны self.canvas и self.evalbar."""

    def _draw_board(self, board, flipped, moves, marks=()):
        c = self.canvas
        c.delete("all")
        best = {}
        for i, m in enumerate(moves):
            best.setdefault(m.from_square, i)
            best.setdefault(m.to_square, i)

        def xy(sq):
            f, r = chess.square_file(sq), chess.square_rank(sq)
            col, row = (7 - f, r) if flipped else (f, 7 - r)
            return col * SQ, row * SQ

        for sq in chess.SQUARES:
            x, y = xy(sq)
            light = (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 1
            color = LIGHT if light else DARK
            c.create_rectangle(x, y, x + SQ, y + SQ, fill=color, outline="")
            if sq in best and best[sq] == 0:
                c.create_rectangle(x, y, x + SQ, y + SQ, fill="#2ecc40", outline="")
            elif sq in best:
                c.create_rectangle(x + 2, y + 2, x + SQ - 2, y + SQ - 2,
                                   outline=config.GREENS[min(best[sq], 4)], width=4)
            if chess.square_rank(sq) == (7 if flipped else 0):
                c.create_text(x + SQ - 4, y + SQ - 3, text="abcdefgh"[chess.square_file(sq)],
                              anchor="se", font=("Segoe UI", 8, "bold"), fill=DARK if light else LIGHT)
            if chess.square_file(sq) == (7 if flipped else 0):
                c.create_text(x + 3, y + 2, text=str(chess.square_rank(sq) + 1), anchor="nw",
                              font=("Segoe UI", 8, "bold"), fill=DARK if light else LIGHT)

        if board is None:
            c.create_text(SQ * 4, SQ * 4, text="Доска не распознана", fill="#ffffff",
                          font=("Segoe UI", 16, "bold"))
            self._draw_eval(None)
            return

        for sq, p in board.piece_map().items():
            x, y = xy(sq)
            s = p.symbol().lower()
            cx, cy = x + SQ / 2, y + SQ / 2 + 2
            if p.color:
                c.create_text(cx, cy, text=GLYPH[s], font=PIECE_FONT, fill="#ffffff")
                c.create_text(cx, cy, text=OUTLINE[s], font=PIECE_FONT, fill="#1a1a1a")
            else:
                c.create_text(cx, cy, text=GLYPH[s], font=PIECE_FONT, fill="#1a1a1a")

        # вердикты сделанным ходам — под зелёными подсказками
        for m, col, sign, arrow in marks:
            (x0, y0), (x1, y1) = xy(m.from_square), xy(m.to_square)
            for x, y in (((x0, y0), (x1, y1)) if arrow else ((x1, y1),)):
                c.create_rectangle(x + 2, y + 2, x + SQ - 2, y + SQ - 2, outline=col, width=4)
            if arrow:
                c.create_line(x0 + SQ / 2, y0 + SQ / 2, x1 + SQ / 2, y1 + SQ / 2, fill=col, width=8,
                              arrow=tk.LAST, arrowshape=(20, 24, 9), capstyle=tk.ROUND)
            if sign:
                c.create_oval(x1 + 3, y1 + SQ - 23, x1 + 25, y1 + SQ - 3, fill=col, outline="#1a1a1a")
                c.create_text(x1 + 14, y1 + SQ - 13, text=sign, fill="#ffffff",
                              font=("Segoe UI Symbol", 9, "bold"))

        for i in reversed(range(len(moves))):
            m = moves[i]
            (x0, y0), (x1, y1) = xy(m.from_square), xy(m.to_square)
            col = config.GREENS[min(i, 4)]
            c.create_line(x0 + SQ / 2, y0 + SQ / 2, x1 + SQ / 2, y1 + SQ / 2,
                          fill=col if i else "#00ff44", width=10 if i == 0 else 6, arrow=tk.LAST,
                          arrowshape=(22, 26, 10), capstyle=tk.ROUND)
            c.create_oval(x1 + SQ - 22, y1 + 3, x1 + SQ - 4, y1 + 21, fill=col, outline="#0b3d0b")
            c.create_text(x1 + SQ - 13, y1 + 12, text=str(i + 1), fill="#0b3d0b", font=("Segoe UI", 9, "bold"))

    def _draw_eval(self, cp):
        e = self.evalbar
        e.delete("all")
        h = SQ * 8
        if cp is None:
            return
        import math
        frac = 0.5 + 0.5 * (2 / (1 + math.exp(-0.004 * cp)) - 1)   # 0..1, доля белых
        e.create_rectangle(0, 0, 18, h, fill="#403e3b", outline="")
        e.create_rectangle(0, h * (1 - frac), 18, h, fill="#f0f0f0", outline="")


class App(BoardView):
    def __init__(self, engine_path: str, opts=None):
        """opts: argparse.Namespace с полями no_window, gdi, auto_find, auto_find_time,
        external_window (None / "" / подстрока заголовка), multipv."""
        self.opts = opts
        self.window = not getattr(opts, "no_window", False)
        ext = getattr(opts, "external_window", None)
        mpv = getattr(opts, "multipv", None) or config.DEFAULT_MULTIPV

        self.root = tk.Tk()
        self.root.title(f"Chess Vision {__version__} — Stockfish")
        self.root.configure(bg="#262421")
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.engine = EngineWorker(engine_path, config.engine_threads(), config.engine_hash_mb(), mpv)
        self.scanner = Scanner(self.engine.set_position,
                               auto_find=getattr(opts, "auto_find", False),
                               auto_find_time=getattr(opts, "auto_find_time", None) or 5.0,
                               external=ext is not None,
                               window_filter=ext or None)
        self.overlay_on = tk.BooleanVar(value=True)
        self.paused = tk.BooleanVar(value=False)
        self.multipv = tk.IntVar(value=mpv)
        self.engine_path = engine_path
        self.selfplay = None                  # самоигра на виртуальной доске (кнопка Auto)
        self.review = None                    # окно Virtual Game Review
        self.sp_speed = tk.StringVar(value="средне")
        self.sp_book = tk.StringVar(value=BOOKS[getattr(opts, "book", None) or "masters"])
        self._drawn_key = None
        self._printed_key = None
        self._closed = False

        if self.window:
            self._build()
            winutil.exclude_from_capture(self.root)   # окно программы не мешает распознаванию
        else:
            self.root.withdraw()
        if getattr(opts, "gdi", False):
            from .gdi_overlay import GdiOverlay
            # стрелки можно рисовать, только если доска снимается из окна (PrintWindow не видит GDI-рисунок)
            self.overlay = GdiOverlay(lambda: self.scanner.external)
        else:
            self.overlay = Overlay(self.root)

        self.engine.start()
        self.scanner.start()
        self.root.after(150, self._tick)

    # ---------------- интерфейс ----------------
    def _build(self):
        apply_style(self.root)
        fg = "#e8e6e3"

        # строка вверху окна: Running Live analysis... Bestmove is ...
        self.banner = tk.Label(self.root, text="Waiting for board...", anchor="w", padx=10, pady=4,
                               bg=config.BANNER_BG, fg=config.GREENS[0], font=("Segoe UI", 11, "bold"))
        self.banner.pack(fill="x")

        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="n")
        self.evalbar = tk.Canvas(left, width=18, height=SQ * 8, bg="#403e3b", highlightthickness=0)
        self.evalbar.grid(row=0, column=0, padx=(0, 6))
        self.canvas = tk.Canvas(left, width=SQ * 8, height=SQ * 8, highlightthickness=0, bg=DARK)
        self.canvas.grid(row=0, column=1)

        side = ttk.Frame(main, padding=(12, 0, 0, 0))
        side.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(1, weight=1)

        self.eval_lbl = ttk.Label(side, text="—", style="Eval.TLabel")
        self.eval_lbl.pack(anchor="w")
        self.engine_lbl = ttk.Label(side, text="Stockfish: запуск...", foreground="#9e9b98")
        self.engine_lbl.pack(anchor="w", pady=(0, 6))

        self.lines = tk.Text(side, width=44, height=9, bg="#1e1d1b", fg=fg, bd=0,
                             font=("Consolas", 10), wrap="word", state="disabled")
        self.lines.pack(fill="x")
        for i, col in enumerate(config.GREENS):
            self.lines.tag_configure(f"g{i}", foreground=col, font=("Consolas", 10, "bold"))
        for kind, col in config.MARK_COLORS.items():
            self.lines.tag_configure(kind, foreground=col, font=("Consolas", 10, "bold"))

        btns = ttk.Frame(side)
        btns.pack(fill="x", pady=8)
        b = [("Найти доску", lambda: self.scanner.command("detect")),
             ("Выделить вручную", self._select_region),
             ("Калибровка", lambda: self.scanner.command("calibrate")),
             ("Перевернуть", lambda: self.scanner.command("flip")),
             ("Сейчас ход белых", lambda: self.scanner.command("turn", chess.WHITE)),
             ("Сейчас ход чёрных", lambda: self.scanner.command("turn", chess.BLACK))]
        for i, (t, cmd) in enumerate(b):
            ttk.Button(btns, text=t, command=cmd).grid(row=i // 2, column=i % 2, sticky="ew", padx=2, pady=2)
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        opts = ttk.Frame(side)
        opts.pack(fill="x")
        ttk.Checkbutton(opts, text="Подсветка поверх экрана", variable=self.overlay_on).pack(anchor="w")
        ttk.Checkbutton(opts, text="Пауза", variable=self.paused,
                        command=lambda: self.scanner.command("pause", self.paused.get())).pack(anchor="w")
        row = ttk.Frame(opts)
        row.pack(anchor="w", pady=4)
        ttk.Label(row, text="Лучших ходов:").pack(side="left")
        tk.Spinbox(row, from_=1, to=5, width=3, textvariable=self.multipv,
                   command=lambda: self.engine.set_multipv(self.multipv.get())).pack(side="left", padx=4)

        sp = ttk.Frame(opts)
        sp.pack(anchor="w", fill="x", pady=(6, 0))
        self.sp_btn = ttk.Button(sp, text="\u25b6 Auto (самоигра)", command=self._toggle_selfplay)
        self.sp_btn.pack(side="left")
        ttk.Combobox(sp, textvariable=self.sp_speed, values=list(SPEEDS), width=9,
                     state="readonly").pack(side="left", padx=6)
        ttk.Button(opts, text="Virtual Game Review", command=self._open_review).pack(anchor="w", pady=(6, 0))
        bk = ttk.Frame(opts)
        bk.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Label(bk, text="Дебюты:").pack(side="left")
        ttk.Combobox(bk, textvariable=self.sp_book, values=list(BOOKS.values()), width=20,
                     state="readonly").pack(side="left", padx=6)

        self.status = ttk.Label(side, text="", wraplength=330, foreground="#c9c6c2")
        self.status.pack(anchor="w", pady=(8, 0))
        ttk.Label(side, wraplength=330, foreground="#7d7a77",
                  text="Калибровка: откройте новую партию (начальная расстановка) — "
                       "программа запомнит фигуры этой программы.").pack(anchor="w", pady=(8, 0))

    # ---------------- самоигра ----------------
    def _toggle_selfplay(self):
        """Auto: Stockfish доигрывает текущую позицию лучшими ходами — только на виртуальной доске."""
        if self.selfplay is not None:              # «Стоп» / «К живой доске»
            self.selfplay.stop()
            self.selfplay = None
            self.sp_btn.config(text="\u25b6 Auto (самоигра)")
            self._drawn_key = None
            return
        board = self.scanner.snapshot()[0]
        if board is None or board.is_game_over():
            self.status.config(text="Самоигра: нет позиции для доигрывания (доска не распознана или партия окончена)")
            return
        source = next((k for k, v in BOOKS.items() if v == self.sp_book.get()), "masters")
        self.selfplay = SelfPlay(self.engine_path, board, SPEEDS[self.sp_speed.get()], book=Book(source))
        self.selfplay.start()
        self.sp_btn.config(text="\u25a0 Стоп")
        self._drawn_key = None

    def _open_review(self):
        """Разбор партии: самоигры Auto, если она запущена, иначе партии с живой доски."""
        from .review import ReviewWindow
        flipped = self.scanner.snapshot()[2]
        if self.selfplay is not None:
            (start, moves), title = self.selfplay.game(), "самоигра Auto"
        else:
            game = self.scanner.game()
            (start, moves), title = game or (chess.Board(), []), "партия с доски" if game else "новая партия"
        if self.review is not None and not self.review._closed:
            self.review.set_game(start, moves, title)
            self.review.win.lift()
            return
        self.review = ReviewWindow(self.engine_path, start, moves, master=self.root, title=title,
                                   flipped=flipped)
        self.review.win.attributes("-topmost", True)

    def _draw_selfplay(self, flipped):
        sp = self.selfplay
        board, sans, last, result = sp.snapshot()
        if not sp.running and self.sp_btn.cget("text") != "\u21a9 К живой доске":
            self.sp_btn.config(text="\u21a9 К живой доске")
        tail = sp.error or result or "идёт..."
        book = sp.book
        phase = "дебют" if book is not None and not book.out_of_book else "Stockfish"
        opening = f"   ≡ {book.opening}" if book is not None and book.opening else ""
        self.banner.config(text=f"Auto ({phase}): {sans[-1] if sans else '...'}   ·   {tail}{opening}")
        key = ("selfplay", board.fen(), len(sans), result, sp.error, flipped, opening)
        if key == self._drawn_key:
            return
        self._drawn_key = key
        marks = [(last, "#4aa3ff", "", True)] if last else []
        self._draw_board(board, flipped, [], marks)
        t = self.lines
        t.config(state="normal")
        t.delete("1.0", "end")
        t.insert("end", f"Самоигра: {len(sans)} полуходов, {sp.move_time:g} с на ход\n", "g0")
        if book is not None:
            t.insert("end", f"Книга: {book.status()} · из книги {sp.book_plies} полуходов\n")
            if book.opening:
                t.insert("end", f"≡ {book.opening}\n", "book")
        t.insert("end", "\n")
        t.insert("end", sp.pgn_moves() + "\n\n")
        if sp.error or result:
            t.insert("end", (sp.error or f"Итог: {result}") + "\n", "blunder" if sp.error else "g0")
        t.see("end")
        t.config(state="disabled")
        self.eval_lbl.config(text="Auto")

    def _select_region(self):
        RegionSelector(self.root, lambda r: self.scanner.command("set_region", r))

    # ---------------- обновление ----------------
    def _tick(self):
        try:
            board, region, flipped, status = self.scanner.snapshot()
            res = self.engine.result
            if res is not None and board is not None and res["fen"].split()[:4] != board.fen().split()[:4]:
                res = None
            moves = [l["move"] for l in res["lines"]] if res else []
            marks = config.verdict_marks(res)
            banner = config.banner_segments(board, res)

            if self.overlay_on.get() and not self.paused.get() and board is not None:
                self.overlay.show(region, flipped, moves, marks, banner)
            else:
                self.overlay.hide()

            if not self.window:
                self._print_console(board, status, res)
                return

            if self.selfplay is not None:       # окно показывает самоигру, подсветка на экране — живую доску
                self.status.config(text=status)
                self._draw_selfplay(flipped)
                return

            self.banner.config(text="".join(t for t, _ in banner) if banner else "Waiting for board...")
            self.status.config(text=status)
            if self.engine.error:
                self.engine_lbl.config(text=self.engine.error, foreground="#ff6b6b")
            elif res:
                self.engine_lbl.config(text=f"{self.engine.name} · глубина {res['depth']} · "
                                            f"{res['nps'] // 1000} kN/s · {config.engine_threads()} потоков")
            else:
                self.engine_lbl.config(text=f"{self.engine.name} · {config.engine_threads()} потоков, "
                                            f"{self.engine.options['Hash']} MB хэш")

            key = (board.fen() if board else None, flipped, tuple(m.uci() for m in moves), tuple(marks))
            if key != self._drawn_key:
                self._drawn_key = key
                self._draw_board(board, flipped, moves, marks)
                self._draw_lines(board, res)
        finally:
            if not self._closed:
                self.root.after(150, self._tick)

    def _print_console(self, board, status, res):
        """--no-window: лучшие ходы печатаются в консоль."""
        key = (status, board.fen() if board else None,
               tuple(l["move"] for l in res["lines"]) if res else None,
               res["depth"] // 4 if res else None,
               tuple((j["san"], j["kind"]) for j in res.get("judged", [])) if res else None)
        if key == self._printed_key:
            return
        self._printed_key = key
        if not res or board is None:
            print(f"[{status}]", flush=True)
            return
        side = "белых" if board.turn else "чёрных"
        for j in res.get("judged", []):
            if j["kind"] in config.MARK_COLORS:
                print("  " + verdict_text(j), flush=True)
        best = "   ".join(f"{i + 1}. {l['san'][0] if l['san'] else '?'} ({l['score']})"
                          for i, l in enumerate(res["lines"]))
        print(f"Ход {side} | глубина {res['depth']:>2} | {best}", flush=True)

    def _draw_lines(self, board, res):
        t = self.lines
        t.config(state="normal")
        t.delete("1.0", "end")
        if not res:
            t.insert("end", "Ожидание анализа..." if board is not None else "Нет позиции для анализа")
            self.eval_lbl.config(text="—")
            self._draw_eval(None)
        else:
            first = res["lines"][0]
            self.eval_lbl.config(text=f"{first['score']}   {first['san'][0] if first['san'] else ''}")
            self._draw_eval(first["cp"])
            for i, l in enumerate(res["lines"]):
                t.insert("end", f"{i + 1}. {l['san'][0] if l['san'] else '?':<7}", f"g{min(i, 4)}")
                t.insert("end", f"{l['score']:>7}  ")
                t.insert("end", " ".join(l["san"][1:7]) + "\n\n")
            for j in res.get("judged", []):
                if j["kind"] in config.MARK_COLORS:
                    t.insert("end", verdict_text(j) + "\n", j["kind"])
        t.config(state="disabled")

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.selfplay is not None:
            self.selfplay.stop()
        if self.review is not None:
            self.review.close()
        self.scanner.stop()
        self.engine.shutdown()
        if hasattr(self.overlay, "destroy") and not isinstance(self.overlay, Overlay):
            self.overlay.destroy()
        self.root.destroy()

    def run(self):
        import signal
        signal.signal(signal.SIGINT, lambda *a: self.root.after(0, self.close))   # Ctrl+C в консоли
        self.root.mainloop()
