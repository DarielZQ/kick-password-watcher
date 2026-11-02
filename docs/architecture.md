# Arquitectura

```
                 ┌─────────────────────┐
                 │ trigger/            │  notificación de Discord (Windows)
                 │ discord_notifications│──► activa búsqueda intensiva N s
                 └─────────┬───────────┘
                           │ is_active()
┌──────────────┐   Frame   ▼             ┌──────────────┐  palabra  ┌─────────────┐  ┌──────────────┐
│ capture/     │──────► app.RaffleBot ──►│ detection/   │──────────►│ confirm.py  │─►│ output/      │
│ stream.py    │  (keyframes, 1080p)     │ raffle.py    │           │ N lecturas  │  │ portapapeles │
│ screen.py    │                         │  + ocr/      │           │ + cooldown  │  │ webhook      │
└──────────────┘                         └──────────────┘           └─────────────┘  │ sonido, PNG  │
                                                                                     └──────────────┘
```

## Módulos (`src/kick_password_watcher/`)

| Módulo | Responsabilidad |
|---|---|
| `capture/stream.py` | streamlink + PyAV: fotogramas del canal/VOD sin navegador; reconexión si cae u offline; un hilo por canal cuando hay varios |
| `capture/screen.py` | Alternativa: captura de un monitor con `mss` |
| `ocr/windows_ocr.py` | Envoltorio del OCR de Windows: imagen BGR → líneas con cajas |
| `detection/raffle.py` | Ancla por OCR del título → zona debajo → máscara de color → OCR de la palabra |
| `trigger/discord_notifications.py` | Hilo que sondea notificaciones de Windows y abre la ventana activa |
| `confirm.py` | Exige lecturas iguales consecutivas y evita duplicados |
| `output/handlers.py` | Portapapeles, webhook de Discord, aviso sonoro, guardar fotograma |
| `config.py` | Modelos pydantic; `config/default.yaml` + `config/local.yaml` |
| `cli.py` | Comandos `run`, `detect`, `scan`, `notifications`, `test-output` |

## Varios canales

`source.urls` lista los canales vigilados. Cada uno se lee en su propio hilo y
sus fotogramas llegan etiquetados con el canal. Cada canal confirma la palabra
por su cuenta (2 lecturas seguidas en el mismo canal), pero el registro de
palabras enviadas es común: si el mismo stream sale por dos canales, la
contraseña se envía una vez.

## Ritmo de análisis

- El stream se lee siempre (barato: sólo keyframes, ~1 cada 2 s).
- **Sin notificación**: OCR cada `idle_interval` (4 s) como respaldo.
- **Con notificación** (o al ver el recuadro): OCR en cada keyframe durante
  `active_seconds`.
- Con `reads_required: 2` la palabra se entrega ~2 s después de aparecer.

## Escalado futuro

Todos los usuarios ven el mismo stream, así que lo eficiente es **una sola
instancia** que lea el stream y publique la palabra (un webhook a varios canales,
un bot de Discord propio o una API). Los módulos ya están separados para eso:
sólo cambia `output/`, y el disparador puede omitirse (`mode: always`).
