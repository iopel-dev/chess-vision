"""Скачивает официальный Stockfish (Windows x64) в папку ./engine.

Пробует сборки от самой быстрой к самой совместимой и оставляет первую,
которая реально запускается на этом процессоре.
"""
import io
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

try:                                    # язык сообщений — как у программы
    from chessvision.i18n import tr
except Exception:                       # запуск отдельно, без пакета рядом
    def tr(text, **kw):
        return text.format(**kw) if kw else text

ENGINE_DIR = Path(__file__).resolve().parent / "engine"
API_URL = "https://api.github.com/repos/official-stockfish/Stockfish/releases/latest"
BASE_URL = "https://github.com/official-stockfish/Stockfish/releases/latest/download/"
# Порядок предпочтения: новые "universal" сборки сами выбирают лучшие инструкции CPU.
PREFERRED = ["universal", "avx2", "bmi2", "sse41-popcnt", ""]


def _variants() -> list:
    """Имена Windows x64 архивов из последнего релиза (с запасным списком)."""
    import json
    names = []
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "stockfish-downloader"})
        rel = json.loads(urllib.request.urlopen(req, timeout=30).read())
        names = [a["name"] for a in rel.get("assets", [])
                 if a["name"].startswith("stockfish-windows-x86-64") and a["name"].endswith(".zip")]
    except Exception as e:
        print(tr("GitHub API недоступен ({e}), пробую стандартные имена", e=e))
    if not names:
        names = ["stockfish-windows-x86-64-universal.zip", "stockfish-windows-x86-64-avx2.zip",
                 "stockfish-windows-x86-64.zip"]

    def rank(n):
        for i, key in enumerate(PREFERRED):
            if key and key in n:
                return i
        return len(PREFERRED)
    return sorted(names, key=rank)


def _works(exe: Path) -> bool:
    try:
        out = subprocess.run([str(exe)], input="uci\nquit\n", capture_output=True,
                             text=True, timeout=20).stdout
        return "uciok" in out
    except Exception:
        return False


def download() -> Path:
    ENGINE_DIR.mkdir(exist_ok=True)
    target = ENGINE_DIR / "stockfish.exe"
    for name in _variants():
        url = BASE_URL + name
        print(tr("Скачиваю {url} ...", url=url))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "stockfish-downloader"})
            data = urllib.request.urlopen(req, timeout=120).read()
        except Exception as e:
            print(tr("  не удалось: {e}", e=e))
            continue
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            exes = [n for n in zf.namelist() if n.lower().endswith(".exe")]
            if not exes:
                print(tr("  в архиве нет .exe"))
                continue
            with zf.open(exes[0]) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        if _works(target):
            print(tr("Готово: {target} ({name})", target=target, name=name))
            return target
        print(tr("  эта сборка не запускается на вашем CPU, пробую следующую"))
    raise SystemExit(tr("Не удалось скачать рабочий Stockfish. Скачайте вручную: "
                        "https://stockfishchess.org/download/ и положите exe в папку engine/"))


if __name__ == "__main__":
    try:
        from chessvision import i18n
        i18n.init(i18n.lang_from_argv(sys.argv[1:]))
    except Exception:
        pass
    download()
    sys.exit(0)
