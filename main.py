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
  python main.py --lang en                        # английский интерфейс (ru — русский)
"""
import argparse
import sys

from chessvision import __version__, config, i18n, winutil
from chessvision.i18n import tr


def positive_float(v):
    try:
        f = float(v.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(tr("не число: {v}", v=v))
    if f <= 0:
        raise argparse.ArgumentTypeError(tr("время должно быть больше 0"))
    return f


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="main.py",
        description=tr("Распознаёт шахматную доску на экране и подсвечивает зелёным лучшие ходы Stockfish."))
    p.add_argument("--version", action="version", version=f"Chess Vision {__version__}")
    p.add_argument("--auto-find", action="store_true",
                   help=tr("периодически заново искать доску (окно сдвинули, сменили вкладку и т.п.)"))
    p.add_argument("--auto-find-time", type=positive_float, metavar=tr("СЕК"), default=None,
                   help=tr("интервал автопоиска в секундах (по умолчанию 5); включает --auto-find"))
    p.add_argument("--no-window", action="store_true",
                   help=tr("не показывать окно программы: только подсветка поверх доски и ходы в консоли"))
    p.add_argument("--gdi", action="store_true",
                   help=tr("рисовать подсветку прямо на экране через GDI, без окна-оверлея"))
    p.add_argument("--external-window", nargs="?", const="", default=None, metavar=tr("ЗАГОЛОВОК"),
                   help=tr("искать доску в любом окне (снимок окна через PrintWindow, работает и когда "
                           "окно перекрыто); можно указать часть заголовка окна"))
    p.add_argument("--multipv", type=int, choices=range(1, 6), metavar="N", default=None,
                   help=tr("сколько лучших ходов подсвечивать (1-5, по умолчанию 3)"))
    p.add_argument("--lang", choices=list(i18n.LANGS), default=None,
                   help=tr("язык интерфейса: ru или en (по умолчанию — сохранённый выбор или язык системы)"))
    g = p.add_argument_group(tr("Auto-ходы (виртуальная доска, на сайте ничего не нажимается)"))
    g.add_argument("--auto-turns", action="store_true",
                   help=tr("сыграть партию в консоли: дебют по ходам из книги, дальше лучшие ходы Stockfish"))
    g.add_argument("--book", choices=["masters", "lichess", "local", "off"], default="masters",
                   help=tr("дебютная книга: masters/lichess — Lichess Opening Explorer из интернета, "
                           "local — встроенная база, off — сразу Stockfish (по умолчанию masters); "
                           "выбирается и для кнопки Auto в окне"))
    g.add_argument("--book-mode", choices=["random", "top"], default="random",
                   help=tr("random — ход по популярности с весами (разные дебюты), top — всегда самый частый"))
    g.add_argument("--move-time", type=positive_float, metavar=tr("СЕК"), default=1.0,
                   help=tr("секунд на ход Stockfish в --auto-turns (по умолчанию 1)"))
    g.add_argument("--fen", default=None, help=tr("начать --auto-turns с этой позиции"))
    g.add_argument("--pgn", default=None, metavar=tr("ФАЙЛ"), help=tr("сохранить партию --auto-turns в PGN"))
    p.add_argument("--review", nargs="?", const="", default=None, metavar="PGN",
                   help=tr("открыть Virtual Game Review: разбор партии из PGN (или с начальной позиции) — "
                           "стрелки назад/вперёд, лучший ход на каждой позиции, доигрывание лучшими ходами"))
    a = p.parse_args(argv)
    if a.fen:
        import chess
        try:
            chess.Board(a.fen)
        except ValueError as e:
            p.error(tr("неверный FEN: {e}", e=e))
    if a.auto_find_time is not None:
        a.auto_find = True
    if a.auto_find_time is None:
        a.auto_find_time = 5.0
    if (a.gdi or a.external_window is not None) and not winutil.IS_WIN:
        p.error(tr("--gdi и --external-window работают только в Windows"))
    return a


def main(argv=None):
    i18n.init(i18n.lang_from_argv(sys.argv[1:] if argv is None else argv))   # до argparse: справка на нужном языке
    args = parse_args(argv)
    if args.lang:
        i18n.set_lang(args.lang, save=True)
    winutil.set_dpi_aware()        # до создания любых окон
    path = config.find_stockfish()
    if not path:
        print(tr("Stockfish не найден — скачиваю официальную сборку..."))
        import get_stockfish
        path = str(get_stockfish.download())

    if args.review is not None:
        from chessvision.review import ReviewWindow
        import chess
        start = chess.Board(args.fen) if args.fen else None
        win = ReviewWindow(path, start, title=tr("новая партия") if not args.review else "")
        if args.review:
            win.load_pgn(args.review)
        win.run()
        return 0

    if args.auto_turns:
        from chessvision import autoturns
        return autoturns.run(path, args.fen, args.book, args.book_mode, args.move_time, args.pgn)

    mode = []
    if args.auto_find:
        mode.append(tr("автопоиск каждые {sec:g} с", sec=args.auto_find_time))
    if args.external_window is not None:
        mode.append(tr("поиск во всех окнах") + (f" «{args.external_window}»" if args.external_window else ""))
    if args.gdi:
        mode.append(tr("подсветка через GDI"))
    if args.no_window:
        mode.append(tr("без окна (Ctrl+C — выход)"))
    if mode:
        print(tr("Режим: ") + ", ".join(mode), flush=True)

    from chessvision.gui import App
    App(path, args).run()


if __name__ == "__main__":
    sys.exit(main())
