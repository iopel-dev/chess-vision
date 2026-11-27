"""Распознавание фигур на доске.

Калибровка по начальной позиции: с каждой из 32 фигур снимается эталон —
картинка фигуры и её силуэт (маска, отделяющая фигуру от клетки).

Распознавание — сравнение с эталонами целиком: эталон «пересаживается» на фон
текущей клетки (силуэт берётся из эталона, всё остальное — цвет этой клетки)
и сравнивается с клеткой попиксельно. Ближайший эталон даёт и тип, и цвет фигуры.
Так белые и чёрные различаются по всему рисунку фигуры (заливка, контур, блики,
тень), а не по средней яркости — это работает и с кремовыми/«деревянными»/
цветными наборами, тенями под фигурами, светлыми и тёмными досками.
"""
import cv2
import chess
import numpy as np

CELL = 64
CALIB_VERSION = 2
EMPTY_FRAC = 0.04        # меньше этой доли пикселей силуэта — клетка пустая
MAX_DIST = 45.0          # среднее L1-отличие от лучшего эталона; больше — фигура не опознана
B = 3                    # край клетки, который не сравниваем (соседние клетки, рамки подсветки)

_RING = np.zeros((CELL, CELL), bool)
_RING[2:CELL - 2, 2:CELL - 2] = True
_RING[7:CELL - 7, 7:CELL - 7] = False
_K3 = np.ones((3, 3), np.uint8)
_K5 = np.ones((5, 5), np.uint8)
SYMBOLS = "PNBRQKpnbrqk"


class CalibrationError(Exception):
    pass


def split_cells(board_img: np.ndarray) -> np.ndarray:
    img = cv2.resize(board_img, (CELL * 8, CELL * 8), interpolation=cv2.INTER_AREA)
    return img.reshape(8, CELL, 8, CELL, 3).transpose(0, 2, 1, 3, 4)   # [row][col] сверху вниз


def cell_background(cell: np.ndarray) -> np.ndarray:
    return np.median(cell[_RING], axis=0)


def analyze_cell(cell: np.ndarray):
    """-> (силуэт 0/1 uint8, яркость фигуры или None, если клетка пустая)"""
    sil, b, _ = _analyze(cell)
    return sil, b


def _analyze(cell: np.ndarray):
    """-> (силуэт, яркость или None, цвет фона клетки)"""
    ring = cell[_RING].astype(np.int16)
    bg = np.median(ring, axis=0)
    # порог отличия от клетки подстраивается под её «шум»: однотонная клетка — низкий
    # порог (видно чёрную фигуру на почти чёрной клетке), текстура дерева — высокий
    noise = float(np.median(np.abs(ring - bg).sum(axis=1)))
    thr = min(55.0, max(20.0, 4 * noise + 15))
    dist = np.abs(cell.astype(np.int16) - bg.astype(np.int16)).sum(axis=2)
    mask = (dist > thr).astype(np.uint8)
    mask[:B] = 0
    mask[-B:] = 0
    mask[:, :B] = 0
    mask[:, -B:] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, _K3)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    keep = []
    lo, hi = int(CELL * 0.34), int(CELL * 0.66)
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w * h < 30:
            continue
        # координаты доски (цифры/буквы) — мелкие пятна в углах клетки
        if w < CELL * 0.33 and h < CELL * 0.33 and (x + w < lo or x > hi) and (y + h < lo or y > hi):
            continue
        keep.append(c)
    sil = np.zeros((CELL, CELL), np.uint8)
    if keep:
        cv2.drawContours(sil, keep, -1, 1, thickness=cv2.FILLED)
    if sil.sum() < EMPTY_FRAC * CELL * CELL:
        return sil, None, bg
    inner = cv2.erode(sil, _K5, iterations=2)
    if inner.sum() < 20:
        inner = sil
    gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
    return sil, float(gray[inner > 0].mean()), bg


_PARITY = (np.add.outer(np.arange(8), np.arange(8)) % 2).astype(bool)
HIGHLIGHT_THR = 30       # L1-отличие фона клетки от обычного цвета клеток этой «чётности»


def last_move_color(cells: np.ndarray, grid):
    """Сайты (lichess, chess.com, ...) подсвечивают клетки последнего хода.
    Ровно 2 подсвеченные клетки: «откуда» (пустая) и «куда» (с фигурой) —
    цвет этой фигуры и есть сторона, сделавшая последний ход. Иначе None."""
    bgs = np.median(cells[:, :, _RING], axis=2).astype(np.float32)     # (8, 8, 3) фон каждой клетки
    hl = np.zeros((8, 8), bool)
    for p in (False, True):
        ref = np.median(bgs[_PARITY == p], axis=0)
        hl |= (_PARITY == p) & (np.abs(bgs - ref).sum(axis=2) > HIGHLIGHT_THR)
    pts = list(zip(*np.nonzero(hl)))
    if len(pts) != 2:
        return None
    occ = [grid[r][c] for r, c in pts]
    filled = [s for s in occ if s not in (None, "?")]
    if len(filled) != 1 or occ.count(None) != 1:
        return None
    return filled[0].isupper()          # True = белые


def square_of(row: int, col: int, flipped: bool) -> int:
    """Клетка экрана (row сверху, col слева) -> поле python-chess."""
    if flipped:   # чёрные снизу
        return chess.square(7 - col, row)
    return chess.square(col, 7 - row)


class Recognizer:
    def __init__(self, imgs, sils, parities, symbols, white_ref, black_ref):
        """imgs (N,64,64,3) uint8, sils (N,64,64) bool, parities (N,) — светлая/тёмная клетка
        эталона, symbols — символ фигуры каждого эталона."""
        self.imgs = np.asarray(imgs, np.uint8)
        self.sils = np.asarray(sils, bool)
        self.parities = np.asarray(parities, bool)
        self.symbols = list(symbols)
        self.white_ref, self.black_ref = float(white_ref), float(black_ref)
        # сравниваем каждый второй пиксель: точность та же, работы вчетверо меньше
        self._t = self.imgs[:, B:-B:2, B:-B:2].astype(np.int16)
        self._s = self.sils[:, B:-B:2, B:-B:2, None]
        # для каждой чётности клетки: эталоны с той же чётностью (фон под полупрозрачными
        # краями и тенью совпадает), а если для фигуры таких нет — все её эталоны
        self._cand = {}
        for p in (False, True):
            idx = []
            for s in SYMBOLS:
                own = [i for i, sym in enumerate(self.symbols) if sym == s]
                same = [i for i in own if self.parities[i] == p]
                idx += same or own
            self._cand[p] = np.array(idx)

    # ---------- калибровка ----------
    @classmethod
    def calibrate(cls, board_img: np.ndarray):
        """Доска должна стоять в начальной позиции. -> (Recognizer, flipped)"""
        cells = split_cells(board_img)
        sils, bright = {}, {}
        for r in range(8):
            for c in range(8):
                sils[r, c], bright[r, c] = analyze_cell(cells[r, c])
        occupied = {k for k, v in bright.items() if v is not None}
        expected = {(r, c) for r in (0, 1, 6, 7) for c in range(8)}
        if occupied != expected:
            raise CalibrationError(
                f"Доска не в начальной позиции (найдено фигур: {len(occupied)}, "
                f"на своих местах: {len(occupied & expected)}/32)")
        # ориентация: средняя яркость 16 фигур сверху против 16 снизу
        top = np.mean([bright[r, c] for r in (0, 1) for c in range(8)])
        bottom = np.mean([bright[r, c] for r in (6, 7) for c in range(8)])
        if abs(top - bottom) < 10:
            raise CalibrationError("Не удаётся отличить белые фигуры от чёрных")
        flipped = top > bottom
        start = chess.Board()
        imgs, ss, pars, syms, wb, bb = [], [], [], [], [], []
        pawns = {}
        for (r, c) in sorted(expected):
            p = start.piece_at(square_of(r, c, flipped))
            sym = p.symbol()
            par = bool((r + c) % 2)
            if sym in "Pp":                 # пешек хватит по 2 на каждую чётность клетки
                key = (sym, par)
                if pawns.get(key, 0) >= 2:
                    continue
                pawns[key] = pawns.get(key, 0) + 1
            imgs.append(cells[r, c].copy())
            ss.append(sils[r, c].astype(bool))
            pars.append(par)
            syms.append(sym)
            (wb if p.color else bb).append(bright[r, c])
        rec = cls(imgs, ss, pars, syms, np.mean(wb), np.mean(bb))
        placement, unknown = rec.read(board_img, flipped)
        if unknown or placement != chess.STARTING_BOARD_FEN:
            raise CalibrationError("Калибровка не прошла самопроверку — попробуйте ещё раз")
        return rec, flipped

    # ---------- распознавание ----------
    def classify(self, cell: np.ndarray, parity: bool):
        """-> символ фигуры, None (пусто) или "?" (не похоже ни на один эталон)"""
        _, b, bg = _analyze(cell)
        if b is None:
            return None
        idx = self._cand[parity]
        bg = bg.astype(np.int16)
        comp = np.where(self._s[idx], self._t[idx], bg)              # эталоны на фоне этой клетки
        dist = np.abs(comp - cell[B:-B:2, B:-B:2].astype(np.int16)).sum(axis=3).mean(axis=(1, 2))
        i = int(np.argmin(dist))
        return self.symbols[idx[i]] if dist[i] <= MAX_DIST else "?"

    def read(self, board_img: np.ndarray, flipped: bool):
        """-> (FEN расстановки, число нераспознанных клеток).
        Заодно заполняет self.last_mover: цвет, сделавший последний ход, по подсветке
        последнего хода на сайте (или None, если подсветки нет / она неоднозначна)."""
        cells = split_cells(board_img)
        board = chess.Board(None)
        unknown = 0
        grid = [[None] * 8 for _ in range(8)]
        for r in range(8):
            for c in range(8):
                s = self.classify(cells[r, c], bool((r + c) % 2))
                grid[r][c] = s
                if s is None:
                    continue
                if s == "?":
                    unknown += 1
                    continue
                board.set_piece_at(square_of(r, c, flipped), chess.Piece.from_symbol(s))
        self.last_mover = last_move_color(cells, grid)
        return board.board_fen(), unknown

    last_mover = None

    # ---------- сохранение ----------
    def save(self, path, flipped: bool):
        np.savez_compressed(path, version=CALIB_VERSION, imgs=self.imgs, sils=self.sils,
                            parities=self.parities, symbols=np.array(self.symbols),
                            white_ref=self.white_ref, black_ref=self.black_ref, flipped=flipped)

    @classmethod
    def load(cls, path):
        d = np.load(path)
        if "version" not in d or int(d["version"]) != CALIB_VERSION:
            raise CalibrationError("Калибровка от старой версии программы — нужна новая")
        rec = cls(d["imgs"], d["sils"], d["parities"], [str(s) for s in d["symbols"]],
                  float(d["white_ref"]), float(d["black_ref"]))
        return rec, bool(d["flipped"])
