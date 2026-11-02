"""Detección de la contraseña de la raffle dentro de un fotograma.

Estrategia (ver docs/decisions.md, ADR-002):
1. OCR del fotograma completo para encontrar el título ancla
   ("CONTRASEÑA DE LA RAFFLE"). Funciona en cualquier posición y escala.
2. Recortar la zona justo debajo del título.
3. Aislar el texto por su color (verde menta) para limpiar el fondo.
4. OCR del recorte limpio -> palabra. Si falla, se usa la línea leída en el paso 1.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import cv2
import numpy as np

from kick_password_watcher.config import DetectionConfig
from kick_password_watcher.ocr.windows_ocr import Box, OcrLine, WindowsOcr


@dataclass
class Detection:
    word: str
    anchor_box: Box
    word_box: Box | None
    method: str  # "color-mask" | "roi" | "full-frame"


def normalize(text: str) -> str:
    """Mayúsculas, sin tildes y sin signos: para comparar textos leídos por OCR."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9 ]", "", text.upper()).strip()


def fix_ambiguous_glyphs(word: str) -> str:
    """En fuentes sans-serif la "I" mayúscula y la "l" minúscula son idénticas.
    Una "I" precedida de minúscula casi siempre es una "l" ("raffIe" -> "raffle")."""
    while (fixed := re.sub(r"(?<=[a-zà-ÿ])I", "l", word)) != word:
        word = fixed  # se repite para cadenas como "IIi" ("pasteIIito")
    return word


class RaffleDetector:
    def __init__(self, config: DetectionConfig, ocr: WindowsOcr) -> None:
        self.config = config
        self.ocr = ocr
        self._anchor = normalize(config.anchor_text)
        c = config.text_color
        self._hsv_low = np.array([c.h_min, c.s_min, c.v_min], dtype=np.uint8)
        self._hsv_high = np.array([c.h_max, c.s_max, c.v_max], dtype=np.uint8)

    def detect(self, frame: np.ndarray) -> Detection | None:
        lines = self.ocr.recognize(frame)
        anchor = self._find_anchor(lines)
        if anchor is None:
            return None

        roi_box = self._roi_below(anchor.box, frame.shape)
        x0, y0, x1, y1 = (int(round(v)) for v in (roi_box.x, roi_box.y, roi_box.right, roi_box.bottom))
        roi = frame[y0:y1, x0:x1]
        if roi.size == 0:
            return None

        word, local_box, method = self._read_by_color(roi)
        if not word:
            word, local_box, method = self._read_plain(roi)
        if word:
            box = Box(local_box.x + x0, local_box.y + y0, local_box.w, local_box.h) if local_box else None
            return Detection(word, anchor.box, box, method)

        # Último recurso: la línea que el OCR completo leyó debajo del título.
        below = self._line_below(lines, anchor, roi_box)
        if below is not None:
            return Detection(below.text.strip(), anchor.box, below.box, "full-frame")
        return None

    # --- ancla -----------------------------------------------------------

    def _find_anchor(self, lines: list[OcrLine]) -> OcrLine | None:
        best, best_score = None, 0.0
        for line in lines:
            text = normalize(line.text)
            if not text:
                continue
            score = SequenceMatcher(None, text, self._anchor).ratio()
            if score > best_score:
                best, best_score = line, score
        return best if best_score >= self.config.anchor_min_similarity else None

    def _roi_below(self, anchor: Box, shape: tuple[int, ...]) -> Box:
        h, w = shape[:2]
        r = self.config.roi
        x0 = max(0.0, anchor.x - anchor.w * r.expand_x)
        x1 = min(float(w), anchor.right + anchor.w * r.expand_x)
        y0 = max(0.0, anchor.bottom + anchor.h * r.gap)
        y1 = min(float(h), anchor.bottom + anchor.h * r.height)
        return Box(x0, y0, max(0.0, x1 - x0), max(0.0, y1 - y0))

    @staticmethod
    def _line_below(lines: list[OcrLine], anchor: OcrLine, roi: Box) -> OcrLine | None:
        candidates = [
            line for line in lines
            if line is not anchor
            and roi.y <= line.box.y + line.box.h / 2 <= roi.bottom
            and roi.x <= line.box.x + line.box.w / 2 <= roi.right
        ]
        return min(candidates, key=lambda line: line.box.y, default=None)

    # --- lectura de la palabra -------------------------------------------

    def text_mask(self, image: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        return cv2.inRange(hsv, self._hsv_low, self._hsv_high)

    def _read_by_color(self, roi: np.ndarray) -> tuple[str, Box | None, str]:
        scale = self.config.upscale
        big = cv2.resize(roi, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        mask = self.text_mask(big)
        if cv2.countNonZero(mask) < self.config.min_text_pixels * scale * scale:
            return "", None, "color-mask"

        ys, xs = np.nonzero(mask)
        pad = int(4 * scale)
        x0, x1 = max(0, int(xs.min()) - pad), min(mask.shape[1], int(xs.max()) + pad)
        y0, y1 = max(0, int(ys.min()) - pad), min(mask.shape[0], int(ys.max()) + pad)
        # Texto negro sobre fondo blanco: lo que mejor lee el OCR.
        clean = cv2.bitwise_not(mask[y0:y1, x0:x1])
        clean = cv2.copyMakeBorder(clean, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)
        clean = cv2.GaussianBlur(clean, (3, 3), 0)

        word = self._join(self.ocr.recognize(clean))
        box = Box(x0 / scale, y0 / scale, (x1 - x0) / scale, (y1 - y0) / scale)
        return word, box, "color-mask"

    def _read_plain(self, roi: np.ndarray) -> tuple[str, Box | None, str]:
        scale = self.config.upscale
        big = cv2.resize(roi, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        lines = self.ocr.recognize(big)
        if not lines:
            return "", None, "roi"
        return self._join(lines[:1]), lines[0].box.scaled(1 / scale), "roi"

    def _join(self, lines: list[OcrLine]) -> str:
        text = " ".join(line.text for line in lines).strip()
        # Las palabras de la raffle no llevan espacios; se unen las partes
        # que el OCR a veces separa ("sar dina" -> "sardina").
        if not self.config.allow_spaces:
            text = text.replace(" ", "")
        text = fix_ambiguous_glyphs(text)
        return text if len(text) <= self.config.max_word_length else ""
