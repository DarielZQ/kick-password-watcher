"""Disparador: escucha las notificaciones de Windows y reacciona a las de Discord.

Usa la API oficial UserNotificationListener. No toca la cuenta de Discord ni
requiere bots en el servidor: sólo lee las notificaciones que Windows ya muestra.
Requisito: notificaciones de escritorio de Discord activadas y permiso de
"acceso a notificaciones" para Python (Windows lo pide la primera vez).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass

from winrt.windows.ui.notifications import KnownNotificationBindings, NotificationKinds
from winrt.windows.ui.notifications.management import (
    UserNotificationListener,
    UserNotificationListenerAccessStatus,
)

from kick_password_watcher.config import TriggerConfig
from kick_password_watcher.detection.raffle import normalize

log = logging.getLogger(__name__)


@dataclass
class Notification:
    id: int
    app: str
    texts: list[str]


async def request_access() -> bool:
    status = await UserNotificationListener.current.request_access_async()
    return status == UserNotificationListenerAccessStatus.ALLOWED


async def read_notifications() -> list[Notification]:
    raw = await UserNotificationListener.current.get_notifications_async(NotificationKinds.TOAST)
    result = []
    for n in raw:
        try:
            app = n.app_info.display_info.display_name
        except OSError:
            app = ""
        binding = n.notification.visual.get_binding(KnownNotificationBindings.toast_generic)
        texts = [t.text for t in binding.get_text_elements()] if binding else []
        result.append(Notification(n.id, app, texts))
    return result


class DiscordNotificationTrigger:
    """Hilo en segundo plano que activa la ventana de búsqueda al llegar una notificación."""

    def __init__(self, config: TriggerConfig) -> None:
        self.config = config
        self._active_until = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._keywords = [normalize(k) for k in config.keywords if k.strip()]

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="discord-trigger", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def activate(self, seconds: float | None = None) -> None:
        with self._lock:
            self._active_until = max(self._active_until, time.monotonic() + (seconds or self.config.active_seconds))

    def is_active(self) -> bool:
        if self.config.mode == "always":
            return True
        with self._lock:
            return time.monotonic() < self._active_until

    def matches(self, notification: Notification) -> bool:
        if normalize(self.config.app_name) not in normalize(notification.app):
            return False
        if not self._keywords:
            return True
        text = normalize(" ".join(notification.texts))
        return any(k in text for k in self._keywords)

    def _run(self) -> None:
        asyncio.run(self._poll())

    async def _poll(self) -> None:
        if not await request_access():
            log.error("Windows denegó el acceso a las notificaciones. Actívalo en "
                      "Configuración > Privacidad y seguridad > Notificaciones.")
            return
        # Las notificaciones ya existentes al arrancar no cuentan.
        seen = {n.id for n in await read_notifications()}
        log.info("Escuchando notificaciones de %s", self.config.app_name)
        while not self._stop.is_set():
            try:
                for n in await read_notifications():
                    if n.id in seen:
                        continue
                    seen.add(n.id)
                    if self.matches(n):
                        title = n.texts[0] if n.texts else ""
                        log.info("Notificación de Discord: %r -> búsqueda activa %.0f s",
                                 title, self.config.active_seconds)
                        self.activate()
            except OSError as exc:
                log.warning("Error leyendo notificaciones: %s", exc)
            await asyncio.sleep(self.config.poll_interval)
