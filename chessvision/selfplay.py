"""Самоигра (Auto-ходы) на виртуальной доске: сначала дебют по ходам из дебютной книги
(Lichess Opening Explorer из интернета или локальная база), затем лучшие ходы Stockfish
за обе стороны.

Работает только на виртуальной доске — на сайте ничего не нажимается. Использует
отдельный экземпляр Stockfish (половина потоков), чтобы не мешать живому анализу.
"""
import os
import threading
import time

import chess
import chess.engine

from .i18n import tr

SPEEDS = {"fast": 0.3, "medium": 1.0, "slow": 3.0}     # секунд на ход
SPEED_NAMES = {"fast": "быстро", "medium": "средне", "slow": "медленно"}
MAX_PLIES = 400

REASONS = {
    chess.Termination.CHECKMATE: "мат",
    chess.Termination.STALEMATE: "пат",
    chess.Termination.INSUFFICIENT_MATERIAL: "недостаточно материала",
    chess.Termination.SEVENTYFIVE_MOVES: "правило 75 ходов",
    chess.Termination.FIVEFOLD_REPETITION: "пятикратное повторение",
    chess.Termination.FIFTY_MOVES: "правило 50 ходов",
    chess.Termination.THREEFOLD_REPETITION: "троекратное повторение",
}


class SelfPlay(threading.Thread):
    def __init__(self, engine_path: str, board: chess.Board, move_time: float = 1.0, book=None,
                 on_move=None):
        """book: explorer.Book или None; on_move(номер полухода, san, источник) — после каждого хода."""
        super().__init__(daemon=True, name="selfplay")
        self.path = engine_path
        self.move_time = move_time
        self.start_board = board.copy(stack=False)
        self.board = self.start_board.copy()
        self.sans = []
        self.moves = []           # сыгранные ходы (chess.Move)
        self.sources = []         # откуда каждый ход: название книги или "Stockfish"
        self.book = book
        self.on_move = on_move
        self.last = None
        self.result = None        # "1-0 (мат)" и т.п., когда партия окончена
        self.error = None
        self._lock = threading.Lock()
        self._halt = threading.Event()

    def stop(self):
        self._halt.set()

    @property
    def running(self) -> bool:
        return self.is_alive() and not self._halt.is_set()

    def snapshot(self):
        with self._lock:
            return self.board.copy(stack=False), list(self.sans), self.last, self.result

    def game(self):
        """-> (начальная позиция, сыгранные ходы) — для разбора партии."""
        with self._lock:
            return self.start_board.copy(), list(self.moves)

    @property
    def book_plies(self) -> int:
        with self._lock:
            return sum(1 for s in self.sources if s != "Stockfish")

    def pgn_moves(self) -> str:
        """Сыгранные ходы в виде «12. Nf3 Nc6 13. …» с правильной нумерацией."""
        with self._lock:
            sans = list(self.sans)
        b = self.start_board
        num, white = b.fullmove_number, b.turn
        out = [] if white else [f"{num}..."]
        for san in sans:
            if white:
                out.append(f"{num}.")
            out.append(san)
            if not white:
                num += 1
            white = not white
        return " ".join(out)

    def run(self):
        engine = None
        try:
            engine = chess.engine.SimpleEngine.popen_uci(self.path, timeout=60)
            threads = max(1, (os.cpu_count() or 2) // 2)
            engine.configure({k: v for k, v in {"Threads": threads, "Hash": 128}.items() if k in engine.options})
            while not self._halt.is_set():
                outcome = self.board.outcome(claim_draw=True)
                if outcome is not None:
                    self.result = f"{outcome.result()} ({tr(REASONS.get(outcome.termination, 'конец партии'))})"
                    break
                if len(self.sans) >= MAX_PLIES:
                    self.result = tr("остановлено: слишком длинная партия")
                    break
                t0 = time.time()
                picked = self.book.pick(self.board) if self.book is not None else None
                if picked is not None:
                    move, source = picked
                else:
                    move = engine.play(self.board, chess.engine.Limit(time=self.move_time)).move
                    source = "Stockfish"
                if self._halt.is_set() or move is None:
                    break
                with self._lock:
                    san = self.board.san(move)
                    self.sans.append(san)
                    self.sources.append(source)
                    self.moves.append(move)
                    self.board.push(move)
                    self.last = move
                if self.on_move is not None:
                    self.on_move(len(self.sans), san, source)
                # движок мог ответить быстрее (например, единственный ход) — держим темп
                self._halt.wait(max(0.0, self.move_time - (time.time() - t0)))
        except Exception as e:
            self.error = tr("Самоигра остановлена: {e}", e=e)
        finally:
            if engine is not None:
                try:
                    engine.quit()
                except Exception:
                    pass
