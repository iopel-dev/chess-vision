"""Язык интерфейса: русский (исходный) или английский.

В коде строки пишутся по-русски и оборачиваются в tr(): tr("Пауза") -> "Pause"
при английском языке. Подстановки — через именованные поля:
tr("Ход {side}", side=...). Нет перевода — показывается русский текст
(тест tests/test_i18n.py следит, чтобы переводы были у всех строк).

Порядок выбора языка: флаг --lang, сохранённый выбор (settings.json рядом
с программой, переключатель «Язык / Language» в окне), язык Windows.
"""
import ctypes
import json
import locale
import sys

from .config import BASE_DIR
from .lang_en import EN

LANGS = {"ru": "Русский", "en": "English"}
SETTINGS = BASE_DIR / "settings.json"
_lang = "ru"


def lang() -> str:
    return _lang


def tr(text: str, **kw) -> str:
    s = EN.get(text, text) if _lang == "en" else text
    return s.format(**kw) if kw else s


def set_lang(code: str, save: bool = False):
    global _lang
    if code not in LANGS:
        raise ValueError(f"unknown language: {code}")
    _lang = code
    if save:
        data = _load()
        data["lang"] = code
        try:
            SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass


def system_lang() -> str:
    """ru — если язык системы русский (или белорусский, казахский), иначе en."""
    try:
        if sys.platform == "win32":
            primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            return "ru" if primary in (0x19, 0x23, 0x3F) else "en"
        name = (locale.getlocale()[0] or "").lower()
        return "ru" if name.startswith(("ru", "be", "kk")) else "en"
    except Exception:
        return "en"


def _load() -> dict:
    try:
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def init(cli=None) -> str:
    """Выбрать язык при запуске: флаг > сохранённый выбор > язык системы."""
    saved = _load().get("lang")
    code = cli or (saved if saved in LANGS else None) or system_lang()
    set_lang(code)
    return code


def lang_from_argv(argv) -> str:
    """--lang en / --lang=en из командной строки (до argparse — чтобы и справка была на нужном языке)."""
    argv = list(argv)
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv) and argv[i + 1] in LANGS:
            return argv[i + 1]
        if a.startswith("--lang=") and a.split("=", 1)[1] in LANGS:
            return a.split("=", 1)[1]
    return None
