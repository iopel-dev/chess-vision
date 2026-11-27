# Chess Vision

**Language / Язык:** **English** | [Русский](README.ru.md)

> ## ⚠ Disclaimer
>
> This program is intended for analysis and study: reviewing positions and your
> own games (PGN, Virtual Game Review), playing against the engine on a virtual
> board, playing against bots.
>
> * **The program never clicks anything** and never makes moves for you in any window.
> * **You use the program at your own risk.** The author is not responsible for
>   your accounts on any websites or services being banned, restricted or
>   deleted, for any violation of their rules, or for any other consequences of
>   using the program or modified versions of it.
> * Engine assistance in games against live opponents is forbidden by the rules
>   of chess websites and tournaments. Do not use the program for that.
>
> The program is provided "as is", without any warranty
> (GPL-3.0, sections 15–16, see [LICENSE](LICENSE)).

Finds a chessboard on the screen, builds a virtual copy of it and highlights the
best Stockfish 19 moves in **green** in real time (NNUE network, all CPU cores,
large hash).

The program's interface is in Russian; button names below are given in Russian
with an English translation.

## Getting started

```
pip install -r requirements.txt
python main.py
```

If Stockfish is not found in the `engine/` folder, it is downloaded automatically
(or manually: `python get_stockfish.py`).

## Command-line options

| Flag | What it does |
|---|---|
| `--auto-find` | periodically search for the board again (window moved, page scrolled, tab switched) |
| `--auto-find-time SEC` | auto-search interval, 5 s by default; implies `--auto-find` |
| `--no-window` | no program window: highlights over the board only, best moves are printed to the console, exit with Ctrl+C |
| `--gdi` | draw highlights directly on the screen with GDI instead of a transparent overlay window |
| `--external-window [TITLE]` | go through all windows and look for a board in any of them; the window is captured with PrintWindow, so the board is recognized even when its window is covered by others. Highlights follow the window and hide when it is covered. You can give part of the window title: `--external-window Arena` |
| `--multipv N` | how many best moves to highlight (1–5) |
| `--auto-turns` | Auto moves in the console: the opening is played move by move from a book, then every move is Stockfish's best move (virtual board, nothing is clicked on any site) |
| `--book masters\|lichess\|local\|off` | opening book for Auto: `masters` — master games from the internet (Lichess Opening Explorer, default), `lichess` — lichess players rated 2000+ (may need a token in `LICHESS_TOKEN`), `local` — built-in database, no internet, `off` — Stockfish from move one |
| `--book-mode random\|top` | `random` — move weighted by popularity (a new opening every game), `top` — always the most popular move |
| `--move-time SEC` | Stockfish time per move in `--auto-turns` (1 s by default) |
| `--review [PGN]` | open **Virtual Game Review** — review a game from a PGN file (without a file — from the starting position or `--fen`) |
| `--fen FEN` / `--pgn FILE` | start `--auto-turns` from a position / save the game to PGN |

Examples:

```
python main.py --auto-find --auto-find-time 3
python main.py --external-window
python main.py --external-window Arena --auto-find
python main.py --no-window --gdi
python main.py --auto-turns --move-time 0.5 --pgn game.pgn
python auto-turns/auto_turns.py --book local --book-mode top   # same as main.py --auto-turns
```

Without internet access (or if lichess rate-limits requests) the book falls back
to the built-in opening database automatically.

About `--gdi`: highlights are drawn with GDI (pens, brushes, Polygon, TextOut)
into a native Win32 window over the board, without Tk. The drawing is not erased
when the board's window repaints, the mouse passes through it, and it is excluded
from screen capture, so the arrows do not interfere with recognition. If such a
window cannot be created on an old Windows version, the program draws directly on
the screen. In that mode highlights may flicker, and without `--external-window`
only frames are drawn, no arrows.

## How to use

1. Open a board on the screen — the program finds it by itself
   (or use **«Выделить вручную»** (Select manually) and drag a frame around the board).
2. **Calibration**: once for each program / piece set, open a new game
   (starting position). The program remembers what the pieces look like
   (`calibration.npz`). Orientation (white at the bottom/top) is detected automatically.
3. Then just play/watch: every move is recognized, and the virtual game follows
   the rules (side to move, castling, en passant).

The best move is a bright green arrow "1", the next ones are lighter ("2", "3").
Above the board (and at the top of the program window) there is a line
`Running Live analysis...   Bestmove is Nf3   +0.25   (depth 22)`;
if the board touches the top of the screen, the line is shown below it.

Moves that were played are rated like in game reviews of chess programs:

| Mark | Meaning |
|---|---|
| 🟤 `≡` icon — book | a move from opening theory; the opening name is shown in the line above the board |
| 🔷 `!!` icon — brilliant | the best (or nearly best) move with a material sacrifice, when the position is not yet winning |
| 🟢 `★` icon — best | the move matches the engine's best move or is almost as good |
| 🟠 `?` arrow — mistake | the position got noticeably worse, but not decisively (winning chances dropped by 10–30 %) |
| 🔴 `??` arrow — blunder | loses material or the game, or allows mate (winning chances dropped by 30 % or more) |

Ordinary good moves are not marked. The last two moves are rated, so the verdict
on your move stays visible even if a bot replies instantly. Highlights are drawn
both in the program window and as a transparent layer right over the real board
(the mouse passes through it).

| Button | What it does |
|---|---|
| Найти доску (Find board) | search the whole screen for the board again |
| Выделить вручную (Select manually) | drag a frame around the board |
| Калибровка (Calibrate) | force calibration (board in the starting position) |
| Перевернуть (Flip) | if the orientation was detected wrongly |
| Сейчас ход белых / чёрных (White / Black to move) | if the program started following mid-game and got the side to move wrong |
| Лучших ходов (Best moves) | how many variations (MultiPV) to show |
| ▶ Auto (самоигра, self-play) | plays the current position out for both sides: while the position is in the book — book moves (the «Дебюты» (Openings) list: masters / lichess players from the internet, local database, no book), then Stockfish's best moves. Only on the virtual board in the program window, nothing is clicked on any site. Speed: быстро / средне / медленно (fast / medium / slow — 0.3 / 1 / 3 s per move) |

## Virtual Game Review

Game review on a virtual board: the **Virtual Game Review** button in the program
window (takes the Auto self-play game or the game from the live board) or
`python main.py --review game.pgn`.

| Control | What it does |
|---|---|
| ⏮ ◀ ▶ ⏭, keys ← → Home End, mouse wheel | step through the moves; click a move in the list to jump to it |
| ▶ at the end of the game | play Stockfish's best move |
| ★ Лучший ход (Best move, B) | play the best move from the current position; if the game had a different move, the continuation is replaced |
| ⏵ Авто (Auto, Space) | step through the game automatically and, at the end, play it out with best moves (speed: fast / medium / slow) |
| Открыть / Сохранить PGN (Open / Save PGN), Перевернуть (Flip, F), Новая партия (New game) | |

For every position: a green arrow for the best move, Stockfish's evaluation and
main line, a mark for the move played (`≡` `★` `!!` `?` `??`) and the opening
name. The whole game is analysed in the background by a separate Stockfish
(0.4 s per position), the current position first.

## How it works

- `chessvision/detector.py` — board detection: square contours + a grid of cells,
  8×8 checker pattern check, pixel-accurate fit to the grid lines.
- `chessvision/recognizer.py` — templates of the 32 pieces taken during calibration;
  each square is compared with the templates "transplanted" onto its background, which
  gives both the piece type and colour (works with shadows, cream/coloured sets, light
  and dark boards). The piece-vs-empty threshold adapts to the board texture.
- `chessvision/tracker.py` — reconstructs the moves played (1–2 plies between frames).
- `chessvision/engine.py` — infinite Stockfish analysis in the background.
- `chessvision/explorer.py` — opening book: Lichess Opening Explorer from the internet,
  local database as a fallback.
- `chessvision/review.py` — Virtual Game Review: game review, navigation, playing on with best moves.
- `chessvision/selfplay.py`, `chessvision/autoturns.py` — Auto moves: book, then Stockfish (window / console).
- `chessvision/overlay.py` — transparent window over the screen, excluded from capture.
- `chessvision/gdi_overlay.py` — drawing directly on the screen with GDI (`--gdi`).
- `chessvision/winutil.py` — WinAPI: window enumeration, window capture via PrintWindow.
- `chessvision/blacklist.py` — browser blacklist, **off by default** (`ENABLED = False`).
  When enabled, boards are not recognized in browser windows: by process name (Chrome,
  Edge, Firefox, Opera, Yandex, Brave, Vivaldi and others), by window class (Chromium /
  Firefox / IE, including renamed executables and Electron apps) and by an embedded
  browser engine (WebView2); checked when searching for the board and on every frame.

Self-test without a real program: `python -m tests.test_synthetic`

> Once again: use the program only for analysis and study, at your own risk —
> see the "Disclaimer" at the top.

## License

GPL-3.0 — see [LICENSE](LICENSE). The project uses [python-chess](https://github.com/niklasf/python-chess)
(GPL-3.0) and the [Stockfish](https://stockfishchess.org) engine (GPL-3.0); Stockfish is not
included in the repository and is downloaded from its official GitHub on first run.
The opening names database comes from [lichess-org/chess-openings](https://github.com/lichess-org/chess-openings)
(CC0-1.0).
