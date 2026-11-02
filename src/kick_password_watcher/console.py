"""Ajustes de la consola de Windows y de los logs.

El "modo de edición rápida" (QuickEdit) de CMD pausa el programa en cuanto se
hace clic dentro de la ventana: cualquier escritura en pantalla se queda
bloqueada hasta pulsar Esc. Para un bot que corre horas sin mirar, eso significa
perder la contraseña, así que se desactiva al arrancar.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

STD_INPUT_HANDLE = -10
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def disable_quick_edit() -> bool:
    """Quita QuickEdit de la consola actual. Devuelve True si había consola y se cambió."""
    if sys.platform != "win32":
        return False
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
    mode = ctypes.c_uint32()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return False  # sin consola (salida redirigida, pythonw...)
    new_mode = (mode.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
    return bool(kernel32.SetConsoleMode(handle, new_mode))


_base_title: str | None = None


def set_status_title(status: str) -> bool:
    """Muestra el estado en el título de la ventana: "Mi bot | canal_a: EN DIRECTO · ...".

    Se conserva el nombre original de la ventana (lo que va antes de " - " o " | "),
    porque el lanzador busca las ventanas por ese nombre para no duplicar bots."""
    global _base_title
    if sys.platform != "win32":
        return False
    kernel32 = ctypes.windll.kernel32
    if _base_title is None:
        buffer = ctypes.create_unicode_buffer(1024)
        if not kernel32.GetConsoleTitleW(buffer, len(buffer)):
            return False  # sin consola
        _base_title = buffer.value.split(" | ")[0].split(" - ")[0].strip() or "kick-password-watcher"
    return bool(kernel32.SetConsoleTitleW(f"{_base_title} | {status}"))


def setup_logging(verbose: bool, log_file: Path | None) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        # El archivo lleva fecha completa; la consola, sólo la hora.
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, "%Y-%m-%d %H:%M:%S"))
        handlers.append(file_handler)
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt="%H:%M:%S", handlers=handlers)
    for noisy in ("streamlink", "httpx", "libav", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
