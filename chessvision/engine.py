"""Stockfish в фоновом потоке: бесконечный анализ текущей позиции, MultiPV."""
import logging
import threading
import time

import chess
import chess.engine

from . import judge as judging
from .openings import OpeningBook

# python-chess ругается на безобидные строки Stockfish вроде 'info string Using 8 threads'
logging.getLogger("chess.engine").setLevel(logging.ERROR)


def format_score(score: chess.engine.PovScore) -> str:
    s = score.white()
    if s.is_mate():
        m = s.mate()
        return f"#{m}" if m > 0 else f"#-{abs(m)}"
    return f"{s.score() / 100:+.2f}"


JUDGE_DEPTH = 12          # с какой глубины оценке позиции можно верить для вердикта ходу


def _after(board, move):
    b = board.copy()
    b.push(move)
    return b


class EngineWorker:
    def __init__(self, path: str, threads: int, hash_mb: int, multipv: int = 3):
        self.path = path
        self.options = {"Threads": threads, "Hash": hash_mb}
        self.multipv = multipv
        self.name = "Stockfish"
        self.error = None
        self.result = None              # {"fen", "lines": [...], "depth", "nps"}
        self._cond = threading.Condition()
        self._target = None
        self._gen = 0
        self._analysis = None
        self._stop = False
        self._evals = {}                # epd -> (cp белых, глубина, лучший ход) — для вердикта ходам
        self.book = None                # дебютная база (грузится в потоке движка)
        self._thread = threading.Thread(target=self._run, daemon=True, name="engine")

    def start(self):
        self._thread.start()

    def set_position(self, board):
        with self._cond:
            self._target = board.copy() if board is not None else None
            self._gen += 1
            self.result = None
            self._abort()
            self._cond.notify_all()

    def set_multipv(self, n: int):
        with self._cond:
            self.multipv = max(1, int(n))
            self._gen += 1
            self._abort()
            self._cond.notify_all()

    def shutdown(self):
        with self._cond:
            self._stop = True
            self._abort()
            self._cond.notify_all()

    # ------------------------------------------------------------
    def _abort(self):
        if self._analysis is not None:
            try:
                self._analysis.stop()
            except Exception:
                pass

    def _start_engine(self):
        # большой таймаут: первое выделение хэша при нехватке памяти может идти долго
        engine = chess.engine.SimpleEngine.popen_uci(self.path, timeout=120)
        opts = {k: v for k, v in self.options.items() if k in engine.options}
        if "Hash" in opts:
            opts["Hash"] = min(opts["Hash"], engine.options["Hash"].max)
        if "Threads" in opts:
            opts["Threads"] = min(opts["Threads"], engine.options["Threads"].max)
        engine.configure(opts)
        engine.ping()                      # дождаться, пока движок выделит память
        if self.book is None:
            try:
                self.book = OpeningBook()
            except Exception:
                self.book = False          # без базы — просто нет отметки «теория»
        self._engine = engine
        self.name = engine.id.get("name", "Stockfish")
        return engine

    def _run(self):
        """Внешний цикл: если движок упал или завис — перезапускаем и продолжаем анализ."""
        restarts = 0
        while not self._stop:
            engine = None
            try:
                engine = self._start_engine()
                self.error = None
                self._analyse_loop(engine)
                return                     # нормальное завершение (shutdown)
            except Exception as e:
                restarts += 1
                self.error = f"Движок перезапускается ({restarts}): {type(e).__name__} {e}".strip()
                with self._cond:
                    self._analysis = None
                    self._gen += 1         # заново проанализировать текущую позицию
                time.sleep(min(5, restarts))
            finally:
                if engine is not None:
                    try:
                        engine.quit()
                    except Exception:
                        try:
                            engine.close()
                        except Exception:
                            pass

    def _analyse_loop(self, engine):
        done = 0
        while True:
            with self._cond:
                while not self._stop and (self._gen == done or self._target is None):
                    done = self._gen
                    self._cond.wait()
                if self._stop:
                    return
                board, gen, mpv = self._target, self._gen, self.multipv
            done = gen
            judge = self._prepare_judge(engine, board)
            if gen != self._gen:
                continue
            # запуск анализа — вне блокировки, чтобы медленный движок не тормозил распознавание
            analysis = engine.analysis(board, multipv=mpv)
            with self._cond:
                self._analysis = analysis
                if gen != self._gen:       # позиция успела смениться
                    analysis.stop()
            try:
                for _info in analysis:
                    if gen != self._gen:
                        break
                    res = self._collect(board, analysis.multipv)
                    if res:
                        self._remember(board, res)
                        if judge:
                            res["judged"] = self._judge(judge, res)
                        if self.book:
                            res["opening"] = self.book.name(board)
                        with self._cond:
                            if gen == self._gen:
                                self.result = res
            finally:
                with self._cond:
                    self._analysis = None
                try:
                    analysis.stop()
                    analysis.wait()
                except chess.engine.EngineTerminatedError:
                    raise
                except Exception:
                    pass

    # ---------------------------------------------------------------- вердикт ходу
    def _remember(self, board, res):
        key = board.epd()
        old = self._evals.get(key)
        if old is None or res["depth"] >= old[1]:
            top = res["lines"][0]
            self._evals[key] = (top["cp"], res["depth"], top["move"])
        if len(self._evals) > 5000:
            self._evals.clear()

    def _eval(self, engine, board):
        """Оценка позиции глубиной не меньше JUDGE_DEPTH: из кэша или быстрым досчётом
        (если позиция простояла на экране слишком мало — соперник ответил мгновенно)."""
        key = board.epd()
        ev = self._evals.get(key)
        if ev is None or ev[1] < JUDGE_DEPTH:
            info = engine.analyse(board, chess.engine.Limit(depth=JUDGE_DEPTH, time=1.0))
            score, pv = info.get("score"), info.get("pv")
            if score is not None:
                ev = (score.white().score(mate_score=100000), info.get("depth", 0), pv[0] if pv else None)
                self._evals[key] = ev
        return ev

    def _prepare_judge(self, engine, board):
        """Два последних хода (обычно ваш и ответ соперника) и оценки позиций до них."""
        if not board.move_stack:
            return []
        parent = board.copy()
        last = parent.pop()
        ev_parent = self._eval(engine, parent)
        if ev_parent is None:
            return []
        judges = [(last, parent, ev_parent, None)]          # «после» — из живого анализа
        if parent.move_stack:
            grand = parent.copy()
            prev = grand.pop()
            ev_grand = self._evals.get(grand.epd())         # её обычно уже считали долго
            if ev_grand is not None and ev_grand[1] >= JUDGE_DEPTH:
                judges.insert(0, (prev, grand, ev_grand, ev_parent[0]))
        return judges

    def _judge(self, judges, res):
        """-> список {"move", "san", "white", "kind": book|brilliant|best|ok|mistake|blunder|None, ...}
        kind None — оценка новой позиции ещё ненадёжна (мало глубины)."""
        out = []
        book = self.book or None
        for move, parent, (before_cp, _, best), after_cp in judges:
            v = {"move": move, "san": parent.san(move), "white": parent.turn == chess.WHITE,
                 "kind": None, "loss": 0.0, "mate": False}
            out.append(v)
            if after_cp is None:
                if res["depth"] < JUDGE_DEPTH:
                    continue
                after_cp = res["lines"][0]["cp"]
            v.update(judging.classify(parent, move, before_cp, after_cp, best, book))
            if v["kind"] == "book":
                v["opening"] = book.name(_after(parent, move))
        return out

    @staticmethod
    def _collect(board, infos):
        lines = []
        seen = set()
        for info in infos:
            pv = info.get("pv")
            score = info.get("score")
            if not pv or score is None or pv[0] in seen:   # между итерациями MultiPV бывают дубли
                continue
            seen.add(pv[0])
            b = board.copy(stack=False)
            sans = []
            for mv in pv[:10]:
                if mv not in b.legal_moves:
                    break
                sans.append(b.san(mv))
                b.push(mv)
            lines.append({
                "move": pv[0],
                "score": format_score(score),
                "cp": score.white().score(mate_score=100000),
                "depth": info.get("depth", 0),
                "san": sans,
            })
        if not lines:
            return None
        first = infos[0]
        return {"fen": board.fen(), "lines": lines,
                "depth": first.get("depth", 0), "nps": first.get("nps", 0)}
