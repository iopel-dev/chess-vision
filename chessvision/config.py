import ctypes
import os
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENGINE_DIR = BASE_DIR / "engine"
CALIB_FILE = BASE_DIR / "calibration.npz"

SCAN_INTERVAL = 0.25        # секунд между снимками доски
REDETECT_AFTER_FAILS = 12   # столько неудачных кадров подряд -> искать доску заново
DEFAULT_MULTIPV = 3         # сколько лучших ходов подсвечивать

# Оттенки зелёного: 1-й (лучший) ход, 2-й, 3-й ...
GREENS = ["#00e639", "#5fd35f", "#a8e6a1", "#c8f0c4", "#dff7dc"]

# Вердикт сделанному ходу: оранжевая стрелка — ошибка, красная — зевок
MARK_COLORS = {"brilliant": "#1baca6", "best": "#98bc4b", "book": "#a88865",
               "mistake": "#ff9800", "blunder": "#ff2a2a"}
MARK_SIGNS = {"brilliant": "!!", "best": "\u2605", "book": "\u2261", "mistake": "?", "blunder": "??"}
MARK_NAMES = {"brilliant": "блестящий ход", "best": "лучший ход", "book": "теория",
              "mistake": "ошибка", "blunder": "зевок"}
MARK_ARROW = {"mistake", "blunder"}     # плохие ходы — стрелкой, хорошие — значком на поле


BANNER_BG = "#1b1a18"
BANNER_FG = "#e8e6e3"
BANNER_DIM = "#a9a6a2"


def banner_segments(board, res):
    """Строка над доской: [(текст, цвет), ...] или None."""
    if board is None:
        return None
    segs = [("Running Live analysis...", BANNER_FG)]
    if res and res["lines"] and res["lines"][0]["san"]:
        top = res["lines"][0]
        segs += [("   Bestmove is ", BANNER_FG), (top["san"][0], GREENS[0]),
                 (f"   {top['score']}   (depth {res['depth']})", BANNER_DIM)]
        if res.get("opening"):
            segs.append((f"   \u2261 {res['opening']}", MARK_COLORS["book"]))
    return tuple(segs)


def banner_height(s) -> int:
    return max(22, int(s * 0.055))


def banner_layout(region, with_banner, text_width=0):
    """Окно оверлея с местом под строку. -> (окно x, y, w, h, смещение доски по y, y строки, высота строки)
    Строка — над доской; если сверху нет места (доска у края экрана) — под доской.
    Если текст длиннее доски, окно (и плашка) шире доски вправо."""
    x, y, s, _ = map(int, region)
    if not with_banner:
        return x, y, s, s, 0, None, 0
    h = banner_height(s)
    w = max(s, int(text_width) + 20)
    if y - h >= 0:
        return x, y - h, w, s + h, h, 0, h
    return x, y, w, s + h, 0, s, h


def verdict_marks(res):
    """Стрелки-вердикты из результата движка: [(ход, цвет, знак), ...]."""
    if not res:
        return []
    return [(j["move"], MARK_COLORS[j["kind"]], MARK_SIGNS[j["kind"]], j["kind"] in MARK_ARROW)
            for j in res.get("judged", []) if j["kind"] in MARK_COLORS]


def find_stockfish():
    env = os.environ.get("STOCKFISH_PATH")
    if env and Path(env).is_file():
        return env
    if ENGINE_DIR.is_dir():
        exes = sorted(ENGINE_DIR.glob("stockfish*.exe" if sys.platform == "win32" else "stockfish*"))
        exes = [p for p in exes if p.is_file()]
        if exes:
            return str(exes[0])
    return shutil.which("stockfish")


def total_ram_mb() -> int:
    return _ram_mb()[0]


def _ram_mb():
    """(всего, свободно) МБ."""
    if sys.platform == "win32":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(st)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(st.ullTotalPhys // 2**20), int(st.ullAvailPhys // 2**20)
    try:
        total = int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // 2**20)
        return total, total // 2
    except Exception:
        return 4096, 2048


def engine_threads() -> int:
    # все потоки, кроме одного: он остаётся захвату экрана, иначе при мгновенных ответах
    # соперника снимки запаздывают и между ними пропадают ходы
    return max(1, (os.cpu_count() or 2) - 1)


def engine_hash_mb() -> int:
    """Хэш Stockfish: не больше 1/3 СВОБОДНОЙ памяти и 1/8 всей (иначе Windows уходит
    в подкачку и движок «зависает» при старте), в пределах 128..2048 МБ."""
    total, avail = _ram_mb()
    return int(max(128, min(2048, total // 8, avail // 3)))
