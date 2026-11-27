"""Virtual Game Review: разбор партии на виртуальной доске.

Стрелки ◀ ▶ (и клавиши ← → Home End) листают ходы. На каждой позиции зелёная стрелка
показывает лучший ход Stockfish, рядом оценка и отметка сделанному ходу (≡ ★ !! ? ??).
«★ Лучший ход» играет лучший ход из текущей позиции, «⏵ Авто» листает партию сам,
а в конце доигрывает её лучшими ходами. ▶ в конце партии тоже делает лучший ход.

Партию можно взять из самоигры Auto, с живой доски или из PGN-файла.
Всё происходит в окне программы — на сайтах ничего не нажимается.
"""
import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import chess
import chess.engine
import chess.pgn

from . import __version__, config, i18n
from . import judge as judging
from .engine import format_score
from .gui import SQ, DARK, BoardView, Choice, apply_style, lang_choice, verdict_text
from .i18n import tr
from .openings import OpeningBook
from .selfplay import REASONS, SPEED_NAMES, SPEEDS

ANALYSIS_TIME = 0.4       # секунд Stockfish на каждую позицию партии
LAST_MOVE = "#4aa3ff"


class Analyzer(threading.Thread):
    """Свой Stockfish: по очереди анализирует все позиции партии, текущую — первой."""

    def __init__(self, path, move_time=ANALYSIS_TIME):
        super().__init__(daemon=True, name="review-analyzer")
        self.path = path
        self.move_time = move_time
        self.fens = []
        self.focus = None
        self.results = {}          # fen -> {"cp", "score", "best", "san", "pv", "depth"}
        self.error = None
        self._cond = threading.Condition()
        self._halt = False

    def set_positions(self, fens, focus):
        with self._cond:
            self.fens = list(fens)
            self.focus = focus
            self._cond.notify()

    def get(self, fen):
        with self._cond:
            return self.results.get(fen)

    def progress(self):
        with self._cond:
            return sum(1 for f in self.fens if f in self.results), len(self.fens)

    def stop(self):
        with self._cond:
            self._halt = True
            self._cond.notify()

    def _next(self):
        """Текущая позиция, предыдущая (нужна для отметки ходу), потом после неё, потом до неё."""
        start = self.fens.index(self.focus) if self.focus in self.fens else 0
        order = [self.focus] if self.focus is not None else []
        order += self.fens[max(0, start - 1):start] + self.fens[start:] + self.fens[:start]
        for f in order:
            if f not in self.results:
                return f
        return None

    def run(self):
        engine = None
        try:
            engine = chess.engine.SimpleEngine.popen_uci(self.path, timeout=60)
            opts = {"Threads": max(1, (os.cpu_count() or 2) // 2), "Hash": 256}
            engine.configure({k: v for k, v in opts.items() if k in engine.options})
            while True:
                with self._cond:
                    while not self._halt and self._next() is None:
                        self._cond.wait()
                    if self._halt:
                        return
                    fen = self._next()
                res = self._analyse(engine, chess.Board(fen))
                with self._cond:
                    self.results[fen] = res
        except Exception as e:
            self.error = f"Stockfish: {e}"
        finally:
            if engine is not None:
                try:
                    engine.quit()
                except Exception:
                    pass

    def _analyse(self, engine, board):
        outcome = board.outcome()
        if outcome is not None:            # мат / пат — движок не нужен
            if outcome.winner is None:
                return {"cp": 0, "score": "0.00", "best": None, "san": None, "pv": [], "depth": 0}
            cp = 100000 if outcome.winner else -100000
            return {"cp": cp, "score": "1-0" if outcome.winner else "0-1",
                    "best": None, "san": None, "pv": [], "depth": 0}
        info = engine.analyse(board, chess.engine.Limit(time=self.move_time))
        pv = info.get("pv") or []
        score = info["score"]
        best = pv[0] if pv else next(iter(board.legal_moves))
        pv_san, b = [], board.copy()
        for m in pv[:8]:
            pv_san.append(b.san(m))
            b.push(m)
        return {"cp": score.white().score(mate_score=100000), "score": format_score(score),
                "best": best, "san": board.san(best), "pv": pv_san, "depth": info.get("depth", 0)}


class ReviewWindow(BoardView):
    def __init__(self, engine_path, start=None, moves=(), master=None, title="", flipped=False,
                 on_lang=None):
        """on_lang(код) — смена языка из этого окна (по умолчанию — только это окно)."""
        self.on_lang = on_lang
        self.own_root = master is None
        self.win = tk.Tk() if self.own_root else tk.Toplevel(master)
        self.win.title(f"Virtual Game Review — Chess Vision {__version__}")
        self.win.configure(bg="#262421")
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        if self.own_root:
            apply_style(self.win)

        self.start = (start or chess.Board()).copy(stack=False)
        self.moves = list(moves)
        self.ply = 0
        self.flipped = flipped
        self.title = title
        self.auto = False
        self.want_best = False          # нажали «Лучший ход», а позиция ещё не посчитана
        self._last_step = 0.0
        self._drawn_key = None
        self._closed = False
        self.speed = "medium"           # ключ SPEEDS
        self.book = OpeningBook()
        self.analyzer = Analyzer(engine_path)

        self._build()
        self._positions_changed()
        self.analyzer.start()
        self.win.after(100, self._tick)

    # ---------------- интерфейс ----------------
    def _build(self):
        fg = "#e8e6e3"
        w = self.win
        self.banner = tk.Label(w, text="Virtual Game Review", anchor="w", padx=10, pady=4,
                               bg=config.BANNER_BG, fg=config.GREENS[0], font=("Segoe UI", 11, "bold"))
        self.banner.pack(fill="x")

        main = ttk.Frame(w, padding=8)
        main.pack(fill="both", expand=True)
        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="n")
        self.evalbar = tk.Canvas(left, width=18, height=SQ * 8, bg="#403e3b", highlightthickness=0)
        self.evalbar.grid(row=0, column=0, padx=(0, 6))
        self.canvas = tk.Canvas(left, width=SQ * 8, height=SQ * 8, highlightthickness=0, bg=DARK)
        self.canvas.grid(row=0, column=1)

        ttk.Style(w).configure("Nav.TButton", font=("Segoe UI Symbol", 14), padding=(10, 2))
        nav = ttk.Frame(left)
        nav.grid(row=1, column=1, pady=(8, 0))
        for text, cmd in (("⏮", lambda: self.goto(0)), ("◀", self.back),
                          ("▶", self.forward), ("⏭", lambda: self.goto(len(self.moves)))):
            ttk.Button(nav, text=text, width=4, style="Nav.TButton", command=cmd).pack(side="left", padx=3)

        side = ttk.Frame(main, padding=(12, 0, 0, 0))
        side.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self.eval_lbl = ttk.Label(side, text="—", style="Eval.TLabel")
        self.eval_lbl.pack(anchor="w")
        self.best_lbl = ttk.Label(side, text="", foreground=config.GREENS[0], font=("Segoe UI", 11, "bold"))
        self.best_lbl.pack(anchor="w")
        self.pv_lbl = ttk.Label(side, text="", foreground="#9e9b98", wraplength=360)
        self.pv_lbl.pack(anchor="w")
        self.verdict_lbl = ttk.Label(side, text="", font=("Segoe UI", 10, "bold"), wraplength=360)
        self.verdict_lbl.pack(anchor="w", pady=(4, 6))

        self.text = tk.Text(side, width=46, height=16, bg="#1e1d1b", fg=fg, bd=0, cursor="arrow",
                            font=("Consolas", 10), wrap="word", state="disabled")
        self.text.pack(fill="both", expand=True)
        for kind, col in config.MARK_COLORS.items():
            self.text.tag_configure(kind, foreground=col, font=("Consolas", 10, "bold"))
        self.text.tag_configure("num", foreground="#7d7a77")
        self.text.tag_configure("cur", background="#4b4847")

        row = ttk.Frame(side)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text=tr("★ Лучший ход"), command=self.play_best).pack(side="left")
        self.auto_btn = ttk.Button(row, text="", command=self.toggle_auto)
        self.auto_btn.pack(side="left", padx=6)
        self._sync_auto_btn()
        Choice(row, SPEED_NAMES, self.speed, 9, lambda k: setattr(self, "speed", k)).pack(side="left")

        row2 = ttk.Frame(side)
        row2.pack(fill="x", pady=(6, 0))
        for text, cmd in ((tr("Открыть PGN"), self.open_pgn), (tr("Сохранить PGN"), self.save_pgn),
                          (tr("Перевернуть"), self.flip), (tr("Новая партия"), self.new_game)):
            ttk.Button(row2, text=text, command=cmd).pack(side="left", padx=(0, 4))

        lang_choice(side, self._set_lang).pack(anchor="w", pady=(6, 0))
        self.status = ttk.Label(side, text="", foreground="#7d7a77", wraplength=360)
        self.status.pack(anchor="w", pady=(6, 0))

        for key, cmd in (("<Left>", self.back), ("<Right>", self.forward),
                         ("<Home>", lambda: self.goto(0)), ("<End>", lambda: self.goto(len(self.moves))),
                         ("<space>", self.toggle_auto), ("<f>", self.flip), ("<b>", self.play_best)):
            w.bind(key, lambda e, c=cmd: c())
        self.canvas.bind("<MouseWheel>", lambda e: self.back() if e.delta > 0 else self.forward())
        w.focus_force()

    # ---------------- позиции ----------------
    def board_at(self, ply) -> chess.Board:
        b = self.start.copy()
        for m in self.moves[:ply]:
            b.push(m)
        return b

    def _fens(self):
        b = self.start.copy()
        out = [b.fen()]
        for m in self.moves:
            b.push(m)
            out.append(b.fen())
        return out

    def _positions_changed(self):
        fens = self._fens()
        self.analyzer.set_positions(fens, fens[self.ply])
        self._drawn_key = None

    def _focus_changed(self):
        self.analyzer.set_positions(self._fens(), self.board_at(self.ply).fen())

    # ---------------- навигация ----------------
    def goto(self, ply):
        ply = max(0, min(len(self.moves), ply))
        if ply != self.ply:
            self.ply = ply
            self._focus_changed()

    def back(self):
        self.auto = False
        self._sync_auto_btn()
        self.goto(self.ply - 1)

    def forward(self):
        """Следующий ход партии; в конце партии — лучший ход движка."""
        if self.ply < len(self.moves):
            self.goto(self.ply + 1)
        else:
            self.play_best()

    def play_best(self):
        b = self.board_at(self.ply)
        if b.is_game_over():
            self.status.config(text=tr("Партия окончена."))
            return False
        res = self.analyzer.get(b.fen())
        if res is None or res["best"] is None:
            self.want_best = True
            self.status.config(text=tr("Stockfish считает лучший ход..."))
            return False
        self.want_best = False
        best = res["best"]
        if self.ply < len(self.moves) and self.moves[self.ply] == best:
            self.goto(self.ply + 1)                 # в партии и так был лучший ход
            return True
        self.moves = self.moves[:self.ply] + [best]  # новое продолжение вместо сыгранного
        self.ply += 1
        self._positions_changed()
        return True

    def toggle_auto(self):
        self.auto = not self.auto
        self._last_step = 0.0
        self._sync_auto_btn()

    def _sync_auto_btn(self):
        self.auto_btn.config(text=tr("⏸ Пауза") if self.auto else tr("⏵ Авто"))

    def flip(self):
        self.flipped = not self.flipped
        self._drawn_key = None

    def set_game(self, start, moves, title=""):
        self.start = start.copy(stack=False)
        self.moves = list(moves)
        self.ply = 0
        self.title = title
        self.auto = False
        self._sync_auto_btn()
        self._positions_changed()

    def new_game(self):
        self.set_game(chess.Board(), [], tr("новая партия"))

    # ---------------- PGN ----------------
    def open_pgn(self):
        path = filedialog.askopenfilename(parent=self.win, title=tr("Открыть партию"),
                                          filetypes=[("PGN", "*.pgn"), (tr("Все файлы"), "*.*")])
        if path:
            self.load_pgn(path)

    def load_pgn(self, path):
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as f:
                game = chess.pgn.read_game(f)
        except OSError as e:
            messagebox.showerror("Virtual Game Review", tr("Не удалось открыть файл:\n{e}", e=e), parent=self.win)
            return
        if game is None:
            messagebox.showerror("Virtual Game Review", tr("В файле нет партии."), parent=self.win)
            return
        h = game.headers
        self.set_game(game.board(), list(game.mainline_moves()),
                      f"{h.get('White', '?')} — {h.get('Black', '?')}  {h.get('Result', '')}".strip())

    def save_pgn(self):
        path = filedialog.asksaveasfilename(parent=self.win, title=tr("Сохранить партию"),
                                            defaultextension=".pgn", filetypes=[("PGN", "*.pgn")])
        if not path:
            return
        game = chess.pgn.Game()
        if self.start.fen() != chess.STARTING_FEN:
            game.setup(self.start)
        game.headers["Event"] = "Chess Vision Review"
        final = self.board_at(len(self.moves))
        game.headers["Result"] = final.result(claim_draw=True)
        node = game
        for i, m in enumerate(self.moves):
            node = node.add_variation(m)
            res = self.analyzer.get(self.board_at(i + 1).fen())
            if res:
                node.comment = f"[%eval {res['score']}]" if not res["score"].startswith(("1-", "0-")) else ""
        with open(path, "w", encoding="utf-8") as f:
            print(game, file=f)
        self.status.config(text=tr("Сохранено: {path}", path=path))

    # ---------------- оценки ----------------
    def verdict(self, ply):
        """Отметка ходу, который привёл в позицию ply (1..n), или None, пока не посчитано."""
        parent = self.board_at(ply - 1)
        move = self.moves[ply - 1]
        r0 = self.analyzer.get(parent.fen())
        child = parent.copy()
        child.push(move)
        r1 = self.analyzer.get(child.fen())
        if r0 is None or r1 is None:
            return None
        j = judging.classify(parent, move, r0["cp"], r1["cp"], r0["best"], book=self.book)
        j.update(san=parent.san(move), white=parent.turn == chess.WHITE, move=move)
        if j["kind"] == "book":
            j["opening"] = self.book.name(child)
        return j

    # ---------------- обновление ----------------
    def _tick(self):
        if self._closed:
            return
        try:
            now = time.time()
            if self.want_best:
                self.play_best()
            elif self.auto and now - self._last_step >= SPEEDS[self.speed]:
                if self.ply < len(self.moves):
                    self.goto(self.ply + 1)
                    self._last_step = now
                elif self.board_at(self.ply).is_game_over():
                    self.auto = False
                    self._sync_auto_btn()
                elif self.play_best():
                    self._last_step = now
            self._redraw()
        finally:
            if not self._closed:
                self.win.after(100, self._tick)

    def _redraw(self):
        board = self.board_at(self.ply)
        res = self.analyzer.get(board.fen())
        done, total = self.analyzer.progress()
        key = (self.ply, len(self.moves), tuple(self.moves[-1:]), done, self.flipped, bool(res))
        if key == self._drawn_key:
            return
        self._drawn_key = key

        verdicts = [self.verdict(i) for i in range(1, len(self.moves) + 1)]
        j = verdicts[self.ply - 1] if self.ply else None

        marks = []
        if self.ply:
            last = self.moves[self.ply - 1]
            if j and j["kind"] in config.MARK_COLORS:
                kind = j["kind"]
                marks = [(last, config.MARK_COLORS[kind], config.MARK_SIGNS[kind], kind in config.MARK_ARROW)]
            else:
                marks = [(last, LAST_MOVE, "", False)]
        arrows = [res["best"]] if res and res["best"] else []
        self._draw_board(board, self.flipped, arrows, marks)
        self._draw_eval(res["cp"] if res else None)

        # строка вверху
        opening = self.book.name(board)
        head = "Virtual Game Review"
        if self.title:
            head += f"  ·  {self.title}"
        head += "  ·  " + tr("ход {ply}/{n}", ply=self.ply, n=len(self.moves))
        if opening:
            head += f"  ·  ≡ {opening}"
        self.banner.config(text=head)

        # оценка и лучший ход
        outcome = board.outcome(claim_draw=True)
        if outcome is not None:
            self.eval_lbl.config(text=outcome.result())
            self.best_lbl.config(text=tr("Партия окончена: {reason}",
                                         reason=tr(REASONS.get(outcome.termination, "конец партии"))))
            self.pv_lbl.config(text="")
        elif res:
            self.eval_lbl.config(text=res["score"])
            best = tr("Лучший ход белых: {san}") if board.turn else tr("Лучший ход чёрных: {san}")
            self.best_lbl.config(text=best.format(san=res["san"]))
            self.pv_lbl.config(text=tr("Вариант: {pv}   (глубина {depth})", pv=" ".join(res["pv"]),
                                       depth=res["depth"]))
        else:
            self.eval_lbl.config(text="…")
            self.best_lbl.config(text=tr("Stockfish считает..."))
            self.pv_lbl.config(text="")
        if j and j["kind"] in config.MARK_COLORS:
            self.verdict_lbl.config(text=verdict_text(j), foreground=config.MARK_COLORS[j["kind"]])
        elif j:
            self.verdict_lbl.config(text=tr("{san}: нормальный ход", san=j["san"]), foreground="#c9c6c2")
        else:
            self.verdict_lbl.config(text="")

        self._draw_moves(verdicts)
        err = self.analyzer.error
        self.status.config(text=err or (tr("Анализ партии: {done}/{total} позиций", done=done, total=total)
                                        if done < total else
                                        tr("Партия разобрана.  ← → Home End — листать, пробел — авто, B — лучший ход")))

    def _draw_moves(self, verdicts):
        t = self.text
        t.config(state="normal")
        t.delete("1.0", "end")
        b = self.start.copy()
        for i, m in enumerate(self.moves):
            ply = i + 1
            if b.turn == chess.WHITE:
                t.insert("end", f"{b.fullmove_number}. ", "num")
            elif i == 0:
                t.insert("end", f"{b.fullmove_number}... ", "num")
            tag = f"m{ply}"
            tags = (tag, "cur") if ply == self.ply else (tag,)
            t.insert("end", b.san(m), tags)
            j = verdicts[i]
            if j and j["kind"] in config.MARK_COLORS:
                t.insert("end", config.MARK_SIGNS[j["kind"]], (j["kind"],) + tags[1:])
            t.insert("end", " ")
            t.tag_bind(tag, "<Button-1>", lambda e, p=ply: self.goto(p))
            b.push(m)
        if not self.moves:
            t.insert("end", tr("Ходов нет. ▶ или «★ Лучший ход» — сыграть лучший ход, «⏵ Авто» — доиграть партию."),
                     "num")
        t.config(state="disabled")
        if self.ply:
            t.see(f"m{self.ply}.first")

    def _set_lang(self, code):
        if self.on_lang is not None:          # окно открыто из главного — меняем язык везде
            self.on_lang(code)
            return
        i18n.set_lang(code, save=True)
        self.win.after(10, self.rebuild)

    def rebuild(self):
        """Пересоздать виджеты окна (смена языка)."""
        if self._closed:
            return
        for w in self.win.winfo_children():
            w.destroy()
        self._build()
        self._drawn_key = None

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.analyzer.stop()
        self.win.destroy()

    def run(self):
        import signal
        signal.signal(signal.SIGINT, lambda *a: self.win.after(0, self.close))
        self.win.mainloop()
