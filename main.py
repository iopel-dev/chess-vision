"""Chess Vision: находит шахматную доску на экране, строит её виртуальную копию
и подсвечивает зелёным лучшие ходы Stockfish (NNUE, максимальная сила).
Используйте на свой риск — см. README.

Примеры:
  python main.py
  python main.py --auto-find --auto-find-time 3
  python main.py --external-window                # искать доску в любом окне
  python main.py --external-window Arena          # только в окнах с "Arena" в заголовке
  python main.py --no-window --gdi                # без окна, подсветка через GDI, ходы в консоли
  python main.py --auto-turns                     # Auto-ходы: дебют из интернета, потом Stockfish
  python main.py --auto-turns --book local --move-time 0.3 --pgn game.pgn
  python main.py --review                         # Virtual Game Review: разбор партии, стрелки назад/вперёд
  python main.py --review game.pgn
"""
import argparse
import sys

from chessvision import __version__, config, winutil


def positive_float(v):
    try:
        f = float(v.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"не число: {v}")
    if f <= 0:
        raise argparse.ArgumentTypeError("время должно быть больше 0")
    return f


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="main.py",
        description="Распознаёт шахматную доску на экране и подсвечивает зелёным лучшие ходы Stockfish.")
    p.add_argument("--version", action="version", version=f"Chess Vision {__version__}")
    p.add_argument("--auto-find", action="store_true",
                   help="периодически заново искать доску (окно сдвинули, сменили вкладку и т.п.)")
    p.add_argument("--auto-find-time", type=positive_float, metavar="СЕК", default=None,
                   help="интервал автопоиска в секундах (по умолчанию 5); включает --auto-find")
    p.add_argument("--no-window", action="store_true",
                   help="не показывать окно программы: только подсветка поверх доски и ходы в консоли")
    p.add_argument("--gdi", action="store_true",
                   help="рисовать подсветку прямо на экране через GDI, без окна-оверлея")
    p.add_argument("--external-window", nargs="?", const="", default=None, metavar="ЗАГОЛОВОК",
                   help="искать доску в любом окне (снимок окна через PrintWindow, работает и когда "
                        "окно перекрыто); можно указать часть заголовка окна")
    p.add_argument("--multipv", type=int, choices=range(1, 6), metavar="N", default=None,
                   help="сколько лучших ходов подсвечивать (1-5, по умолчанию 3)")
    g = p.add_argument_group("Auto-ходы (виртуальная доска, на сайте ничего не нажимается)")
    g.add_argument("--auto-turns", action="store_true",
                   help="сыграть партию в консоли: дебют по ходам из книги, дальше лучшие ходы Stockfish")
    g.add_argument("--book", choices=["masters", "lichess", "local", "off"], default="masters",
                   help="дебютная книга: masters/lichess — Lichess Opening Explorer из интернета, "
                        "local — встроенная база, off — сразу Stockfish (по умолчанию masters); "
                        "выбирается и для кнопки Auto в окне")
    g.add_argument("--book-mode", choices=["random", "top"], default="random",
                   help="random — ход по популярности с весами (разные дебюты), top — всегда самый частый")
    g.add_argument("--move-time", type=positive_float, metavar="СЕК", default=1.0,
                   help="секунд на ход Stockfish в --auto-turns (по умолчанию 1)")
    g.add_argument("--fen", default=None, help="начать --auto-turns с этой позиции")
    g.add_argument("--pgn", default=None, metavar="ФАЙЛ", help="сохранить партию --auto-turns в PGN")
    p.add_argument("--review", nargs="?", const="", default=None, metavar="PGN",
                   help="открыть Virtual Game Review: разбор партии из PGN (или с начальной позиции) — "
                        "стрелки назад/вперёд, лучший ход на каждой позиции, доигрывание лучшими ходами")
    a = p.parse_args(argv)
    if a.fen:
        import chess
        try:
            chess.Board(a.fen)
        except ValueError as e:
            p.error(f"неверный FEN: {e}")
    if a.auto_find_time is not None:
        a.auto_find = True
    if a.auto_find_time is None:
        a.auto_find_time = 5.0
    if (a.gdi or a.external_window is not None) and not winutil.IS_WIN:
        p.error("--gdi и --external-window работают только в Windows")
    return a


def main(argv=None):
    args = parse_args(argv)
    winutil.set_dpi_aware()        # до создания любых окон
    path = config.find_stockfish()
    if not path:
        print("Stockfish не найден — скачиваю официальную сборку...")
        import get_stockfish
        path = str(get_stockfish.download())

    if args.review is not None:
        from chessvision.review import ReviewWindow
        import chess
        start = chess.Board(args.fen) if args.fen else None
        win = ReviewWindow(path, start, title="новая партия" if not args.review else "")
        if args.review:
            win.load_pgn(args.review)
        win.run()
        return 0

    if args.auto_turns:
        from chessvision import autoturns
        return autoturns.run(path, args.fen, args.book, args.book_mode, args.move_time, args.pgn)

    mode = []
    if args.auto_find:
        mode.append(f"автопоиск каждые {args.auto_find_time:g} с")
    if args.external_window is not None:
        mode.append("поиск во всех окнах" + (f" «{args.external_window}»" if args.external_window else ""))
    if args.gdi:
        mode.append("подсветка через GDI")
    if args.no_window:
        mode.append("без окна (Ctrl+C — выход)")
    if mode:
        print("Режим: " + ", ".join(mode), flush=True)

    from chessvision.gui import App
    App(path, args).run()


if __name__ == "__main__":
    sys.exit(main())
