"""Filtra lecturas: exige N lecturas iguales seguidas y evita repetir la misma palabra."""

from __future__ import annotations

import time

from kick_password_watcher.config import ConfirmConfig


class WordConfirmer:
    def __init__(self, config: ConfirmConfig, clock=time.monotonic,
                 sent: dict[str, float] | None = None) -> None:
        self.config = config
        self.clock = clock
        self._candidate: str | None = None
        self._count = 0
        # Compartido entre canales: la misma palabra vista en dos canales se envía una vez.
        self._sent: dict[str, float] = {} if sent is None else sent

    def feed(self, word: str | None, frame_gap: float | None = None) -> str | None:
        """Recibe la lectura de un fotograma (None si no hubo). Devuelve la palabra
        cuando queda confirmada por primera vez.

        frame_gap: segundos entre los fotogramas que entrega el canal. Si son muy
        espaciados (p. ej. un keyframe cada 4 s), esperar una segunda lectura puede
        hacer perder la palabra, así que basta con una."""
        if not word:
            self._candidate, self._count = None, 0
            return None
        key = word.casefold()
        if key == self._candidate:
            self._count += 1
        else:
            self._candidate, self._count = key, 1
        required = self.config.reads_required
        if frame_gap is not None and frame_gap >= self.config.sparse_frame_gap:
            required = 1
        if self._count < required:
            return None

        now = self.clock()
        last = self._sent.get(key)
        if last is not None and now - last < self.config.cooldown_seconds:
            return None
        self._sent[key] = now
        return word
