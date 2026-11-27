"""Прозрачное окно поверх настоящей доски: зелёные стрелки и рамки лучших ходов.
Мышь проходит сквозь него, а в скриншоты оно не попадает."""
import tkinter as tk
from tkinter import font as tkfont

from . import winutil
from .config import BANNER_BG, GREENS, banner_height, banner_layout

KEY = "#ff00fe"   # этот цвет становится прозрачным


class Overlay:
    def __init__(self, root):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=KEY)
        try:
            self.win.attributes("-transparentcolor", KEY)
        except tk.TclError:
            self.win.attributes("-alpha", 0.5)
        self.canvas = tk.Canvas(self.win, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.win.geometry("10x10+0+0")
        self.win.update_idletasks()
        winutil.make_click_through(self.win)
        # Если окно нельзя исключить из захвата, рисуем только тонкие рамки по краю клеток:
        # распознавание эту зону игнорирует, стрелки же помешали бы.
        self.safe = winutil.exclude_from_capture(self.win)
        self.win.withdraw()
        self._shown = False
        self._key = None
        self._raise_tick = 0

    def hide(self):
        if self._shown:
            self.win.withdraw()
            self._shown = False
            self._key = None

    def show(self, region, flipped, moves, marks=(), banner=None):
        """moves: список chess.Move, лучший первым; marks: [(ход, цвет, знак)] — вердикты
        сделанным ходам (оранжевая — ошибка, красная — зевок); banner: строка над доской
        [(текст, цвет), ...]."""
        if region is None or not (moves or marks or banner):
            self.hide()
            return
        key = (region, flipped, tuple(m.uci() for m in moves), tuple(marks), banner)
        if key == self._key and self._shown:
            self._raise_tick += 1
            if self._raise_tick % 7 == 0:          # другие "поверх всех" окна не должны нас перекрыть
                self.win.attributes("-topmost", True)
                self.win.lift()
            return
        self._key = key
        s = int(region[2])
        bfont = ("Segoe UI", max(9, int(banner_height(s) * 0.45)), "bold")
        text_w = 0
        if banner:
            f = tkfont.Font(root=self.win, font=bfont)
            text_w = sum(f.measure(t) for t, _ in banner)
        wx, wy, ww, wh, off, bar_y, bar_h = banner_layout(region, bool(banner), text_w)
        self.win.geometry(f"{ww}x{wh}+{wx}+{wy}")
        c = self.canvas
        c.delete("all")
        cs = s / 8
        if banner:
            c.create_rectangle(0, bar_y, ww, bar_y + bar_h, fill=BANNER_BG, outline="")
            tx = 8
            font = bfont
            for text, color in banner:
                item = c.create_text(tx, bar_y + bar_h / 2, text=text, fill=color, font=font, anchor="w")
                tx = c.bbox(item)[2]

        def center(sq):
            f, r = sq % 8, sq // 8
            col, row = (7 - f, r) if flipped else (f, 7 - r)
            return (col + 0.5) * cs, (row + 0.5) * cs + off

        def frame(sq, color, w):
            cx, cy = center(sq)
            h = cs / 2 - w / 2
            c.create_rectangle(cx - h, cy - h, cx + h, cy + h, outline=color, width=w)

        for m, color, sign, arrow in marks:          # вердикты — под зелёными подсказками
            w = max(3, int(cs * 0.05))
            if arrow:
                frame(m.from_square, color, w)
            frame(m.to_square, color, w)
            if not self.safe:
                continue
            (x0, y0), (x1, y1) = center(m.from_square), center(m.to_square)
            if arrow:      # ошибка / зевок — стрелкой; лучший / блестящий / теория — значком
                c.create_line(x0, y0, x1, y1, fill=color, width=max(3, int(cs * 0.12)), arrow=tk.LAST,
                              capstyle=tk.ROUND, arrowshape=(cs * 0.32, cs * 0.38, cs * 0.14))
            r0 = cs * 0.16
            ox, oy = x1 - cs * 0.3, y1 + cs * 0.3      # нижний левый угол: номера подсказок — вверху справа
            c.create_oval(ox - r0, oy - r0, ox + r0, oy + r0, fill=color, outline="#1a1a1a")
            c.create_text(ox, oy, text=sign, fill="#ffffff",
                          font=("Segoe UI Symbol", max(8, int(cs * 0.14)), "bold"))

        for i in reversed(range(len(moves))):
            m = moves[i]
            color = GREENS[min(i, len(GREENS) - 1)]
            if self.safe:
                w = max(3, int(cs * (0.07 if i == 0 else 0.04)))
                frame(m.from_square, color, w)
                frame(m.to_square, color, w)
                (x0, y0), (x1, y1) = center(m.from_square), center(m.to_square)
                c.create_line(x0, y0, x1, y1, fill=color, width=max(3, int(cs * (0.16 if i == 0 else 0.09))),
                              arrow=tk.LAST, capstyle=tk.ROUND,
                              arrowshape=(cs * 0.35, cs * 0.42, cs * 0.16))
                c.create_oval(x1 + cs * 0.18, y1 - cs * 0.46, x1 + cs * 0.46, y1 - cs * 0.18,
                              fill=color, outline="#0b3d0b")
                c.create_text(x1 + cs * 0.32, y1 - cs * 0.32, text=str(i + 1), fill="#0b3d0b",
                              font=("Segoe UI", max(8, int(cs * 0.15)), "bold"))
            else:
                w = max(2, int(cs * 0.035))
                frame(m.from_square, color, w)
                frame(m.to_square, color, w)
        if not self._shown:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self._shown = True
