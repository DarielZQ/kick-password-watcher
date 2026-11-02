# Requisitos

## Contexto

En algunos streams de Kick (`kick.com/<canal>`) se anuncia un sorteo (raffle) por
Discord. Unos 5 s después de la notificación aparece en el video un recuadro
"CONTRASEÑA DE LA RAFFLE" con una palabra en verde, visible 5–10 s. El recuadro
puede aparecer en distintas posiciones de la pantalla.

## Funcionales

- **RF1** Detectar el recuadro y leer la palabra en cualquier posición y escala.
- **RF2** Soportar letras, números, tildes y ñ.
- **RF3** Activarse al llegar una notificación de Discord. El usuario es sólo
  miembro del servidor (no puede añadir bots).
- **RF4** Copiar la palabra al portapapeles.
- **RF5** Enviar la palabra a un canal de Discord propio.
- **RF6** Funcionar en segundo plano, sin necesidad de tener la pestaña del
  navegador visible o abierta.
- **RF7** No enviar la misma palabra más de una vez por raffle.

## No funcionales

- **RNF1** Latencia: palabra entregada antes de que desaparezca (< 5 s desde que aparece).
- **RNF2** Bajo consumo de CPU para dejarlo corriendo durante todo el stream.
- **RNF3** Sin violar los términos de Discord (nada de self-bots).
- **RNF4** Configurable sin tocar código (colores, textos, canal, tiempos).
- **RNF5** Preparado para escalar a más usuarios en el futuro.

## Fuera de alcance (por ahora)

- Escribir automáticamente la contraseña en el chat de Kick.
- Overlays con un diseño muy distinto (posible en parte vía configuración:
  `detection.anchor_text`, `detection.text_color`, `detection.roi`).
