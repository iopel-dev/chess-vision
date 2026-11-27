"""Виртуальная копия партии.

По последовательности распознанных расстановок восстанавливает сделанные
ходы, поэтому знает, чей ход, права на рокировку и взятие на проходе.

Чтобы не сбиться с очереди хода:
  * между двумя снимками ищется до MAX_PLIES полуходов (бот ответил мгновенно,
    сработал предход, захват подтормозил) — выбирается самое короткое объяснение;
  * подсказка сайта: подсветка последнего хода показывает, кто ходил последним.
    Она помогает выбрать объяснение, задаёт очередь хода для «чистой» позиции и
    исправляет очередь, если та всё-таки разошлась с доской.
"""
import time

import chess

STABLE_FRAMES = 2       # расстановка должна продержаться столько кадров (анимация ходов)
MAX_PLIES = 4           # сколько пропущенных полуходов можно восстановить
SEARCH_TIME = 0.8       # предел времени перебора на одно изменение позиции, с
FIX_TURN_FRAMES = 3     # столько кадров подряд подсветка должна противоречить очереди хода


class PositionTracker:
    def __init__(self):
        self.board = None
        self.default_turn = chess.WHITE
        self._cand = None
        self._cand_n = 0
        self._bad_turn = 0

    def reset(self):
        self.board = None
        self._cand = None
        self._cand_n = 0
        self._bad_turn = 0

    def update(self, placement: str, last_mover=None) -> bool:
        """Новая распознанная расстановка (+ кто ходил последним по подсветке сайта,
        если известно). True, если позиция или очередь хода изменились."""
        if self.board is not None and placement == self.board.board_fen():
            self._cand = None
            return self._check_turn(last_mover)
        self._bad_turn = 0
        if placement != self._cand:
            self._cand, self._cand_n = placement, 1
        else:
            self._cand_n += 1
        if self._cand_n < STABLE_FRAMES:
            return False
        self._cand = None
        new = self._continuation(placement, last_mover) if self.board is not None else None
        self.board = new or self._fresh(placement, last_mover)
        return True

    def set_turn(self, color: bool) -> bool:
        if self.board is None or self.board.turn == color:
            return False
        b = self.board.copy(stack=False)
        b.turn = color
        b.ep_square = None
        if not b.is_valid():               # например, тогда «не ходящий» стоял бы под шахом
            return False
        self.board = b
        self._bad_turn = 0
        return True

    # ------------------------------------------------------------
    def _check_turn(self, last_mover) -> bool:
        """Позиция не менялась: сверяем очередь хода с подсветкой последнего хода."""
        if last_mover is None or self.board.turn != last_mover:
            self._bad_turn = 0
            return False
        self._bad_turn += 1               # по подсветке последним ходил тот, чей сейчас «ход»
        if self._bad_turn < FIX_TURN_FRAMES:
            return False
        return self.set_turn(not last_mover)

    def _continuation(self, target: str, last_mover):
        """Самая короткая цепочка ходов (1..MAX_PLIES) к новой расстановке.
        Сначала при текущей очереди хода, затем — если очередь была определена неверно."""
        base = self.board
        alt = base.copy(stack=False)
        alt.turn = not alt.turn
        alt.ep_square = None
        variants = [base] + ([alt] if alt.is_valid() else [])

        tb = chess.BaseBoard(target)
        diff = {sq for sq in chess.SQUARES if base.piece_at(sq) != tb.piece_at(sq)}
        self._t = tb
        self._deadline = time.perf_counter() + SEARCH_TIME
        fallback = None
        for depth in range(1, MAX_PLIES + 1):
            for v in variants:
                b = v.copy()
                if not self._dfs(b, target, depth, diff):
                    continue
                # подсветка сайта говорит, кто ходил последним — объяснение должно с ней совпасть
                if last_mover is None or b.turn != last_mover:
                    return b
                fallback = fallback or b
            if time.perf_counter() > self._deadline:
                break
        return fallback

    def _mismatch(self, b) -> int:
        """Сколько клеток ещё отличается от цели (битбордами — быстро)."""
        t = self._t
        m = ((b.occupied_co[0] ^ t.occupied_co[0]) | (b.occupied_co[1] ^ t.occupied_co[1])
             | (b.pawns ^ t.pawns) | (b.knights ^ t.knights) | (b.bishops ^ t.bishops)
             | (b.rooks ^ t.rooks) | (b.queens ^ t.queens) | (b.kings ^ t.kings))
        return bin(m).count("1")

    def _dfs(self, b, target, depth, diff) -> bool:
        """Перебор ходов глубиной depth. Рассматриваем только ходы, затрагивающие
        изменившиеся клетки, и отсекаем ветки, где за оставшиеся ходы цель не достижима
        (обычный ход меняет 2 клетки; +4 на возможные рокировки/взятия на проходе).
        При успехе ходы остаются в b."""
        if depth == 0:
            return b.board_fen() == target
        if self._mismatch(b) > 2 * depth + 4 or time.perf_counter() > self._deadline:
            return False
        for m in list(b.legal_moves):
            if m.from_square not in diff and m.to_square not in diff:
                continue
            b.push(m)
            if self._dfs(b, target, depth - 1, diff):
                return True
            b.pop()
        return False

    def _fresh(self, placement: str, last_mover=None):
        b = chess.Board(None)
        b.set_board_fen(placement)
        if placement == chess.STARTING_BOARD_FEN:
            b.turn = chess.WHITE
        elif last_mover is not None:
            b.turn = not last_mover        # ходит тот, кто НЕ делал последний (подсвеченный) ход
        else:
            b.turn = self.default_turn
        rights = ""
        if b.piece_at(chess.E1) == chess.Piece(chess.KING, chess.WHITE):
            if b.piece_at(chess.H1) == chess.Piece(chess.ROOK, chess.WHITE):
                rights += "K"
            if b.piece_at(chess.A1) == chess.Piece(chess.ROOK, chess.WHITE):
                rights += "Q"
        if b.piece_at(chess.E8) == chess.Piece(chess.KING, chess.BLACK):
            if b.piece_at(chess.H8) == chess.Piece(chess.ROOK, chess.BLACK):
                rights += "k"
            if b.piece_at(chess.A8) == chess.Piece(chess.ROOK, chess.BLACK):
                rights += "q"
        b.set_castling_fen(rights or "-")
        if not b.is_valid():
            b.turn = not b.turn       # например, под шахом стоит тот, кто «не ходит»
            if not b.is_valid():
                b.turn = not b.turn
        return b
