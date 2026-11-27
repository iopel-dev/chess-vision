"""Поиск шахматной доски на скриншоте.

1. Кандидаты: большие квадратные контуры + решётки, восстановленные по
   отдельным квадратным клеткам.
2. Каждый кандидат проверяется на шахматный узор 8x8 (цвет углов клеток —
   там почти никогда не бывает фигур).
3. Победитель подгоняется с точностью до пикселя по линиям сетки.
"""
import cv2
import numpy as np

MIN_BOARD = 120          # минимальный размер доски, px
MIN_SCORE = 0.85         # доля клеток, совпавших с шахматным узором

_PARITY = (np.add.outer(np.arange(8), np.arange(8)) % 2).astype(bool)


def _cell_colors(roi: np.ndarray) -> np.ndarray:
    """Цвет фона каждой из 64 клеток (по углам клетки)."""
    r = cv2.resize(roi, (256, 256), interpolation=cv2.INTER_AREA).astype(np.float32)
    cells = r.reshape(8, 32, 8, 32, 3).transpose(0, 2, 1, 3, 4)
    a, b = 2, 6
    patches = np.concatenate([
        cells[:, :, a:b, a:b], cells[:, :, a:b, 32 - b:32 - a],
        cells[:, :, 32 - b:32 - a, a:b], cells[:, :, 32 - b:32 - a, 32 - b:32 - a],
    ], axis=2)
    return np.median(patches.reshape(8, 8, -1, 3), axis=2)


def checker_score(img: np.ndarray, rect) -> float:
    x, y, w, h = map(int, rect)
    H, W = img.shape[:2]
    if w < MIN_BOARD or h < MIN_BOARD or x < 0 or y < 0 or x + w > W or y + h > H:
        return 0.0
    cols = _cell_colors(img[y:y + h, x:x + w])
    A, B = cols[~_PARITY], cols[_PARITY]
    ma, mb = np.median(A, 0), np.median(B, 0)
    sep = float(np.linalg.norm(ma - mb))
    if sep < 20:
        return 0.0
    ok_a = (np.linalg.norm(A - ma, axis=1) < 0.4 * sep) & \
           (np.linalg.norm(A - ma, axis=1) < np.linalg.norm(A - mb, axis=1))
    ok_b = (np.linalg.norm(B - mb, axis=1) < 0.4 * sep) & \
           (np.linalg.norm(B - mb, axis=1) < np.linalg.norm(B - ma, axis=1))
    return float(ok_a.sum() + ok_b.sum()) / 64.0


def _contour_rects(gray: np.ndarray):
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    kernel = np.ones((3, 3), np.uint8)
    for lo, hi in ((30, 90), (8, 30)):
        edges = cv2.dilate(cv2.Canny(blur, lo, hi), kernel)
        cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            if w < 12 or h < 12:
                continue
            if abs(w - h) > 0.1 * max(w, h):
                continue
            if cv2.contourArea(c) < 0.7 * w * h:
                continue
            yield x, y, w, h


def _refine_spacing(vals, s):
    vals = np.unique(np.round(vals).astype(int))
    if len(vals) < 2:
        return s
    d = np.diff(vals)
    k = np.round(d / s)
    m = k > 0
    if not m.any() or k[m].sum() == 0:
        return s
    return float(d[m].sum() / k[m].sum())


def _grid_candidates(cells):
    """Из множества квадратных клеток одинакового размера строим возможные доски."""
    if len(cells) < 6:
        return []
    cells = np.array(cells, dtype=np.float32)
    sizes = (cells[:, 2] + cells[:, 3]) / 2
    out = []
    for s0 in np.unique(np.round(sizes / 2) * 2):
        grp = cells[np.abs(sizes - s0) <= max(2, s0 * 0.06)]
        if len(grp) < 6 or s0 * 8 < MIN_BOARD:
            continue
        s = float(np.median((grp[:, 2] + grp[:, 3]) / 2))
        # клетки должны лежать на общей решётке: группируем по остатку от деления
        key = np.stack([np.round(grp[:, 0] / s * 4) % 4, np.round(grp[:, 1] / s * 4) % 4], 1)
        uniq, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
        best = grp[inv.ravel() == np.argmax(cnt)]
        if len(best) < 6:
            continue
        sx = _refine_spacing(best[:, 0], s)
        sy = _refine_spacing(best[:, 1], s)
        s = (sx + sy) / 2
        anchor = best[np.argsort(best[:, 0] + best[:, 1])[len(best) // 2]]
        for i in range(8):
            for j in range(8):
                out.append((anchor[0] - i * s, anchor[1] - j * s, 8 * s, 8 * s))
    return out


def _refine(img: np.ndarray, rect, radius=4):
    """Подгонка к линиям сетки: на границах клеток резкий перепад цвета."""
    x, y, w, h = rect
    pad = radius + 4
    H, W = img.shape[:2]
    x0, y0 = max(0, int(x) - pad), max(0, int(y) - pad)
    x1, y1 = min(W, int(x + w) + pad), min(H, int(y + h) + pad)
    roi = img[y0:y1, x0:x1].astype(np.int16)
    gx = np.zeros(roi.shape[:2], np.float32)
    gy = np.zeros(roi.shape[:2], np.float32)
    gx[:, 1:] = np.abs(roi[:, 1:] - roi[:, :-1]).sum(2)   # перепад между столбцами i-1 и i
    gy[1:, :] = np.abs(roi[1:] - roi[:-1]).sum(2)
    gx = np.minimum(gx, 120)
    gy = np.minimum(gy, 120)
    bx, by, bs = x - x0, y - y0, (w + h) / 2
    best, best_rect = -1.0, rect
    for ds in range(-radius, radius + 1):
        size = bs + ds
        s = size / 8
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                ox, oy = bx + dx, by + dy
                xs = np.round(ox + s * np.arange(1, 8)).astype(int)
                ys = np.round(oy + s * np.arange(1, 8)).astype(int)
                r0, r1 = int(round(oy)), int(round(oy + size))
                c0, c1 = int(round(ox)), int(round(ox + size))
                if r0 < 0 or c0 < 0 or r1 > gx.shape[0] or c1 > gx.shape[1] \
                        or xs.max() >= gx.shape[1] or ys.max() >= gx.shape[0]:
                    continue
                score = gx[r0:r1, xs].mean() + gy[ys, c0:c1].mean()
                if score > best:
                    best, best_rect = score, (ox + x0, oy + y0, size, size)
    return best_rect


def find_board(img: np.ndarray):
    """Возвращает (x, y, size, size) доски на изображении или None."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    boards, cells = set(), []
    for x, y, w, h in _contour_rects(gray):
        if w >= MIN_BOARD:
            boards.add((x, y, w, h))
        elif w <= 200:
            cells.append((x, y, w, h))
    cands = list(boards) + _grid_candidates(cells)

    best, best_key = None, (0.0, 0)
    for r in cands:
        sc = checker_score(img, r)
        key = (round(sc, 3), r[2] * r[3])
        if sc >= MIN_SCORE and key > best_key:
            best, best_key = r, key
    if best is None:
        return None
    x, y, w, h = _refine(img, best)
    x, y, w = int(round(x)), int(round(y)), int(round(w))
    if checker_score(img, (x, y, w, w)) < MIN_SCORE:   # подгонка ушла не туда
        x, y, w = int(round(best[0])), int(round(best[1])), int(round(best[2]))
    return x, y, w, w

