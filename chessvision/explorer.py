"""Дебютная книга для Auto-ходов: сначала дебют по ходам из интернета, потом Stockfish.

Источники:
  masters — партии мастеров (Lichess Opening Explorer, explorer.lichess.ovh/masters)
  lichess — партии игроков lichess 2000+ (может требовать токен: переменная LICHESS_TOKEN)
  local   — без интернета: линии из chessvision/data/openings.tsv
  off     — без книги, сразу Stockfish

Если интернет недоступен или сервер ограничил запросы (HTTP 429), книга сама
переходит на локальную базу. Ответы кэшируются по позиции, запросы идут по одному.
"""
import json
from collections import Counter
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import chess

from . import __version__
from .openings import DATA, OpeningBook, _key

BOOKS = {"masters": "Lichess: мастера", "lichess": "Lichess: игроки 2000+",
         "local": "локальная база", "off": "без книги"}
URLS = {"masters": "https://explorer.lichess.ovh/masters",
        "lichess": "https://explorer.lichess.ovh/lichess"}
MIN_GAMES = 30          # меньше партий в позиции — дебют кончился, дальше думает Stockfish
MIN_SHARE = 0.05        # редкие ходы (< 5 % партий) из книги не играем
MAX_BOOK_PLIES = 30     # книжная часть не длиннее 15 ходов


class Book:
    def __init__(self, source="masters", mode="random", timeout=5.0, local=None):
        if source not in BOOKS:
            raise ValueError(f"неизвестная книга: {source}")
        self.source = source
        self.mode = mode                 # "random" — по популярности с весами, "top" — самый частый ход
        self.timeout = timeout
        self.token = os.environ.get("LICHESS_TOKEN")
        self._local = local
        self._counts = None              # позиция -> сколько линий локальной базы через неё проходит
        self._cache = {}
        self._lock = threading.Lock()    # lichess просит не слать запросы параллельно
        self.online_error = None         # почему перешли на локальную базу
        self.opening = None              # название дебюта последней книжной позиции
        self.out_of_book = source == "off"
        self.plies = 0                   # сколько книжных ходов уже сыграно

    # ---------------- выбор хода ----------------
    def pick(self, board: chess.Board):
        """-> (ход, источник) или None, когда книга кончилась."""
        if self.out_of_book or self.plies >= MAX_BOOK_PLIES:
            return None
        res = None
        if self.source in URLS and self.online_error is None:
            res = self._online(board)
            if res is None and self.online_error is None:   # сервер ответил, но позиция уже не дебютная
                self.out_of_book = True
                return None
        if res is None:
            res = self._local_pick(board)
        if res is None:
            self.out_of_book = True
        else:
            self.plies += 1
        return res

    def _choose(self, cands):
        """cands: [(ход, вес)] -> ход."""
        if self.mode == "top":
            return max(cands, key=lambda c: c[1])[0]
        return random.choices([m for m, _ in cands], weights=[w for _, w in cands])[0]

    # ---------------- интернет ----------------
    def _online(self, board):
        data = self._fetch(board.fen())
        if data is None:
            return None
        total = sum(m["white"] + m["draws"] + m["black"] for m in data.get("moves", []))
        if total < MIN_GAMES:
            return None
        cands = []
        for m in data["moves"]:
            n = m["white"] + m["draws"] + m["black"]
            try:
                move = chess.Move.from_uci(m["uci"])
            except ValueError:
                continue
            if n / total >= MIN_SHARE and move in board.legal_moves:
                cands.append((move, n))
        if not cands:
            return None
        move = self._choose(cands)
        op = next((m.get("opening") for m in data["moves"] if m["uci"] == move.uci()), None) \
            or data.get("opening")
        if op:
            self.opening = f"{op['eco']} {op['name']}"
        return move, BOOKS[self.source]

    def _fetch(self, fen):
        if fen in self._cache:
            return self._cache[fen]
        q = {"fen": fen, "moves": 12, "topGames": 0, "recentGames": 0}
        if self.source == "lichess":
            q.update(speeds="blitz,rapid,classical", ratings="2000,2200,2500")
        req = urllib.request.Request(URLS[self.source] + "?" + urllib.parse.urlencode(q),
                                     headers={"User-Agent": f"chess-vision/{__version__}",
                                              "Accept": "application/json"})
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        with self._lock:
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.load(r)
            except urllib.error.HTTPError as e:
                self.online_error = {429: "lichess ограничил запросы (429)",
                                     401: "нужен токен LICHESS_TOKEN"}.get(e.code, f"HTTP {e.code}")
                return None
            except (urllib.error.URLError, OSError, ValueError) as e:
                self.online_error = f"нет связи с lichess ({getattr(e, 'reason', e)})"
                return None
            time.sleep(0.2)                # вежливая пауза между запросами
        self._cache[fen] = data
        return data

    # ---------------- локальная база ----------------
    def _local_pick(self, board):
        if self._local is None:
            self._local = OpeningBook()
        if self._counts is None:
            self._counts = _line_counts()
        book = self._local
        if _key(board) not in book.positions:
            return None
        cands = []
        for move in board.legal_moves:
            child = board.copy(stack=False)
            child.push(move)
            n = self._counts.get(_key(child), 0)
            if n:
                cands.append((move, n))
        if not cands:
            return None
        best = max(n for _, n in cands)          # редкие побочные линии не играем
        cands = [c for c in cands if c[1] >= best * MIN_SHARE]
        if not cands:
            return None
        move = self._choose(cands)
        child = board.copy()
        child.push(move)
        name = book.name(child)
        if name:
            self.opening = name
        return move, BOOKS["local"]

    def status(self) -> str:
        if self.source == "off":
            return "без книги"
        if self.online_error and self.source in URLS:
            return f"{BOOKS['local']} ({self.online_error})"
        return BOOKS[self.source]


def _line_counts(path=DATA) -> Counter:
    """Популярность позиций локальной базы: через сколько дебютных линий проходит каждая."""
    counts = Counter()
    try:
        f = open(path, encoding="utf-8")
    except OSError:
        return counts
    with f:
        next(f, None)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            b = chess.Board()
            try:
                for tok in parts[2].split():
                    if not tok.endswith("."):
                        b.push_san(tok)
                        counts[_key(b)] += 1
            except ValueError:
                continue
    return counts
