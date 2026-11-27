import mss
import numpy as np

_MSS = getattr(mss, "MSS", None) or mss.mss


class ScreenGrabber:
    """Захват экрана. Создавать в том потоке, где он используется."""

    def __init__(self):
        self.sct = _MSS()

    def virtual_screen(self):
        m = self.sct.monitors[0]          # все мониторы вместе
        return m["left"], m["top"], m["width"], m["height"]

    def grab(self, region=None) -> np.ndarray:
        """region = (left, top, width, height) в экранных координатах. Возвращает BGR."""
        if region is None:
            left, top, w, h = self.virtual_screen()
        else:
            left, top, w, h = region
        shot = self.sct.grab({"left": int(left), "top": int(top), "width": int(w), "height": int(h)})
        return np.ascontiguousarray(np.asarray(shot)[:, :, :3])
