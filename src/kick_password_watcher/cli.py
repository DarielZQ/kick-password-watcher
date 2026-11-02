"""Línea de comandos: `uv run kick-password-watcher <comando>`."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from kick_password_watcher.config import PROJECT_ROOT, ConfigError, load_config
from kick_password_watcher.console import disable_quick_edit, setup_logging


def parse_time(value: str) -> float:
    """Acepta segundos ("1918") o h:mm:ss / mm:ss ("31:58")."""
    seconds = 0.0
    for part in value.split(":"):
        seconds = seconds * 60 + float(part)
    return seconds


def read_image(path: str) -> np.ndarray:
    # imdecode para soportar rutas con tildes en Windows.
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def cmd_run(args, config) -> None:
    from kick_password_watcher.app import RaffleBot

    if args.always:
        config.trigger.mode = "always"
    RaffleBot(config).run()


def cmd_detect(args, config) -> None:
    from kick_password_watcher.detection.raffle import RaffleDetector
    from kick_password_watcher.ocr.windows_ocr import WindowsOcr

    detector = RaffleDetector(config.detection, WindowsOcr(config.detection.language))
    for path in args.images:
        start = time.perf_counter()
        result = detector.detect(read_image(path))
        ms = (time.perf_counter() - start) * 1000
        print(f"{path}: {result.word + ' (' + result.method + ')' if result else 'sin contraseña'} [{ms:.0f} ms]")


def cmd_scan(args, config) -> None:
    """Recorre un VOD (o el directo) y muestra lo que detectaría el bot."""
    from kick_password_watcher.capture.stream import StreamSource
    from kick_password_watcher.detection.raffle import RaffleDetector
    from kick_password_watcher.ocr.windows_ocr import WindowsOcr

    detector = RaffleDetector(config.detection, WindowsOcr(config.detection.language))
    source = StreamSource(args.url, args.quality or config.source.quality, not args.all_frames,
                          args.interval, parse_time(args.start) if args.start else None,
                          parse_time(args.end) if args.end else None)
    save = Path(args.save) if args.save else None
    if save:
        save.mkdir(parents=True, exist_ok=True)
    for frame in source.frames():
        result = detector.detect(frame.image)
        stamp = time.strftime("%H:%M:%S", time.gmtime(frame.timestamp))
        if result:
            print(f"{stamp}  {result.word}  ({result.method})", flush=True)
            if save:
                name = f"t{int(frame.timestamp)}_{''.join(c for c in result.word if c.isalnum())}.png"
                (save / name).write_bytes(cv2.imencode(".png", frame.image)[1].tobytes())
        elif args.verbose:
            print(f"{stamp}  -", flush=True)


def cmd_notifications(args, config) -> None:
    """Muestra las notificaciones nuevas para ayudar a configurar las palabras clave."""
    from kick_password_watcher.trigger.discord_notifications import (
        DiscordNotificationTrigger, read_notifications, request_access)

    trigger = DiscordNotificationTrigger(config.trigger)

    async def watch() -> None:
        if not await request_access():
            sys.exit("Acceso a notificaciones denegado por Windows.")
        seen = {n.id for n in await read_notifications()}
        print("Esperando notificaciones nuevas (Ctrl+C para salir)...")
        while True:
            for n in await read_notifications():
                if n.id not in seen:
                    seen.add(n.id)
                    mark = "DISPARA" if trigger.matches(n) else "ignorada"
                    print(f"[{mark}] {n.app}: {' | '.join(n.texts)}", flush=True)
            await asyncio.sleep(0.5)

    asyncio.run(watch())


def cmd_test_output(args, config) -> None:
    from kick_password_watcher.output.handlers import OutputDispatcher

    OutputDispatcher(config.output).emit(args.word)
    print("Salidas ejecutadas; revisa el portapapeles y tu canal de Discord.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kick-password-watcher", description=__doc__)
    parser.add_argument("--config", type=Path, help="YAML extra que sobreescribe la configuración")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="Arranca el bot")
    p.add_argument("--always", action="store_true", help="Buscar siempre, sin esperar notificación")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("detect", help="Prueba la detección sobre imágenes")
    p.add_argument("images", nargs="+")
    p.set_defaults(func=cmd_detect)

    p = sub.add_parser("scan", help="Recorre un VOD/directo mostrando las detecciones")
    p.add_argument("url")
    p.add_argument("--start", help="inicio, p. ej. 31:30")
    p.add_argument("--end", help="fin, p. ej. 33:00")
    p.add_argument("--quality")
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--all-frames", action="store_true", help="No limitarse a fotogramas clave")
    p.add_argument("--save", help="Carpeta donde guardar los fotogramas detectados")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("notifications", help="Muestra notificaciones nuevas y si disparan el bot")
    p.set_defaults(func=cmd_notifications)

    p = sub.add_parser("test-output", help="Envía una palabra de prueba a las salidas")
    p.add_argument("word", nargs="?", default="prueba")
    p.set_defaults(func=cmd_test_output)

    args = parser.parse_args(argv)
    disable_quick_edit()
    # Sólo el bot en marcha deja registro en archivo (logs/ está en .gitignore).
    setup_logging(args.verbose, PROJECT_ROOT / "logs" / "kick-password-watcher.log" if args.command == "run" else None)
    try:
        args.func(args, load_config(args.config))
    except ConfigError as exc:
        sys.exit(f"Error de configuración: {exc}")
    except KeyboardInterrupt:
        print("\nDetenido.")


if __name__ == "__main__":
    main()
