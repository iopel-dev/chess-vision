"""Дебютная теория: база названий дебютов lichess (CC0, chessvision/data/openings.tsv).

Ход считается теоретическим, если и позиция до него, и позиция после встречаются
в одной из ~3 900 дебютных линий базы. Ключ позиции — расстановка + очередь хода
(без прав на рокировку и взятия на проходе), чтобы работать и с позициями,
которые программа начала отслеживать с середины партии.
"""
from pathlib import Path

import chess

DATA = Path(__file__).resolve().parent / "data" / "openings.tsv"
INDEX = DATA.with_name("openings_index.tsv")   # готовый индекс позиций: грузится мгновенно


def _key(board: chess.Board) -> str:
    return f"{board.board_fen()} {'w' if board.turn else 'b'}"


class OpeningBook:
    def __init__(self, path=DATA, index=INDEX):
        self.positions = set()     # все позиции, встречающиеся в дебютных линиях
        self.names = {}            # позиция в конце линии -> "ECO Название"
        self.positions.add(_key(chess.Board()))
        path, index = Path(path), Path(index)
        if index.exists() and (not path.exists() or index.stat().st_mtime >= path.stat().st_mtime):
            self._load_index(index)
        elif path.exists():
            self._build(path)
            self._save_index(index)

    def _load_index(self, index):
        with open(index, encoding="utf-8") as f:
            for line in f:
                key, _, name = line.rstrip("\n").partition("\t")
                self.positions.add(key)
                if name:
                    self.names[key] = name

    def _save_index(self, index):
        try:
            with open(index, "w", encoding="utf-8") as f:
                for key in sorted(self.positions):
                    f.write(f"{key}\t{self.names.get(key, '')}\n")
        except OSError:
            pass                   # нет прав на запись — просто строим каждый раз

    def _build(self, path):
        start = chess.Board()
        with open(path, encoding="utf-8") as f:
            next(f, None)          # заголовок
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3:
                    continue
                eco, name, pgn = parts[:3]
                b = start.copy()
                try:
                    for tok in pgn.split():
                        if tok.endswith("."):
                            continue
                        b.push_san(tok)
                        self.positions.add(_key(b))
                except ValueError:
                    continue
                self.names.setdefault(_key(b), f"{eco} {name}")

    def is_book(self, parent: chess.Board, move: chess.Move) -> bool:
        if _key(parent) not in self.positions:
            return False
        child = parent.copy(stack=False)
        child.push(move)
        return _key(child) in self.positions

    def name(self, board: chess.Board):
        """Название дебюта: самой «глубокой» названной позиции на пути к текущей."""
        b = board.copy()
        while True:
            n = self.names.get(_key(b))
            if n:
                return n
            if not b.move_stack:
                return None
            b.pop()
