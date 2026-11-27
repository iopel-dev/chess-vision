"""Английский перевод интерфейса: русская строка -> английская.

Подстановки {поля} должны совпадать с оригиналом — это проверяет tests/test_i18n.py.
"""

EN = {
    # ---------------- главное окно ----------------
    "Доска не распознана": "Board not recognized",
    "белые": "White",
    "чёрные": "Black",
    ", допускает мат": ", allows mate",
    " — жертва {n} пешки": " — {n}-pawn sacrifice",
    " — жертва {n} пешек": " — {n}-pawn sacrifice",
    "Выделите доску мышью  (Esc — отмена)": "Drag a frame around the board  (Esc — cancel)",
    "Stockfish: запуск...": "Stockfish: starting...",
    "Найти доску": "Find board",
    "Выделить вручную": "Select manually",
    "Калибровка": "Calibrate",
    "Перевернуть": "Flip",
    "Сейчас ход белых": "White to move",
    "Сейчас ход чёрных": "Black to move",
    "Подсветка поверх экрана": "Highlight on screen",
    "Пауза": "Pause",
    "Лучших ходов:": "Best moves:",
    "Дебюты:": "Openings:",
    "Калибровка: откройте новую партию (начальная расстановка) — "
    "программа запомнит фигуры этой программы.":
        "Calibration: open a new game (starting position) — "
        "the program will remember this program's pieces.",
    "▶ Auto (самоигра)": "▶ Auto (self-play)",
    "■ Стоп": "■ Stop",
    "↩ К живой доске": "↩ Back to live board",
    "Самоигра: нет позиции для доигрывания (доска не распознана или партия окончена)":
        "Self-play: no position to play out (board not recognized or game over)",
    "самоигра Auto": "Auto self-play",
    "партия с доски": "game from the board",
    "новая партия": "new game",
    "идёт...": "running...",
    "дебют": "opening",
    "Самоигра: {n} полуходов, {sec:g} с на ход": "Self-play: {n} plies, {sec:g} s per move",
    "Книга: {book} · из книги {n} полуходов": "Book: {book} · {n} plies from the book",
    "Итог: {result}": "Result: {result}",
    "{name} · глубина {depth} · {knps} kN/s · {threads} потоков":
        "{name} · depth {depth} · {knps} kN/s · {threads} threads",
    "{name} · {threads} потоков, {hash} MB хэш": "{name} · {threads} threads, {hash} MB hash",
    "Ход белых | глубина {depth:>2} | {best}": "White to move | depth {depth:>2} | {best}",
    "Ход чёрных | глубина {depth:>2} | {best}": "Black to move | depth {depth:>2} | {best}",
    "Ожидание анализа...": "Waiting for analysis...",
    "Нет позиции для анализа": "No position to analyse",

    # ---------------- оценки ходов ----------------
    "блестящий ход": "brilliant move",
    "лучший ход": "best move",
    "теория": "book move",
    "ошибка": "mistake",
    "зевок": "blunder",

    # ---------------- скорость, книги, итоги партии ----------------
    "быстро": "fast",
    "средне": "medium",
    "медленно": "slow",
    "Lichess: мастера": "Lichess: masters",
    "Lichess: игроки 2000+": "Lichess: players 2000+",
    "локальная база": "local database",
    "без книги": "no book",
    "мат": "checkmate",
    "пат": "stalemate",
    "недостаточно материала": "insufficient material",
    "правило 75 ходов": "75-move rule",
    "пятикратное повторение": "fivefold repetition",
    "правило 50 ходов": "50-move rule",
    "троекратное повторение": "threefold repetition",
    "конец партии": "game over",
    "остановлено: слишком длинная партия": "stopped: game too long",
    "Самоигра остановлена: {e}": "Self-play stopped: {e}",

    # ---------------- Virtual Game Review ----------------
    "★ Лучший ход": "★ Best move",
    "Открыть PGN": "Open PGN",
    "Сохранить PGN": "Save PGN",
    "Новая партия": "New game",
    "Партия окончена.": "Game over.",
    "Stockfish считает лучший ход...": "Stockfish is calculating the best move...",
    "⏸ Пауза": "⏸ Pause",
    "⏵ Авто": "⏵ Auto",
    "Открыть партию": "Open game",
    "Все файлы": "All files",
    "Не удалось открыть файл:\n{e}": "Could not open the file:\n{e}",
    "В файле нет партии.": "The file contains no game.",
    "Сохранить партию": "Save game",
    "Сохранено: {path}": "Saved: {path}",
    "ход {ply}/{n}": "ply {ply}/{n}",
    "Партия окончена: {reason}": "Game over: {reason}",
    "Лучший ход белых: {san}": "Best move for White: {san}",
    "Лучший ход чёрных: {san}": "Best move for Black: {san}",
    "Вариант: {pv}   (глубина {depth})": "Line: {pv}   (depth {depth})",
    "Stockfish считает...": "Stockfish is thinking...",
    "{san}: нормальный ход": "{san}: good move",
    "Анализ партии: {done}/{total} позиций": "Analysing the game: {done}/{total} positions",
    "Партия разобрана.  ← → Home End — листать, пробел — авто, B — лучший ход":
        "Game analysed.  ← → Home End — step, Space — auto, B — best move",
    "Ходов нет. ▶ или «★ Лучший ход» — сыграть лучший ход, «⏵ Авто» — доиграть партию.":
        "No moves. ▶ or \"★ Best move\" — play the best move, \"⏵ Auto\" — play the game out.",

    # ---------------- распознавание доски ----------------
    "Запуск...": "Starting...",
    "Ошибка: {e}": "Error: {e}",
    "Ищу доску...": "Searching for the board...",
    "Ищу доску во всех окнах...": "Searching for the board in all windows...",
    "Доска не найдена. Откройте доску или выделите её вручную":
        "Board not found. Open a board or select it manually",
    " (повтор каждые {sec:g} с)": " (retrying every {sec:g} s)",
    "Доска найдена на экране: {s}x{s} px": "Board found on screen: {s}x{s} px",
    "Доска найдена в окне «{title}»: {s}x{s} px": "Board found in window \"{title}\": {s}x{s} px",
    "Окно с доской свёрнуто или закрыто": "The board's window is minimized or closed",
    "Нужна калибровка: поставьте начальную позицию (новая партия) — откалибруется автоматически":
        "Calibration needed: set up the starting position (new game) — it will calibrate automatically",
    "Не распознаётся позиция ({n})": "Position not recognized ({n})",
    "Позиция невозможна по правилам (проверьте калибровку / чей ход)":
        "Illegal position (check calibration / side to move)",
    "Партия окончена: {result}": "Game over: {result}",
    "Слежу за доской. Ход белых.": "Following the board. White to move.",
    "Слежу за доской. Ход чёрных.": "Following the board. Black to move.",
    "Калибровка готова (белые снизу)": "Calibration done (White at the bottom)",
    "Калибровка готова (чёрные снизу)": "Calibration done (Black at the bottom)",
    "Область задана вручную в окне «{title}»": "Area selected manually in window \"{title}\"",
    "Область задана вручную: {s}x{s} px": "Area selected manually: {s}x{s} px",
    "Доска не в начальной позиции (найдено фигур: {n}, на своих местах: {ok}/32)":
        "The board is not in the starting position (pieces found: {n}, in place: {ok}/32)",
    "Не удаётся отличить белые фигуры от чёрных": "Cannot tell white pieces from black ones",
    "Калибровка не прошла самопроверку — попробуйте ещё раз": "Calibration failed its self-check — try again",
    "Калибровка от старой версии программы — нужна новая": "Calibration is from an old version — a new one is needed",
    "Доска в окне браузера: Chess Vision не работает с браузерами и сайтами — "
    "только шахматные программы на компьютере, PGN и Virtual Game Review.":
        "Board in a browser window: Chess Vision does not work with browsers and websites — "
        "only desktop chess programs, PGN and Virtual Game Review.",
    "Распознавание доски на экране поддерживается только в Windows.":
        "On-screen board recognition is supported on Windows only.",

    # ---------------- движок и книга ----------------
    "Движок перезапускается ({n}): {err}": "Engine restarting ({n}): {err}",
    "lichess ограничил запросы (429)": "lichess rate-limited requests (429)",
    "нужен токен LICHESS_TOKEN": "LICHESS_TOKEN token required",
    "нет связи с lichess ({reason})": "no connection to lichess ({reason})",

    # ---------------- Auto-ходы в консоли ----------------
    "Партия в этой позиции уже окончена.": "The game is already over in this position.",
    "Auto-ходы: книга — {book}, затем Stockfish ({sec:g} с на ход). Ctrl+C — стоп.":
        "Auto moves: book — {book}, then Stockfish ({sec:g} s per move). Ctrl+C — stop.",
    "Остановлено.": "Stopped.",
    "Внимание: {error} — дебют доигран по локальной базе.":
        "Warning: {error} — the opening was played from the local database.",
    "Итог: {result}  ·  из книги {book} полуходов, всего {total}":
        "Result: {result}  ·  {book} plies from the book, {total} in total",
    "не доиграно": "unfinished",
    "PGN сохранён: {path}": "PGN saved: {path}",

    # ---------------- командная строка ----------------
    "не число: {v}": "not a number: {v}",
    "время должно быть больше 0": "time must be greater than 0",
    "Распознаёт шахматную доску на экране и подсвечивает зелёным лучшие ходы Stockfish.":
        "Recognizes a chessboard on the screen and highlights Stockfish's best moves in green.",
    "периодически заново искать доску (окно сдвинули, сменили вкладку и т.п.)":
        "periodically search for the board again (window moved, tab switched, etc.)",
    "СЕК": "SEC",
    "ЗАГОЛОВОК": "TITLE",
    "ФАЙЛ": "FILE",
    "интервал автопоиска в секундах (по умолчанию 5); включает --auto-find":
        "auto-search interval in seconds (default 5); implies --auto-find",
    "не показывать окно программы: только подсветка поверх доски и ходы в консоли":
        "no program window: only highlights over the board and moves in the console",
    "рисовать подсветку прямо на экране через GDI, без окна-оверлея":
        "draw highlights directly on the screen with GDI, without an overlay window",
    "искать доску в любом окне (снимок окна через PrintWindow, работает и когда "
    "окно перекрыто); можно указать часть заголовка окна":
        "search for the board in any window (captured via PrintWindow, works even when "
        "the window is covered); you can give part of the window title",
    "сколько лучших ходов подсвечивать (1-5, по умолчанию 3)": "how many best moves to highlight (1-5, default 3)",
    "язык интерфейса: ru или en (по умолчанию — сохранённый выбор или язык системы)":
        "interface language: ru or en (default: saved choice or the system language)",
    "Auto-ходы (виртуальная доска, на сайте ничего не нажимается)":
        "Auto moves (virtual board, nothing is clicked on any site)",
    "сыграть партию в консоли: дебют по ходам из книги, дальше лучшие ходы Stockfish":
        "play a game in the console: the opening move by move from a book, then Stockfish's best moves",
    "дебютная книга: masters/lichess — Lichess Opening Explorer из интернета, "
    "local — встроенная база, off — сразу Stockfish (по умолчанию masters); "
    "выбирается и для кнопки Auto в окне":
        "opening book: masters/lichess — Lichess Opening Explorer from the internet, "
        "local — built-in database, off — Stockfish from move one (default masters); "
        "also used by the Auto button in the window",
    "random — ход по популярности с весами (разные дебюты), top — всегда самый частый":
        "random — move weighted by popularity (varied openings), top — always the most popular",
    "секунд на ход Stockfish в --auto-turns (по умолчанию 1)": "seconds per Stockfish move in --auto-turns (default 1)",
    "начать --auto-turns с этой позиции": "start --auto-turns from this position",
    "сохранить партию --auto-turns в PGN": "save the --auto-turns game to PGN",
    "открыть Virtual Game Review: разбор партии из PGN (или с начальной позиции) — "
    "стрелки назад/вперёд, лучший ход на каждой позиции, доигрывание лучшими ходами":
        "open Virtual Game Review: review a game from PGN (or from the starting position) — "
        "back/forward arrows, best move in every position, playing on with best moves",
    "неверный FEN: {e}": "invalid FEN: {e}",
    "--gdi и --external-window работают только в Windows": "--gdi and --external-window work on Windows only",
    "Stockfish не найден — скачиваю официальную сборку...": "Stockfish not found — downloading the official build...",
    "автопоиск каждые {sec:g} с": "auto-search every {sec:g} s",
    "поиск во всех окнах": "search in all windows",
    "подсветка через GDI": "GDI highlighting",
    "без окна (Ctrl+C — выход)": "no window (Ctrl+C — exit)",
    "Режим: ": "Mode: ",

    # ---------------- загрузка Stockfish ----------------
    "GitHub API недоступен ({e}), пробую стандартные имена": "GitHub API unavailable ({e}), trying standard names",
    "Скачиваю {url} ...": "Downloading {url} ...",
    "  не удалось: {e}": "  failed: {e}",
    "  в архиве нет .exe": "  no .exe in the archive",
    "Готово: {target} ({name})": "Done: {target} ({name})",
    "  эта сборка не запускается на вашем CPU, пробую следующую": "  this build does not run on your CPU, trying the next one",
    "Не удалось скачать рабочий Stockfish. Скачайте вручную: "
    "https://stockfishchess.org/download/ и положите exe в папку engine/":
        "Could not download a working Stockfish. Download it manually from "
        "https://stockfishchess.org/download/ and put the exe into the engine/ folder",
}
