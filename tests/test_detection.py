import cv2
import pytest

from conftest import (load, private, render_synthetic_box, render_synthetic_frame, requires_font,
                      skip_unless_private)
from kick_password_watcher.detection.raffle import fix_ambiguous_glyphs, normalize

# --- imágenes sintéticas (siempre disponibles) -------------------------------


@requires_font
@pytest.mark.parametrize("word, position", [
    ("girasol", (650, 865)),     # abajo, en el centro (posición habitual)
    ("tortuga", (80, 60)),       # esquina superior izquierda
    ("relampago", (1100, 420)),  # a media altura, a la derecha
])
def test_detects_password_in_synthetic_frames(detector, word, position):
    result = detector.detect(render_synthetic_frame(word, position))
    assert result is not None
    assert result.word == word
    assert result.method == "color-mask"


@requires_font
def test_ignores_synthetic_frame_without_password(detector):
    # El chat ficticio menciona "contraseña" y "raffles" y hay verdes señuelo.
    assert detector.detect(render_synthetic_frame(None)) is None


@requires_font
@pytest.mark.parametrize("scale", [0.75, 1.0, 2.0])
def test_detects_scaled_synthetic_box(detector, scale):
    result = detector.detect(render_synthetic_box("cometa", scale=scale))
    assert result is not None and result.word == "cometa"


@requires_font
@pytest.mark.parametrize("word", ["camión", "ñandú", "pingüino", "raffle2026", "Halloween31"])
def test_reads_accents_and_numbers(detector, word):
    result = detector.detect(render_synthetic_box(word))
    assert result is not None
    assert result.word == word


# --- capturas reales privadas (se omiten si no están) ------------------------


@pytest.mark.parametrize("name", [
    private("box_crop_sardina.png"),          # recorte del recuadro
    private("kick_fullscreen_sardina.png"),   # navegador al 90 %, video escalado
    private("vod1080_t1918_sardina.png"),     # fotograma de un VOD a 1080p (aparición)
    private("vod1080_t1926_sardina.png"),     # fotograma de un VOD a 1080p (final)
    private("live1080_wanted.png"),           # directo, recuadro más ancho y en otra posición
    private("live1080_cosplay.png"),          # directo
    private("canalb1080_lentilla.png"),       # mismo stream emitido desde un segundo canal
])
def test_detects_password_in_real_frames(detector, name):
    expected = name.removesuffix(".png").rsplit("_", 1)[-1]
    result = detector.detect(load(name))
    assert result is not None
    assert result.word == expected
    assert result.method == "color-mask"


@pytest.mark.parametrize("name", [
    private("vod1080_t1887_no_password.png"),            # el chat menciona "raffles"
    private("live1080_chat_contrasena_no_password.png"),  # el chat dice "escribir una contraseña"
])
def test_ignores_frame_without_password(detector, name):
    assert detector.detect(load(name)) is None


@skip_unless_private("vod1080_t1887_no_password.png", "box_crop_sardina.png")
def test_detects_real_box_anywhere_on_screen(detector):
    frame = load("vod1080_t1887_no_password.png")
    box = load("box_crop_sardina.png")
    h, w = box.shape[:2]
    frame[100:100 + h, 300:300 + w] = box  # recuadro en otra posición
    result = detector.detect(frame)
    assert result is not None and result.word == "sardina"


@skip_unless_private("box_crop_sardina.png")
def test_detects_scaled_real_box(detector):
    small = cv2.resize(load("box_crop_sardina.png"), None, fx=0.75, fy=0.75, interpolation=cv2.INTER_AREA)
    result = detector.detect(small)
    assert result is not None and result.word == "sardina"


# --- utilidades de texto -----------------------------------------------------


def test_normalize():
    assert normalize("Contraseña de la Raffle!") == "CONTRASENA DE LA RAFFLE"


def test_fix_ambiguous_glyphs():
    assert fix_ambiguous_glyphs("raffIe2026") == "raffle2026"
    assert fix_ambiguous_glyphs("pasteIIito") == "pastellito"
    assert fix_ambiguous_glyphs("Isla") == "Isla"
    assert fix_ambiguous_glyphs("HOLAIA") == "HOLAIA"
