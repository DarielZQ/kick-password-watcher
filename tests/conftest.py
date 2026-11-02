"""Utilidades comunes de las pruebas.

Hay dos tipos de imágenes:

- Sintéticas: se generan aquí por código (PIL + OpenCV) con un recuadro que imita
  el estilo del overlay y contraseñas inventadas. Siempre están disponibles.
- Privadas: capturas reales de streams en ``tests/fixtures/privadas/``. No se
  publican (muestran a terceros) y están en .gitignore; las pruebas que las usan
  se omiten si faltan.
"""

from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from kick_password_watcher.config import DetectionConfig
from kick_password_watcher.detection.raffle import RaffleDetector
from kick_password_watcher.ocr.windows_ocr import WindowsOcr

PRIVATE_FIXTURES = Path(__file__).parent / "fixtures" / "privadas"
PRIVATE_REASON = ("falta la fixture privada tests/fixtures/privadas/{name} "
                  "(capturas reales de streams que no se publican)")

FONT_CANDIDATES = [Path(r"C:\Windows\Fonts\segoeuib.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")]
BOLD_FONT = next((f for f in FONT_CANDIDATES if f.exists()), None)
requires_font = pytest.mark.skipif(
    BOLD_FONT is None,
    reason="no hay una fuente en negrita (Segoe UI Bold o Arial Bold) para generar imágenes sintéticas")

# Colores (RGB) medidos en el overlay real; ver docs/research.md.
BOX_BACKGROUND = (58, 64, 80)
BOX_BORDER = (88, 96, 114)
TITLE_COLOR = (245, 245, 245)
WORD_COLOR = (55, 178, 130)
ANCHOR_TEXT = DetectionConfig().anchor_text


# --- fixtures privadas ----------------------------------------------------

def private(name: str):
    """Parámetro de prueba que se omite con un motivo claro si la captura no está."""
    missing = not (PRIVATE_FIXTURES / name).exists()
    return pytest.param(name, id=name,
                        marks=pytest.mark.skipif(missing, reason=PRIVATE_REASON.format(name=name)))


def skip_unless_private(*names: str) -> pytest.MarkDecorator:
    missing = [n for n in names if not (PRIVATE_FIXTURES / n).exists()]
    return pytest.mark.skipif(bool(missing), reason=PRIVATE_REASON.format(name=", ".join(missing)))


def load(name: str) -> np.ndarray:
    return cv2.imread(str(PRIVATE_FIXTURES / name))


# --- imágenes sintéticas --------------------------------------------------

def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(BOLD_FONT), size)


def render_synthetic_box(word: str, title: str = ANCHOR_TEXT, scale: float = 1.0) -> np.ndarray:
    """Recuadro con el título ancla y la palabra en verde menta, como el overlay (BGR)."""
    w, h = int(round(475 * scale)), int(round(77 * scale))
    image = Image.new("RGB", (w, h), BOX_BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=int(10 * scale), fill=BOX_BACKGROUND,
                           outline=BOX_BORDER, width=max(1, int(2 * scale)))
    title_font, word_font = _font(int(round(21 * scale))), _font(int(round(20 * scale)))
    tw = draw.textlength(title, font=title_font)
    draw.text(((w - tw) / 2, 9 * scale), title, font=title_font, fill=TITLE_COLOR)
    ww = draw.textlength(word, font=word_font)
    draw.text(((w - ww) / 2, 39 * scale), word, font=word_font, fill=WORD_COLOR)
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def render_synthetic_frame(word: str | None, position: tuple[int, int] = (650, 865),
                           scale: float = 1.4, seed: int = 0) -> np.ndarray:
    """Fotograma 1080p inventado: fondo con ruido, paneles, un chat con usuarios ficticios
    que escriben "contraseña" y "raffles", textos verdes parecidos a la palabra (señuelos) y,
    si ``word`` no es None, el recuadro de la contraseña en ``position``."""
    rng = np.random.default_rng(seed)
    base = np.linspace(20, 45, 1080, dtype=np.float32)[:, None, None]
    frame = np.clip(base + rng.normal(0, 6, (1080, 1920, 3)), 0, 255).astype(np.uint8)
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)

    # Paneles del "overlay" con textos que no son la contraseña.
    draw.rounded_rectangle((20, 820, 320, 1000), radius=12, fill=(18, 24, 38))
    draw.text((40, 840), "INFO", font=_font(30), fill=TITLE_COLOR)
    draw.text((40, 900), "RTP 96.50%", font=_font(28), fill=WORD_COLOR)  # verde señuelo
    draw.text((40, 950), "Sin récord", font=_font(26), fill=WORD_COLOR)  # verde señuelo
    draw.rounded_rectangle((1440, 90, 1900, 560), radius=16, fill=(16, 22, 40))
    draw.text((1460, 110), "CHAT", font=_font(26), fill=WORD_COLOR)
    chat = [("UsuarioEjemplo1", "escribir una contraseña?"),
            ("UsuarioEjemplo2", "cuando son las raffles"),
            ("UsuarioEjemplo3", "suerte a todos"),
            ("UsuarioEjemplo4", "contraseña de la raffle?")]
    for i, (user, text) in enumerate(chat):
        y = 160 + i * 48
        draw.text((1460, y), f"{user}: {text}", font=_font(18), fill=TITLE_COLOR)
    # Una "cámara" inventada: bloque de colores difuminados.
    cam = rng.integers(0, 255, (300, 520, 3), dtype=np.uint8)
    image.paste(Image.fromarray(cv2.GaussianBlur(cam, (31, 31), 0)), (1380, 760))

    frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    if word is not None:
        box = render_synthetic_box(word, scale=scale)
        h, w = box.shape[:2]
        x, y = position
        frame[y:y + h, x:x + w] = box
    return frame


# --- detector -------------------------------------------------------------

@pytest.fixture(scope="session")
def ocr() -> WindowsOcr:
    return WindowsOcr("es")


@pytest.fixture(scope="session")
def detector(ocr) -> RaffleDetector:
    return RaffleDetector(DetectionConfig(), ocr)
