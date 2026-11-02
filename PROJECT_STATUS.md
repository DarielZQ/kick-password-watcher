# Estado del proyecto

## Hecho

- Lectura del stream de Kick sin navegador (streamlink + PyAV, keyframes 1080p).
- Detección del recuadro por OCR del título + aislamiento de la palabra por color.
- Validado sobre VODs y directos reales: contraseña detectada y confirmada en ~2 s.
- Tildes, ñ y números verificados con imágenes sintéticas.
- Disparador por notificaciones de Windows (sondeo cada 0.5 s).
- Salidas: portapapeles, webhook de Discord, sonido, guardar fotograma.
- CLI (`run`, `detect`, `scan`, `notifications`, `test-output`) y pruebas automáticas.
- Revisión continua en cada keyframe (la palabra puede salir antes del aviso de Discord).
- Reintentos ante fallos o límites de Discord y ante errores de la API de Kick (504).
- Las capturas sólo viven en memoria (no se guardan salvo que se configure).
- QuickEdit de CMD desactivado; registro en `logs/kick-password-watcher.log`.
- Envío a varios webhooks (`extra_webhook_urls`).
- Vigila varios canales a la vez sin duplicar envíos.
- Sin canales fijos en el código: se configuran en `config/local.yaml`.

## Pendiente

- [ ] Ver una notificación real de Discord con `kick-password-watcher notifications` y ajustar `trigger.keywords`.
- [ ] Juntar más capturas propias (otras palabras/posiciones) con `kick-password-watcher scan --save`.

## Ideas futuras

- Instancia central que publique a varios usuarios (ver docs/architecture.md).
- Arranque automático con Windows / icono en la bandeja del sistema.
- Empaquetar como `.exe` (PyInstaller) para usuarios sin Python.
