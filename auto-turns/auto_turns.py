"""Auto-ходы: дебют по ходам из интернета (Lichess Opening Explorer), дальше лучший ход Stockfish.

Тонкая обёртка над main.py + пакетом chessvision — то же самое, что `python main.py --auto-turns`.
Партия идёт на виртуальной доске в консоли, на сайтах ничего не нажимается.

  python auto-turns/auto_turns.py
  python auto-turns/auto_turns.py --book local --book-mode top --move-time 0.3
  python auto-turns/auto_turns.py --fen "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
  python auto-turns/auto_turns.py --pgn партия.pgn
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # корень проекта: main.py и chessvision/

import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main.main(["--auto-turns", *sys.argv[1:]]))
