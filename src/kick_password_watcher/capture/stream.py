"""Fuente de fotogramas leyendo el stream de Kick directo (sin navegador).

- streamlink resuelve la URL del canal/VOD a un stream HLS.
- PyAV (ffmpeg) decodifica el video en memoria.
- Con keyframes_only se decodifican sólo los fotogramas clave (~1 cada 2 s en
  Kick), lo que reduce mucho el uso de CPU.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import av
import numpy as np
import streamlink
from streamlink.exceptions import StreamlinkError
from streamlink.stream.hls import HLSStream

log = logging.getLogger(__name__)


class StreamOffline(Exception):
    pass


class KickApiError(StreamOffline):
    """Kick no respondió bien (504, 403 de Cloudflare...). Suele ser temporal."""


@dataclass
class Frame:
    image: np.ndarray  # BGR
    timestamp: float  # segundos dentro del stream
    source: str = ""  # canal del que viene (p. ej. "canal_a")


def channel_name(url: str) -> str:
    """https://kick.com/canal_a -> "canal_a"."""
    return url.rstrip("/").rsplit("/", 1)[-1]


# Estado actual de cada canal ("EN DIRECTO", "offline"...), para mostrarlo en pantalla.
channel_status: dict[str, str] = {}
status_listeners: list[Callable[[dict[str, str]], None]] = []
_status_lock = threading.Lock()


def set_channel_status(name: str, status: str) -> None:
    with _status_lock:
        if channel_status.get(name) == status:
            return
        channel_status[name] = status
        snapshot = dict(channel_status)
    for listener in status_listeners:
        try:
            listener(snapshot)
        except Exception:  # mostrar el estado nunca debe afectar a la lectura
            log.debug("Fallo al notificar el estado", exc_info=True)


def describe_status(status: dict[str, str]) -> str:
    """{"canal_a": "EN DIRECTO", "canal_b": "offline"} -> "canal_a: EN DIRECTO · canal_b: offline"."""
    return " · ".join(f"{name}: {value}" for name, value in status.items())


def resolve(url: str, quality: str, attempts: int = 3) -> HLSStream:
    session = streamlink.Streamlink()
    streams = {}
    error: StreamlinkError | None = None
    # Cloudflare de Kick a veces rechaza la primera petición y su API a veces
    # responde 504: se reintenta.
    for attempt in range(attempts):
        try:
            streams = session.streams(url)
            error = None
        except StreamlinkError as exc:
            streams, error = {}, exc
        if streams:
            break
        if attempt < attempts - 1:
            time.sleep(2 * (attempt + 1))
    if error is not None:
        raise KickApiError(str(error)) from error
    if not streams:
        raise StreamOffline(f"Sin streams disponibles en {url} (¿canal offline?)")
    for name in [q.strip() for q in quality.split(",")]:
        if name in streams:
            log.info("Calidad elegida: %s", name)
            return streams[name]
    raise StreamOffline(f"Ninguna calidad de {quality!r} disponible: {list(streams)}")


class StreamSource:
    def __init__(
        self,
        url: str,
        quality: str = "best",
        keyframes_only: bool = True,
        sample_interval: float = 1.0,
        start: float | None = None,
        end: float | None = None,
    ) -> None:
        self.url = url
        self.quality = quality
        self.keyframes_only = keyframes_only
        self.sample_interval = sample_interval
        self.start = start
        self.end = end

    def frames(self) -> Iterator[Frame]:
        stream = resolve(self.url, self.quality)
        headers = "".join(f"{k}: {v}\r\n" for k, v in stream.args.get("headers", {}).items())
        container = av.open(stream.url, options={"headers": headers} if headers else None, timeout=20)
        try:
            video = container.streams.video[0]
            if self.keyframes_only:
                video.codec_context.skip_frame = "NONKEY"
            if self.start:
                container.seek(int(self.start * av.time_base))
            last = -1e9
            for frame in container.decode(video):
                if frame.time is None:
                    continue
                if self.start and frame.time < self.start:
                    continue
                if self.end and frame.time > self.end:
                    break
                if frame.time - last < self.sample_interval:
                    continue
                last = frame.time
                yield Frame(frame.to_ndarray(format="bgr24"), float(frame.time))
        finally:
            container.close()


def live_frames(source: StreamSource, offline_retry: float, name: str = "") -> Iterator[Frame]:
    """Igual que StreamSource.frames pero reconecta si el canal cae o está offline.
    Los avisos de "offline" se muestran una sola vez hasta que vuelva el directo."""
    name = name or channel_name(source.url)
    offline_logged = False
    set_channel_status(name, "conectando")
    while True:
        try:
            for i, frame in enumerate(source.frames()):
                if i == 0:
                    log.info("[%s] Conectado al directo: buscando la contraseña...", name)
                    set_channel_status(name, "EN DIRECTO")
                    offline_logged = False
                frame.source = name
                yield frame
            log.warning("[%s] El stream terminó; esperando a que vuelva el directo", name)
            set_channel_status(name, "offline")
        except KickApiError as exc:
            log.warning("[%s] Kick no respondió (%s); reintento en %.0f s", name, exc, offline_retry)
            set_channel_status(name, "reintentando")
        except StreamOffline:
            if not offline_logged:
                log.info("[%s] El canal está offline; se conectará solo cuando empiece el directo", name)
                offline_logged = True
            set_channel_status(name, "offline")
        except (av.error.FFmpegError, OSError, StreamlinkError) as exc:
            log.warning("[%s] Error leyendo el stream (%s); reconectando en %.0f s", name, exc, offline_retry)
            set_channel_status(name, "reconectando")
        except Exception:
            # Último recurso: un fallo inesperado no debe cerrar el bot.
            log.exception("[%s] Error inesperado con el stream; reconectando en %.0f s", name, offline_retry)
            set_channel_status(name, "reconectando")
        time.sleep(offline_retry)


def merged_live_frames(sources: list[StreamSource], offline_retry: float,
                       max_pending: int = 8) -> Iterator[Frame]:
    """Vigila varios canales a la vez (un hilo por canal) y entrega sus fotogramas
    en una sola secuencia. Si el análisis va atrasado se descartan fotogramas
    viejos en lugar de acumular retraso."""
    pending: queue.Queue[Frame] = queue.Queue(maxsize=max_pending)

    def reader(source: StreamSource) -> None:
        for frame in live_frames(source, offline_retry):
            while True:
                try:
                    pending.put_nowait(frame)
                    break
                except queue.Full:
                    try:
                        pending.get_nowait()  # se tira el más viejo
                    except queue.Empty:
                        pass

    for source in sources:
        threading.Thread(target=reader, args=(source,), name=f"stream-{channel_name(source.url)}",
                         daemon=True).start()
    while True:
        yield pending.get()
