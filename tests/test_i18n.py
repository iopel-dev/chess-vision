"""Проверка переводов: у каждой строки интерфейса (tr("...")) есть английский вариант,
и подстановки {поля} в переводе те же, что в оригинале.

Запуск:  python -m tests.test_i18n
"""
import ast
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from chessvision import blacklist, config, explorer, selfplay   # noqa: E402
from chessvision.lang_en import EN                              # noqa: E402

FILES = [ROOT / "main.py", ROOT / "get_stockfish.py", *sorted((ROOT / "chessvision").glob("*.py"))]
# строки, которые переводятся через словари (tr(BOOKS[k]) и т.п.)
INDIRECT = [*config.MARK_NAMES.values(), *explorer.BOOKS.values(), *selfplay.REASONS.values(),
            *selfplay.SPEED_NAMES.values(), "конец партии", blacklist.MESSAGE, blacklist.UNSUPPORTED]


def keys():
    found = {}
    for f in FILES:
        if f.name == "lang_en.py":
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "tr":
                arg = node.args[0] if node.args else None
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found[arg.value] = f"{f.name}:{node.lineno}"
                elif isinstance(arg, ast.IfExp):        # tr("a" if x else "b")
                    for v in (arg.body, arg.orelse):
                        if isinstance(v, ast.Constant):
                            found[v.value] = f"{f.name}:{node.lineno}"
    for v in INDIRECT:
        found.setdefault(v, "словарь")
    return found


def fields(s):
    return sorted(f for _, f, _, _ in string.Formatter().parse(s) if f)


def main():
    ok = True
    used = keys()
    for k, where in sorted(used.items(), key=lambda kv: kv[1]):
        if k not in EN:
            print(f"нет перевода ({where}): {k!r}")
            ok = False
        elif fields(k) != fields(EN[k]):
            print(f"разные поля ({where}): {k!r} -> {EN[k]!r}")
            ok = False
    unused = set(EN) - set(used)
    for k in sorted(unused):
        print(f"лишний перевод: {k!r}")
    print(f"строк: {len(used)}, переводов: {len(EN)}")
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
