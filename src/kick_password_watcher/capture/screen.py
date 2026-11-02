"""Fuente alternativa: captura de un monitor. Sólo sirve si el stream está visible
en pantalla; la fuente recomendada es StreamSource (no necesita navegador)."""

from __future__ import annotations

import time
from collections.abc import Iterator

import mss
import numpy as np

from kick_password_watcher.capture.stream import Frame


class ScreenSource:
    def __init__(self, monitor: int = 1, sample_interval: float = 1.0) -> None:
        self.monitor = monitor
        self.sample_interval = sample_interval

    def frames(self) -> Iterator[Frame]:
        start = time.monotonic()
        with mss.mss() as sct:
            area = sct.monitors[self.monitor]
            while True:
                shot = np.asarray(sct.grab(area))[:, :, :3]  # BGRA -> BGR
                yield Frame(np.ascontiguousarray(shot), time.monotonic() - start)
                time.sleep(self.sample_interval)
