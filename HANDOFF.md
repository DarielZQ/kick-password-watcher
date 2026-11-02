# Traspaso

Notas para retomar el proyecto.

## Arrancar rápido

```bash
uv sync
uv run pytest -q
uv run kick-password-watcher scan https://kick.com/<canal>/videos/<id-del-vod> --start 31:50 --end 32:10
```

El último comando, sobre un VOD en el que salga un sorteo, debe imprimir la
contraseña varias veces: confirma de punta a punta que streamlink, PyAV y el OCR
funcionan.

## Dónde mirar

- Lógica de detección: `src/kick_password_watcher/detection/raffle.py` (ver ADR-002).
- Ajustes sin tocar código: `config/default.yaml`; canales, webhook y ajustes
  personales en `config/local.yaml` (modelo en `config/local.example.yaml`).
- Imágenes de prueba sintéticas: `tests/conftest.py`. Capturas reales opcionales
  en `tests/fixtures/privadas/` (ignorada por git).

## Trampas conocidas

- Cloudflare de Kick a veces rechaza la primera petición de streamlink (hay reintentos).
- El OCR confunde "I"/"l" en sans-serif; se corrige por contexto en `fix_ambiguous_glyphs`.
- Si el overlay cambia el texto del título o el color, ajustar `detection.anchor_text`
  y `detection.text_color`.
- Las notificaciones de Discord sólo llegan si Discord tiene activadas las
  notificaciones de escritorio y Windows no está en modo "No molestar"
  (en ese modo puede que no se registren; la revisión continua sigue funcionando).
- CMD pausa el programa si se hace clic dentro de la ventana (QuickEdit). El bot
  lo desactiva al arrancar (`kick_password_watcher/console.py`) y envía la palabra
  antes de escribir en pantalla. Registro completo en `logs/kick-password-watcher.log`.
- Cada canal de Kick puede tener otra separación de keyframes (p. ej. 2 s o 4.2 s).
  El bot la mide sola; ver ADR-010.
- El título de la ventana muestra el estado de cada canal
  ("Mi bot | canal_a: EN DIRECTO · canal_b: offline") y cada 10 min en directo se
  escribe "Sigo en directo: N fotogramas analizados". El título conserva el nombre
  original de la ventana por si un lanzador lo usa para no abrir bots duplicados.
