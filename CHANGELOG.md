# Changelog

**Language / Язык:** English below, [русский ниже](#ru).

## 1.6.0 — 2026-11-27

- English interface with a language switch: **Язык / Language** in the program window and in
  Virtual Game Review (switches instantly) or `--lang en|ru`; the choice is remembered in
  `settings.json`, by default the Windows display language is used. Console messages and
  `--help` are translated too.
- `python -m tests.test_i18n` checks that every interface string has an English translation.

## 1.5.0 — 2026-11-27

First public release.

- Finds a chessboard on the screen (all monitors) or in any window (`--external-window`),
  calibrates to any board theme and piece set, keeps a virtual copy of the game
  and highlights Stockfish 19 (NNUE) best moves with green arrows.
- Ratings of played moves: `≡` book, `!!` brilliant, `★` best, `?` mistake, `??` blunder;
  opening name from the lichess openings database (CC0).
- Auto self-play with an opening book: the opening is played move by move from
  Lichess Opening Explorer (masters or lichess 2000+), with a built-in database as an
  offline fallback, then Stockfish's best moves. Console mode `python main.py --auto-turns`
  and the `auto-turns/auto_turns.py` script.
- Virtual Game Review: step back/forward through a game, best move and evaluation for every
  position, marks for played moves, playing on with best moves, open/save PGN
  (`python main.py --review [PGN]`).
- Browser blacklist in `chessvision/blacklist.py`, off by default (`ENABLED = False`).
- README in English and Russian with a disclaimer: use at your own risk.

<a id="ru"></a>
## 1.6.0 — 2026-11-27 (RU)

- Английский интерфейс с выбором языка: переключатель **Язык / Language** в окне программы и в
  Virtual Game Review (меняется сразу) или `--lang ru|en`; выбор запоминается в `settings.json`,
  по умолчанию — язык Windows. Сообщения в консоли и `--help` тоже переведены.
- `python -m tests.test_i18n` проверяет, что у всех строк интерфейса есть английский перевод.

## 1.5.0 — 2026-11-27 (RU)

Первый публичный выпуск.

- Находит шахматную доску на экране (все мониторы) или в любом окне (`--external-window`),
  калибруется под любую доску и набор фигур, ведёт виртуальную копию партии и подсвечивает
  зелёными стрелками лучшие ходы Stockfish 19 (NNUE).
- Оценки сделанных ходов: `≡` теория, `!!` блестящий, `★` лучший, `?` ошибка, `??` зевок;
  название дебюта по базе lichess (CC0).
- Auto-самоигра с дебютной книгой: дебют по ходам из Lichess Opening Explorer (мастера или
  игроки lichess 2000+), без интернета — из встроенной базы, дальше лучшие ходы Stockfish.
  Консольный режим `python main.py --auto-turns` и скрипт `auto-turns/auto_turns.py`.
- Virtual Game Review: листать партию назад/вперёд, лучший ход и оценка на каждой позиции,
  отметки ходам, доигрывание лучшими ходами, открытие/сохранение PGN
  (`python main.py --review [PGN]`).
- Чёрный список браузеров в `chessvision/blacklist.py`, по умолчанию выключен (`ENABLED = False`).
- README на английском и русском, с отказом от ответственности: использование на свой риск.
