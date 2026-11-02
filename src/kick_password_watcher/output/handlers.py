"""Qué hacer con la palabra detectada: portapapeles, canal de Discord, aviso."""

from __future__ import annotations

import logging
import os
import time
import winsound
from datetime import datetime
from pathlib import Path

import cv2
import httpx
import numpy as np
import pyperclip

from kick_password_watcher.config import PROJECT_ROOT, OutputConfig

log = logging.getLogger(__name__)

# Variable de entorno que, si existe, sustituye a output.discord_webhook_url.
WEBHOOK_ENV_VAR = "KICK_PW_DISCORD_WEBHOOK"


def send_discord_webhook(url: str, content: str, attempts: int = 5) -> None:
    """Envía el mensaje; reintenta ante fallos de red, errores 5xx y límites (429)."""
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.post(url, json={"content": content}, timeout=10)
            if response.status_code == 429:
                wait = float(response.json().get("retry_after", 1))
                raise httpx.HTTPStatusError(f"límite de Discord, espera {wait} s",
                                            request=response.request, response=response)
            response.raise_for_status()
            log.info("Enviada a Discord")
            return
        except httpx.HTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                raise  # URL inválida o webhook borrado: reintentar no sirve
            if attempt == attempts:
                raise
            wait = float(exc.response.json().get("retry_after", 1)) if status == 429 else attempt
            log.warning("Fallo enviando a Discord (%s); reintento %d/%d en %.1f s",
                        exc, attempt, attempts - 1, wait)
            time.sleep(wait)


class OutputDispatcher:
    def __init__(self, config: OutputConfig) -> None:
        self.config = config
        # La URL del webhook es un secreto: mejor en variable de entorno o config/local.yaml.
        self.webhook_url = os.environ.get(WEBHOOK_ENV_VAR) or config.discord_webhook_url
        # El mismo mensaje va también a cada canal extra (p. ej. uno general y otro dedicado).
        self.webhook_urls = [u for u in [self.webhook_url, *config.extra_webhook_urls] if u]

    def emit(self, word: str, frame: np.ndarray | None = None) -> None:
        # Primero lo importante (portapapeles y Discord) y después el log: escribir
        # en la consola puede bloquearse (p. ej. si alguien selecciona texto en CMD).
        if self.config.clipboard:
            self._safe("portapapeles", pyperclip.copy, word)
        message = self.config.message_template.format(word=word)
        for url in self.webhook_urls:
            self._safe("webhook de Discord", send_discord_webhook, url, message)
        log.info("CONTRASEÑA DETECTADA: %s", word)
        if self.config.beep:
            self._safe("aviso sonoro", winsound.MessageBeep, winsound.MB_ICONASTERISK)
        if frame is not None and self.config.save_frames_dir:
            self._safe("guardar fotograma", self._save_frame, word, frame)

    def _save_frame(self, word: str, frame: np.ndarray) -> None:
        folder = PROJECT_ROOT / self.config.save_frames_dir
        folder.mkdir(parents=True, exist_ok=True)
        safe = "".join(c for c in word if c.isalnum()) or "palabra"
        path = folder / f"{datetime.now():%Y%m%d_%H%M%S}_{safe}.png"
        # imencode + write_bytes para soportar rutas con tildes en Windows.
        Path(path).write_bytes(cv2.imencode(".png", frame)[1].tobytes())

    @staticmethod
    def _safe(name: str, func, *args) -> None:
        try:
            func(*args)
        except Exception as exc:  # una salida que falla no debe tumbar al bot
            log.error("Falló la salida '%s': %s", name, exc)
