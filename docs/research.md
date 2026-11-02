# Investigación (2026-10-16)

## Origen de la palabra

- La palabra está **quemada en el video** (overlay de OBS), no es HTML en Kick.
  Leer el DOM no es posible → hace falta visión por computadora.

## Acceso al video sin navegador

- `streamlink` (plugin `kick`) resuelve canal y VOD a HLS (Amazon IVS).
  Calidades del VOD de prueba: 160p, 360p, 480p, 720p60, 1080p60.
- Cloudflare de Kick rechaza peticiones de forma intermitente → reintentos con espera.
- PyAV decodifica el HLS en memoria y permite buscar (`seek`) en VODs.
- **Fotogramas clave cada 2 s** en Kick. Decodificar sólo keyframes
  (`skip_frame = NONKEY`) basta para ver la palabra 3–5 veces y ahorra mucha CPU.
- Un navegador en segundo plano o minimizado deja de dibujar el video, por lo
  que capturar la pantalla no sirve si la pestaña no está visible.

## OCR

- El OCR integrado de Windows (`Windows.Media.Ocr`) con `es-MX` instalado lee
  el título y la palabra en el fotograma completo de 1080p en ~300 ms.
- En recortes pequeños tarda ~10 ms.
- Limitación: en fuentes sans-serif "I" mayúscula y "l" minúscula son idénticas;
  se corrige por contexto (una "I" tras minúscula es "l").

## Colores medidos (capturas y VOD de prueba)

| Elemento | Valor |
|---|---|
| Palabra (verde menta) | RGB ≈ (55, 178, 130); HSV OpenCV H 75–84, S 104–252, V 127–219 |
| Título | Blanco (S < 40, V > 200) |
| Fondo del recuadro | Azul grisáceo oscuro, V ≈ 80 |

Otros elementos del overlay usan verdes parecidos (logos de patrocinadores,
porcentajes como "96.50%", nombres del chat), por eso el color **no basta para ubicar** el recuadro: se usa
para limpiar la palabra una vez ubicado el título.

## Notificaciones de Windows

- `UserNotificationListener` funciona desde Python sin empaquetar (acceso "Allowed").
- Se consulta por sondeo cada 0.5 s (el evento `NotificationChanged` no está
  disponible para apps sin identidad de paquete).
- Pendiente: confirmar con una notificación real de Discord el texto que trae
  (título = autor/servidor, cuerpo = mensaje) para ajustar `keywords`.

## Prueba sobre el VOD real

En un VOD de prueba la contraseña aparece de 31:58 a 32:06 (8 s). El bot la
detecta en los 5 keyframes de ese intervalo y la confirma a las 32:00.
