"""Самопроверка без реального сайта: рисуем «скриншот» с доской и прогоняем пайплайн.

Запуск:  python -m tests.test_synthetic
"""
import random
import sys
from pathlib import Path

import chess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from chessvision.detector import find_board            # noqa: E402
from chessvision.recognizer import Recognizer          # noqa: E402
from chessvision.tracker import PositionTracker        # noqa: E402

FONT = "C:/Windows/Fonts/seguisym.ttf"
THEMES = [((235, 236, 208), (115, 149, 82)),   # зелёная
          ((240, 217, 181), (181, 136, 99)),   # коричневая
          ((222, 227, 230), (140, 162, 173))]  # синяя
# Наборы фигур: заливка белых, контур белых, заливка чёрных, контур чёрных, тень (None — без тени)
STYLES = {
    "classic": ((250, 250, 250), (20, 20, 20), (30, 30, 30), None, None),
    "shaded":  ((214, 212, 208), (70, 68, 66), (88, 85, 82), (150, 148, 145), (0, 0, 0)),
    "cream":   ((236, 226, 196), (120, 100, 70), (64, 58, 52), (30, 26, 22), (0, 0, 0)),
    "wood":    ((222, 186, 132), (110, 70, 30), (92, 52, 22), (40, 22, 8), None),
    "colored": ((240, 200, 120), (120, 70, 0), (60, 90, 170), (20, 30, 70), None),
}
# Необычные доски
HARD_THEMES = {
    "газета": ((250, 250, 250), (120, 120, 120)),
    "тёмная": ((105, 115, 125), (40, 44, 50)),
    "фиолет": ((200, 190, 235), (110, 80, 170)),
    "песок":  ((238, 232, 220), (205, 190, 160)),
    "лёд":    ((230, 240, 250), (170, 200, 225)),
}
GLYPH = {"k": "\u265a", "q": "\u265b", "r": "\u265c", "b": "\u265d", "n": "\u265e", "p": "\u265f"}
OUTLINE = {"k": "\u2654", "q": "\u2655", "r": "\u2656", "b": "\u2657", "n": "\u2658", "p": "\u2659"}


def render(board, origin, size, theme, flipped=False, highlight=(), screen=(1600, 900), seed=0, style="classic"):
    rnd = random.Random(seed)
    img = Image.new("RGB", screen, (38, 36, 33))
    d = ImageDraw.Draw(img)
    for _ in range(40):   # «интерфейс» вокруг доски
        x, y = rnd.randrange(screen[0]), rnd.randrange(screen[1])
        w, h = rnd.randrange(20, 200), rnd.randrange(10, 60)
        if x + w > origin[0] - 5 and x < origin[0] + size + 5 and y + h > origin[1] - 5 and y < origin[1] + size + 5:
            continue
        d.rectangle([x, y, x + w, y + h], fill=tuple(rnd.randrange(256) for _ in range(3)))
    cs = size / 8
    font = ImageFont.truetype(FONT, int(cs * 0.85))
    lab = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", int(cs * 0.16))
    for r in range(8):
        for c in range(8):
            sq = chess.square(7 - c, r) if flipped else chess.square(c, 7 - r)
            x0, y0 = origin[0] + c * cs, origin[1] + r * cs
            col = theme[(r + c) % 2]
            if sq in highlight:
                col = tuple(int(0.6 * a + 0.4 * b) for a, b in zip(col, (246, 246, 105)))
            d.rectangle([round(x0), round(y0), round(x0 + cs) - 1, round(y0 + cs) - 1], fill=col)
            if c == 0:
                d.text((x0 + 3, y0 + 2), str(chess.square_rank(sq) + 1), font=lab, fill=theme[(r + c + 1) % 2])
            if r == 7:
                d.text((x0 + cs - cs * 0.16, y0 + cs - cs * 0.2), "abcdefgh"[chess.square_file(sq)],
                       font=lab, fill=theme[(r + c + 1) % 2])
            p = board.piece_at(sq)
            if p:
                s = p.symbol().lower()
                pos = (x0 + cs / 2, y0 + cs / 2)
                wf, wo, bf, bo, shadow = STYLES[style]
                if shadow is not None:   # полупрозрачная тень под фигурой (как на chess.com)
                    sh = tuple(int(0.65 * a + 0.35 * b) for a, b in zip(col, shadow))
                    d.text((pos[0] + cs * 0.04, pos[1] + cs * 0.05), GLYPH[s], font=font, fill=sh, anchor="mm")
                fill, outline = (wf, wo) if p.color else (bf, bo)
                d.text(pos, GLYPH[s], font=font, fill=fill, anchor="mm")
                if outline is not None:
                    d.text(pos, OUTLINE[s], font=font, fill=outline, anchor="mm")
    return np.array(img)[:, :, ::-1].copy()


def main():
    ok = True
    for ti, theme in enumerate(THEMES):
        for flipped in (False, True):
            origin, size = (310 + 37 * ti, 95 + 11 * ti), 520 + 40 * ti
            start = chess.Board()
            shot = render(start, origin, size, theme, flipped, seed=ti)
            rect = find_board(shot)
            err = None if rect is None else max(abs(rect[0] - origin[0]), abs(rect[1] - origin[1]),
                                                abs(rect[2] - size))
            print(f"theme {ti} flipped={flipped}: board {rect} expected {origin + (size,)} err={err}")
            if rect is None or err > 3:
                ok = False
                continue
            x, y, s, _ = rect
            crop = lambda im: im[y:y + s, x:x + s]
            rec, fl = Recognizer.calibrate(crop(shot))
            assert fl == flipped, "orientation"
            tr = PositionTracker()
            tr.default_turn = chess.BLACK if flipped else chess.WHITE
            game = chess.Board()
            moves = "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O h3 Nb8 d4 Nbd7".split()
            for frame in range(len(moves) + 1):
                hl = ()
                if frame:
                    mv = game.push_san(moves[frame - 1])
                    hl = (mv.from_square, mv.to_square)
                img = render(game, origin, size, theme, flipped, highlight=hl, seed=ti)
                placement, unknown = rec.read(crop(img), fl)
                if placement != game.board_fen() or unknown:
                    print(f"  frame {frame}: recognition mismatch\n   got  {placement}\n   want {game.board_fen()}")
                    ok = False
                    break
                tr.update(placement)
                tr.update(placement)
                if tr.board.fen() != game.fen():
                    print(f"  frame {frame}: tracker mismatch {tr.board.fen()} != {game.fen()}")
                    ok = False
                    break
            else:
                print(f"  {len(moves)} ходов распознаны и восстановлены, FEN совпадает")
            ok &= check_turn_recovery(rec, fl, crop, origin, size, theme, flipped, ti, moves)
    ok &= check_styles()
    ok &= check_judge()
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


def check_judge():
    """Оценка ходов (лучший / блестящий / теория / ошибка / зевок) на заданных оценках."""
    from chessvision.judge import classify, sacrifice
    from chessvision.openings import OpeningBook
    book = OpeningBook()
    ok = True

    def pos(moves, fen=None):
        b = chess.Board(fen) if fen else chess.Board()
        for m in moves.split():
            b.push_san(m)
        return b

    legal = pos("e4 e5 Nf3 d6 Bc4 Bg4 Nc3 g6")
    cases = [
        # (название, позиция до хода, ход, оценка до, оценка после (белых), лучший ход, ожидаемо)
        ("теория: Итальянская Nf6", pos("e4 e5 Nf3 Nc6 Bc4"), "Nf6", 30, 30, None, "book"),
        ("1.e4 h5 — «теория», но ошибка", pos("e4"), "h5", 30, 110, None, "mistake"),
        ("Nf6?? допускает мат", pos("e4 e5 Qh5 Nc6 Bc4"), "Nf6", 0, 100000, None, "blunder"),
        ("лучший ход = ход движка", legal, "Nxe5", 250, 250, legal.parse_san("Nxe5"), "brilliant"),
        ("лучший ход вне теории", pos("", "r1bq1rk1/pp2bppp/2n1pn2/3p4/3P4/2NBPN2/PP3PPP/R2QK2R w KQ - 0 9"),
         "O-O", 30, 28, None, "best"),
        ("ошибка −0.7", pos("e4 e5 Nf3 Nc6 d4"), "d6", 40, 110, None, "mistake"),
    ]
    for name, b, san, before, after, best, want in cases:
        got = classify(b, b.parse_san(san), before, after, best, book)["kind"]
        if got != want:
            print(f"  оценка хода «{name}»: ожидали {want}, получили {got}")
            ok = False
    if sacrifice(legal, legal.parse_san("Nxe5")) != 2:
        print("  жертва в ловушке Легаля посчитана неверно")
        ok = False
    if book.name(pos("e4 e5 Nf3 Nc6 Bc4 Nf6")) != "C55 Italian Game: Two Knights Defense":
        print("  название дебюта не определилось")
        ok = False
    print("оценка ходов и дебюты:", "OK" if ok else "ОШИБКИ")
    return ok


def check_styles():
    """Наборы фигур (тени, кремовые, «дерево», цветные) × необычные доски:
    белые не должны путаться с чёрными."""
    ok = True
    moves = "e4 e5 Nf3 Nc6 Bb5 a6 O-O Nf6".split()
    crop = lambda im: im[100:620, 300:820]
    for style in STYLES:
        errs = []
        for name, th in HARD_THEMES.items():
            try:
                rec, fl = Recognizer.calibrate(crop(render(chess.Board(), (300, 100), 520, th, style=style)))
            except Exception as e:
                errs.append(f"{name}: калибровка ({e})")
                continue
            g = chess.Board()
            for m in moves:
                mv = g.push_san(m)
                p, u = rec.read(crop(render(g, (300, 100), 520, th, highlight=(mv.from_square, mv.to_square),
                                            style=style)), fl)
                if p != g.board_fen() or u:
                    errs.append(f"{name}: после {m} {p}")
                    break
        print(f"набор {style:8s}: " + ("все доски OK" if not errs else "; ".join(errs)))
        ok &= not errs
    return ok


def check_turn_recovery(rec, fl, crop, origin, size, theme, flipped, ti, moves):
    """Сценарии, где раньше сбивалась очередь хода."""
    ok = True

    def frame(game):
        mv = game.peek() if game.move_stack else None
        hl = (mv.from_square, mv.to_square) if mv else ()
        img = crop(render(game, origin, size, theme, flipped, highlight=hl, seed=ti))
        placement, _ = rec.read(img, fl)
        return placement, rec.last_mover

    # 1) подсветка последнего хода распознаётся
    g = chess.Board()
    for m in moves[:6]:
        g.push_san(m)
        _, lm = frame(g)
        if lm != (not g.turn):
            print(f"  подсветка: после {m} ожидали {'белые' if not g.turn else 'чёрные'}, получили {lm}")
            ok = False

    # 2) между снимками пропало 3-4 полухода (бот ответил мгновенно, предход)
    for step in (3, 4):
        tr, g = PositionTracker(), chess.Board()
        tr.default_turn = chess.BLACK if flipped else chess.WHITE
        p0, _ = frame(g)
        tr.update(p0)
        tr.update(p0)
        for i in range(0, len(moves), step):
            for m in moves[i:i + step]:
                g.push_san(m)
            p, lm = frame(g)
            tr.update(p, lm)
            tr.update(p, lm)
            if tr.board.fen().split()[:4] != g.fen().split()[:4]:
                print(f"  пропуск {step} полуходов: {tr.board.fen()} != {g.fen()}")
                ok = False
                break

    # 3) слежение началось с середины партии, когда ходят ЧЁРНЫЕ (а снизу белые)
    g = chess.Board()
    for m in moves[:9]:
        g.push_san(m)
    tr = PositionTracker()
    tr.default_turn = chess.WHITE
    p, lm = frame(g)
    tr.update(p, lm)
    tr.update(p, lm)
    if tr.board.turn != g.turn:
        print("  середина партии: очередь хода не определилась по подсветке")
        ok = False

    # 4) очередь хода сбилась — должна исправиться сама за несколько кадров
    tr.set_turn(not g.turn)
    for _ in range(4):
        tr.update(p, lm)
    if tr.board.turn != g.turn:
        print("  неверная очередь хода не исправилась")
        ok = False
    if ok:
        print("  очередь хода: подсветка, пропуск 3-4 полуходов, середина партии, самоисправление — OK")
    return ok


if __name__ == "__main__":
    sys.exit(main())
