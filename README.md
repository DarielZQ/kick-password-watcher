# kick-password-watcher

Vigila uno o varios canales de [Kick](https://kick.com) (directo o VOD), detecta
con OCR la **contraseña de un sorteo** que el overlay del stream muestra en
pantalla y la **copia al portapapeles** y la **envía a un canal de Discord** por
webhook.

- **No necesita el navegador abierto.** Lee el video de Kick en segundo plano
  (streamlink + PyAV), así que la pestaña puede estar cerrada.
- **Varios canales a la vez.** Si el mismo stream sale por más de un canal y la
  contraseña aparece en varios, se envía una sola vez.
- **Disparador opcional por notificaciones de Discord** (leídas desde Windows, sin
  bots ni acceso a tu cuenta) y revisión continua por si la notificación no llega.
- Lee tildes, ñ y números (OCR integrado de Windows en español).

## Aviso de uso

Este proyecto es una herramienta personal de lectura de video. Úsalo respetando
los términos de servicio de Kick y de Discord, las reglas de cada canal y de
cada sorteo, y la normativa aplicable. No automatiza la participación en
sorteos ni escribe en el chat; si un sorteo prohíbe herramientas de este tipo,
no la uses ahí.

## Tecnologías

**Lenguajes**

- **Python 3.12**: todo el bot (captura, detección, OCR, confirmación y avisos).
- **PowerShell**: instalador `instalar.ps1` (con `instalar.bat` para lanzarlo con doble clic).
- **Batch (CMD)**: lanzador `scripts/iniciar_bot.bat` para arrancarlo con doble clic.

**Librerías y plataforma**

- **OpenCV** y **NumPy**: localizan el recuadro del overlay por color (HSV) y preparan el recorte para el OCR.
- **OCR de Windows** (`Windows.Media.Ocr`, vía los paquetes **WinRT** para Python): lee el texto en español,
  con tildes y ñ, sin instalar motores de OCR externos.
- **Streamlink**: obtiene la URL HLS del directo o del VOD de Kick.
- **PyAV** (bibliotecas de **FFmpeg** incluidas): decodifica el video en segundo plano, sin navegador.
- **mss**: captura de pantalla como fuente alternativa al stream.
- **Pydantic** y **PyYAML**: configuración en YAML (`config/default.yaml` + `config/local.yaml`) validada con
  tipos.
- **httpx**: envío de la contraseña a los **webhooks de Discord**.
- **Notificaciones de Windows** (`UserNotificationListener`, vía WinRT): lee las notificaciones de escritorio
  de Discord para disparar la búsqueda.
- **pyperclip** y **winsound**: copia al portapapeles y aviso sonoro.
- **Pillow**: genera en las pruebas las imágenes sintéticas del overlay.

**Herramientas**

- **uv**: gestiona la versión de Python, el entorno y las dependencias (`uv.lock`).
- **pytest**: pruebas automáticas con imágenes sintéticas (y capturas privadas opcionales).

## Requisitos

- Windows 10/11 con un idioma OCR español instalado (Configuración > Hora e idioma >
  Idioma > Español > Opciones > Reconocimiento óptico de caracteres).
- [uv](https://docs.astral.sh/uv/) (gestiona Python y dependencias). Si no lo
  tienes, sirve Python 3.12 o superior con venv + pip.
- Para el disparador: notificaciones de escritorio de Discord activadas.

## Instalación con el instalador

Doble clic en `instalar.bat`, o desde PowerShell en la carpeta del proyecto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\instalar.ps1
```

El instalador:

1. Comprueba que estás en Windows con PowerShell 5.1 o superior y busca `uv` o,
   si no está, Python 3.12+ (`py -3.12`, `py -3` o `python`). Si falta algo,
   explica cómo instalarlo (`winget` o la web oficial) y se detiene: **no instala
   nada del sistema por su cuenta**. También avisa si Windows no tiene un idioma
   OCR español.
2. Instala las dependencias con `uv sync` o, sin uv, crea `.venv` e instala el
   proyecto con `pip install -e . --group dev`.
3. Crea `config/local.yaml` a partir de `config/local.example.yaml` **solo si no
   existe**: nunca sobrescribe tu configuración.
4. Pregunta si quieres un acceso directo "Kick Password Watcher" en el
   Escritorio que abre `scripts/iniciar_bot.bat`.

Se puede repetir las veces que haga falta (por ejemplo, para actualizar
dependencias). Para no responder a la pregunta, añade `-AccesoDirecto` o
`-SinAccesoDirecto` (también funcionan con `instalar.bat`).

## Puesta en marcha

Si prefieres instalar a mano:

```bash
uv sync
```

Copia `config/local.example.yaml` como `config/local.yaml` (está en
`.gitignore`; el instalador ya lo crea) y rellena:

```yaml
source:
  urls:
    - https://kick.com/<canal>        # uno o varios canales
output:
  discord_webhook_url: "https://discord.com/api/webhooks/<id>/<token>"
```

El repositorio no trae canales por defecto: si `source.urls` está vacío, el bot
termina con un error que indica qué falta. La URL del webhook también puede ir
en la variable de entorno `KICK_PW_DISCORD_WEBHOOK`.

Si el overlay de tu canal usa otro texto o color, ajusta `detection.anchor_text`
(el título fijo que aparece encima de la contraseña) y `detection.text_color`
(rango HSV de la palabra). El resto de opciones están comentadas en
`config/default.yaml`.

```bash
uv run kick-password-watcher test-output prueba   # prueba portapapeles y webhook
uv run kick-password-watcher run                  # arranca el bot
```

O doble clic en `scripts/iniciar_bot.bat` (o en el acceso directo del Escritorio).
El lanzador usa `uv run` y, si no hay uv, el entorno `.venv` que crea el
instalador.

## Comandos

| Comando | Para qué |
|---|---|
| `kick-password-watcher run` | Arranca el bot (revisión continua + disparador de Discord) |
| `kick-password-watcher run --always` | Busca en cada fotograma, sin depender de la notificación |
| `kick-password-watcher detect img1.png ...` | Prueba la detección sobre capturas |
| `kick-password-watcher scan https://kick.com/<canal>/videos/<id> --start 31:30 --end 33:00 --save data/samples` | Recorre un VOD y muestra qué detectaría |
| `kick-password-watcher notifications` | Muestra las notificaciones nuevas y si disparan el bot (para ajustar `keywords`) |
| `kick-password-watcher test-output [palabra]` | Prueba portapapeles y webhook |

Añade `-v` para ver cada lectura.

## Pruebas

```bash
uv run pytest -q
```

Las pruebas de detección usan imágenes **sintéticas** generadas por código
(`tests/conftest.py`) con contraseñas inventadas. Si además tienes capturas
reales propias en `tests/fixtures/privadas/` (carpeta ignorada por git), se
ejecutan también; si faltan, esas pruebas se omiten con un aviso.

## Documentación

- [Estado del proyecto](PROJECT_STATUS.md) · [Traspaso](HANDOFF.md)
- [Requisitos](docs/requirements.md) · [Investigación](docs/research.md)
- [Arquitectura](docs/architecture.md) · [Decisiones](docs/decisions.md)
