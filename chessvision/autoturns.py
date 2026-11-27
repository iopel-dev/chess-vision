"""Auto-ходы в консоли: партия на виртуальной доске без распознавания экрана.

Дебют играется по ходам из дебютной книги (Lichess Opening Explorer из интернета,
без связи — локальная база), дальше каждый ход — лучший ход Stockfish.
На сайтах ничего не нажимается.
"""
import chess
import chess.pgn

from .explorer import Book
from .selfplay import SelfPlay


def run(engine_path: str, fen=None, book="masters", book_mode="random", move_time=1.0,
        pgn_path=None) -> int:
    board = chess.Board(fen) if fen else chess.Board()
    if board.is_game_over():
        print("Партия в этой позиции уже окончена.")
        return 1
    bk = Book(book, book_mode)
    print(f"Auto-ходы: книга — {bk.status()}, затем Stockfish ({move_time:g} с на ход). Ctrl+C — стоп.",
          flush=True)

    last_opening = [None]

    def on_move(ply, san, source):
        i = ply - 1 + (0 if board.turn == chess.WHITE else 1)   # полуходы от хода белых
        num = board.fullmove_number + i // 2
        prefix = f"{num}." if i % 2 == 0 else f"{num}..."
        line = f"{prefix:>6} {san:<8} {source}"
        if bk.opening and bk.opening != last_opening[0] and source != "Stockfish":
            last_opening[0] = bk.opening
            line += f"   ≡ {bk.opening}"
        print(line, flush=True)

    sp = SelfPlay(engine_path, board, move_time, book=bk, on_move=on_move)
    sp.start()
    try:
        while sp.is_alive():
            sp.join(0.2)
    except KeyboardInterrupt:
        sp.stop()
        sp.join(5)
        print("\nОстановлено.")

    if bk.online_error and book in ("masters", "lichess"):
        print(f"Внимание: {bk.online_error} — дебют доигран по локальной базе.")
    if sp.error:
        print(sp.error)
    final, sans, _, result = sp.snapshot()
    print(f"\nИтог: {result or 'не доиграно'}  ·  из книги {sp.book_plies} полуходов, всего {len(sans)}")
    print(sp.pgn_moves())

    if pgn_path:
        game = chess.pgn.Game()
        if fen:
            game.setup(board)
        game.headers.update(Event="Chess Vision Auto", White="Stockfish", Black="Stockfish",
                            Result=(result or "*").split()[0])
        if bk.opening:
            game.headers["Opening"] = bk.opening
        node = game
        b = board.copy()
        for san in sans:
            move = b.parse_san(san)
            b.push(move)
            node = node.add_variation(move)
        with open(pgn_path, "w", encoding="utf-8") as f:
            print(game, file=f)
        print(f"PGN сохранён: {pgn_path}")
    return 0 if not sp.error else 1
