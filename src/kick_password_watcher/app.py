"""Bucle principal: fotogramas -> detección -> confirmación -> salidas."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from kick_password_watcher.capture.screen import ScreenSource
from kick_password_watcher.capture import stream
from kick_password_watcher.capture.stream import Frame, StreamSource, live_frames, merged_live_frames
from kick_password_watcher.config import AppConfig
from kick_password_watcher.confirm import WordConfirmer
from kick_password_watcher.console import set_status_title
from kick_password_watcher.detection.raffle import RaffleDetector
from kick_password_watcher.ocr.windows_ocr import WindowsOcr
from kick_password_watcher.output.handlers import OutputDispatcher
from kick_password_watcher.trigger.discord_notifications import DiscordNotificationTrigger

log = logging.getLogger(__name__)

STATUS_EVERY = 600  # segundos de stream entre avisos de "sigo en directo"


def build_frames(config: AppConfig) -> Iterator[Frame]:
    src = config.source
    if src.type == "screen":
        return ScreenSource(src.monitor, src.sample_interval).frames()
    urls = src.require_urls()  # error claro si no hay canales configurados
    streams = [StreamSource(url, src.quality, src.keyframes_only, src.sample_interval) for url in urls]
    if len(streams) == 1:
        return live_frames(streams[0], src.offline_retry)
    return merged_live_frames(streams, src.offline_retry)


@dataclass
class _ChannelState:
    """Lo que se lleva por separado de cada canal vigilado."""

    confirmer: WordConfirmer
    last_check: float = -1e9
    last_frame: float | None = None  # para medir cada cuánto entrega fotogramas el canal
    frame_gap: float | None = None
    last_heartbeat: float = -1e9
    last_status: float | None = None
    checks_at_status: int = 0
    frames_seen: int = 0
    checks: int = 0


class RaffleBot:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.ocr = WindowsOcr(config.detection.language)
        self.detector = RaffleDetector(config.detection, self.ocr)
        # Cooldown compartido: si la palabra sale en dos canales, se envía una sola vez.
        self._sent_words: dict[str, float] = {}
        self._channels: dict[str, _ChannelState] = {}
        self.trigger = DiscordNotificationTrigger(config.trigger)
        self.output = OutputDispatcher(config.output)

    def run(self, frames: Iterable[Frame] | None = None) -> None:
        if frames is None:
            frames = build_frames(self.config)
        log.info("OCR: %s | fuente: %s | disparador: %s", self.ocr.language,
                 ", ".join(self.config.source.urls) if self.config.source.type == "stream" else "pantalla",
                 self.config.trigger.mode)
        stream.status_listeners.append(lambda status: set_status_title(stream.describe_status(status)))
        if self.config.trigger.mode == "discord":
            self.trigger.start()
        try:
            self.process(frames)
        finally:
            self.trigger.stop()

    def _channel(self, name: str) -> _ChannelState:
        if name not in self._channels:
            self._channels[name] = _ChannelState(WordConfirmer(self.config.confirm, sent=self._sent_words))
        return self._channels[name]

    def process(self, frames: Iterable[Frame]) -> None:
        for frame in frames:
            ch = self._channel(frame.source)
            ch.frames_seen += 1
            if ch.last_frame is not None and 0 < frame.timestamp - ch.last_frame < 30:
                ch.frame_gap = frame.timestamp - ch.last_frame
            ch.last_frame = frame.timestamp
            if ch.last_status is None or frame.timestamp < ch.last_status:
                ch.last_status, ch.checks_at_status = frame.timestamp, ch.checks  # (re)conexión
            elif frame.timestamp - ch.last_status >= STATUS_EVERY:
                log.info("[%s] Sigo en directo: %d fotogramas analizados en los últimos %d min",
                         frame.source, ch.checks - ch.checks_at_status, STATUS_EVERY // 60)
                ch.last_status, ch.checks_at_status = frame.timestamp, ch.checks
            if frame.timestamp - ch.last_heartbeat >= 60:
                log.debug("[%s] Activo: t=%.0f s, %d fotogramas recibidos, %d analizados",
                          frame.source, frame.timestamp, ch.frames_seen, ch.checks)
                ch.last_heartbeat = frame.timestamp
            active = self.trigger.is_active()
            interval = 0.0 if active else self.config.trigger.idle_interval
            if not active and interval <= 0:
                continue
            # Tolerancia: los keyframes llegan cada ~2.0 s y no deben saltarse por redondeo.
            if frame.timestamp - ch.last_check < interval - 0.25:
                continue
            ch.last_check = frame.timestamp
            ch.checks += 1

            detection = self.detector.detect(frame.image)
            if detection is None:
                ch.confirmer.feed(None)
                continue
            log.debug("[%s] t=%.1f lectura=%r (%s)", frame.source, frame.timestamp,
                      detection.word, detection.method)
            # Si aparece el recuadro sin notificación previa, se pasa a modo intensivo.
            self.trigger.activate(30)
            word = ch.confirmer.feed(detection.word, ch.frame_gap)
            if word:
                self.output.emit(word, frame.image)
