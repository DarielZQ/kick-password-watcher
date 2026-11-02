# Registro de decisiones

## ADR-001 · Leer el stream directo en vez de capturar la pantalla — 2026-10-16

**Contexto:** el usuario quiere que funcione sin tener la pestaña visible.
**Decisión:** fuente principal `streamlink` + PyAV. La captura de pantalla queda
como alternativa (`source.type: screen`).
**Consecuencias:** funciona en segundo plano, con resolución nativa 1080p sin
zoom del navegador ni UI encima. Depende del plugin de Kick de streamlink: si
Kick cambia su API hay que actualizar streamlink.

## ADR-002 · Ubicar por el título (OCR) y aislar la palabra por color — 2026-10-16

**Contexto:** la idea inicial era guiarse sólo por los colores del recuadro.
**Decisión:** el título "CONTRASEÑA DE LA RAFFLE" se busca con OCR en el
fotograma completo (independiente de posición y escala). El color verde menta se
usa para recortar y binarizar la palabra antes del OCR final.
**Motivo:** hay otros verdes parecidos en el overlay; el título es único. El
color sigue siendo clave para leer la palabra con precisión.
**Alternativas descartadas:** sólo color (falsos positivos); plantilla de
imagen (frágil ante escalado); servicio externo de visión (latencia y coste).

## ADR-003 · OCR de Windows — 2026-10-16

**Decisión:** `Windows.Media.Ocr` con idioma español.
**Motivo:** gratis, sin instalación, ~300 ms en 1080p, lee tildes y ñ.
**Alternativas:** Tesseract (requiere instalar binario), EasyOCR (pesado, usa torch).

## ADR-004 · Disparador por notificaciones de Windows — 2026-10-16

**Contexto:** el usuario sólo es miembro del servidor de Discord.
**Decisión:** `UserNotificationListener` (API oficial de Windows).
**Descartado:** self-bot de Discord (viola los ToS, riesgo de baneo).
**Respaldo:** revisión cada 4 s aunque no llegue notificación.

## ADR-005 · Salida a Discord por webhook — 2026-10-16

**Decisión:** el canal propio recibe la palabra vía webhook (no hace falta bot).
La URL es un secreto: va en `config/local.yaml` (ignorado por git) o en la
variable `KICK_PW_DISCORD_WEBHOOK`.

## ADR-006 · Confirmación con 2 lecturas — 2026-10-16

**Decisión:** aceptar la palabra cuando se lee igual en 2 keyframes seguidos.
**Compromiso:** +2 s de latencia a cambio de evitar lecturas parciales durante
animaciones. Configurable (`confirm.reads_required: 1` para máxima velocidad).

## ADR-007 · Revisión continua como mecanismo principal — 2026-10-18

**Contexto:** en el primer directo probado, la contraseña ("wanted") apareció en
pantalla **antes** de que se anunciara la raffle en Discord.
**Decisión:** analizar cada keyframe (`idle_interval: 2`) siempre, sin esperar
notificación. El disparador de Discord queda como complemento.
**Coste:** ~250 ms de OCR cada 2 s (~12 % de un núcleo). Latencia: 2–4 s desde
que aparece la palabra.

## ADR-008 · Desactivar QuickEdit y registrar en archivo — 2026-10-21

**Contexto:** el bot leyó "cosplay" pero se quedó congelado al escribir el aviso
en CMD: un clic en la ventana activa la selección de texto (QuickEdit) y pausa
cualquier escritura en consola. No llegó ni al portapapeles ni a Discord.
**Decisión:** desactivar QuickEdit al arrancar, enviar la palabra antes de
escribir el log y guardar el registro en `logs/kick-password-watcher.log` (rotativo, 1 MB × 3).

## ADR-009 · Vigilar varios canales a la vez — 2026-10-28

**Contexto:** el mismo stream a veces se emite desde un segundo canal
(`kick.com/<canal_b>`) en lugar del habitual (`kick.com/<canal_a>`).
**Decisión:** `source.urls` con varios canales, un hilo de lectura por canal y
confirmación por canal con registro de envíos compartido.
**Coste:** cuando sólo uno está en directo, igual que antes. Si los dos emiten
a la vez se duplica el trabajo (~25 % de un núcleo).

## ADR-010 · Confirmación según la separación de keyframes — 2026-10-28

**Contexto:** un canal emitía un keyframe cada 4.2 s (otro, cada 2 s).
En uno de los sorteos sólo dos keyframes mostraron la palabra: con 2 lecturas
obligatorias, una contraseña visible ~5 s se habría perdido.
**Decisión:** cada canal mide cada cuánto entrega fotogramas; si es cada
`sparse_frame_gap` (3 s) o más, basta 1 lectura. En canales con keyframes cada
2 s se siguen exigiendo 2.
**Descartado:** decodificar todos los fotogramas (66 % de un núcleo a 1080p60,
19 % a 720p60, de forma continua).
