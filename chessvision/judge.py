"""Оценка сделанного хода — как в разборе партий lichess / chess.com.

    book       ≡   теория (ход из дебютной базы)
    brilliant  !!  блестящий: лучший (или почти) ход с жертвой материала,
                   когда позиция ещё не выиграна
    best       ★   лучший: совпал с ходом движка или почти не уступает ему
    ok             обычный нормальный ход (без отметки)
    mistake    ?   ошибка: шансы на победу упали на 10-30 %
    blunder    ??  зевок: шансы упали на 30 %+, или ход допускает мат
"""
import math

import chess

MISTAKE_DROP = 0.10       # падение шансов (шкала -1..1, как на lichess)
BLUNDER_DROP = 0.30
BEST_DROP = 0.02          # не хуже лучшего хода больше чем на это — тоже «лучший»
BRILLIANT_DROP = 0.02     # блестящий ход должен быть лучшим или почти лучшим
BRILLIANT_MAX_BEFORE = 0.80   # ...и позиция до него ещё не выиграна (шансы < 80 %)
SACRIFICE_MIN = 2         # жертва: на поле хода теряется минимум 2 пешки материала

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


def win_chances(cp: int) -> float:
    """Шансы на победу -1..1 по оценке в сантипешках (формула lichess)."""
    return 2 / (1 + math.exp(-0.00368208 * max(-4000, min(4000, cp)))) - 1


def see(board: chess.Board, square: int, depth: int = 0) -> int:
    """Сколько материала выигрывает сторона, которая ходит, разменом на поле square
    (бьёт самой дешёвой фигурой, может и не бить). Связки учитываются через легальные ходы."""
    target = board.piece_at(square)
    if target is None or depth > 12:
        return 0
    caps = [m for m in board.legal_moves if m.to_square == square]
    if not caps:
        return 0
    m = min(caps, key=lambda mv: VALUES[board.piece_type_at(mv.from_square)])
    board.push(m)
    gain = VALUES[target.piece_type] - see(board, square, depth + 1)
    board.pop()
    return max(0, gain)


def sacrifice(parent: chess.Board, move: chess.Move) -> int:
    """Сколько материала (в пешках) отдаёт ход: что соперник выиграет на поле хода
    минус то, что этим ходом взято."""
    taken = parent.piece_type_at(move.to_square)
    if parent.is_en_passant(move):
        taken = chess.PAWN
    gained = VALUES[taken] if taken else 0
    child = parent.copy(stack=False)
    child.push(move)
    if child.is_checkmate():
        return 0
    return see(child, move.to_square) - gained


def classify(parent: chess.Board, move: chess.Move, before_cp: int, after_cp: int,
             best_move=None, book=None) -> dict:
    """before_cp — оценка позиции до хода, after_cp — после (обе с точки зрения белых).
    -> {"kind", "loss" (пешки), "drop" (шансы), "mate" (допускает мат), "sac" (жертва, пешки)}"""
    out = {"kind": "ok", "loss": 0.0, "drop": 0.0, "mate": False, "sac": 0}
    sign = 1 if parent.turn == chess.WHITE else -1      # всё — с точки зрения сходившего
    before, after = sign * before_cp, sign * after_cp
    drop = 0.0 if move == best_move else max(0.0, win_chances(before) - win_chances(after))
    out["drop"] = drop
    out["loss"] = 0.0 if move == best_move else max(0.0, (before - after) / 100)
    out["mate"] = after <= -90000 < before
    if drop < MISTAKE_DROP and book is not None and book.is_book(parent, move):
        out["kind"] = "book"     # теория — если только это не сомнительная «теория» вроде 1.e4 h5
    elif out["mate"] or drop >= BLUNDER_DROP:
        out["kind"] = "blunder"
    elif drop >= MISTAKE_DROP:
        out["kind"] = "mistake"
    elif drop <= BRILLIANT_DROP:
        sac = sacrifice(parent, move)
        out["sac"] = sac
        if (sac >= SACRIFICE_MIN and win_chances(before) < BRILLIANT_MAX_BEFORE
                and win_chances(after) > -0.3):
            out["kind"] = "brilliant"
        elif move == best_move or drop <= BEST_DROP:
            out["kind"] = "best"
    return out
