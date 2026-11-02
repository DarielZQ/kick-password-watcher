"""OCR usando el motor integrado de Windows (Windows.Media.Ocr).

No requiere instalar nada extra: usa los paquetes de idioma OCR de Windows.
Para leer tildes y ñ hace falta un idioma español instalado (p. ej. es-MX, es-ES).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import cv2
import numpy as np
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def scaled(self, factor: float) -> Box:
        return Box(self.x * factor, self.y * factor, self.w * factor, self.h * factor)

    @staticmethod
    def union(boxes: list[Box]) -> Box:
        x0 = min(b.x for b in boxes)
        y0 = min(b.y for b in boxes)
        x1 = max(b.right for b in boxes)
        y1 = max(b.bottom for b in boxes)
        return Box(x0, y0, x1 - x0, y1 - y0)


@dataclass
class OcrLine:
    text: str
    box: Box
    words: list[tuple[str, Box]] = field(default_factory=list)


class WindowsOcr:
    def __init__(self, language: str | None = "es") -> None:
        self.engine = self._create_engine(language)
        self.language = self.engine.recognizer_language.language_tag
        self.max_dimension = OcrEngine.max_image_dimension
        self._loop = asyncio.new_event_loop()

    @staticmethod
    def _create_engine(language: str | None) -> OcrEngine:
        if language:
            available = [lang.language_tag for lang in OcrEngine.available_recognizer_languages]
            # Acepta "es" y elige la primera variante instalada (es-MX, es-ES...).
            match = next(
                (tag for tag in available if tag.lower() == language.lower()),
                next((tag for tag in available if tag.lower().startswith(language.lower())), None),
            )
            if match:
                engine = OcrEngine.try_create_from_language(Language(match))
                if engine:
                    return engine
        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError("No hay idiomas OCR de Windows instalados")
        return engine

    def recognize(self, image: np.ndarray) -> list[OcrLine]:
        """Reconoce texto en una imagen BGR (o en escala de grises) de OpenCV."""
        image, scale = self._fit(image)
        bitmap = self._to_bitmap(image)
        result = self._loop.run_until_complete(self.engine.recognize_async(bitmap))
        lines: list[OcrLine] = []
        for line in result.lines:
            words = []
            for word in line.words:
                r = word.bounding_rect
                words.append((word.text, Box(r.x, r.y, r.width, r.height).scaled(1 / scale)))
            if words:
                lines.append(OcrLine(line.text, Box.union([b for _, b in words]), words))
        return lines

    def _fit(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        h, w = image.shape[:2]
        largest = max(h, w)
        if largest <= self.max_dimension:
            return image, 1.0
        scale = self.max_dimension / largest
        return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA), scale

    @staticmethod
    def _to_bitmap(image: np.ndarray) -> SoftwareBitmap:
        if image.ndim == 2:
            bgra = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
        else:
            bgra = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        h, w = bgra.shape[:2]
        writer = DataWriter()
        writer.write_bytes(np.ascontiguousarray(bgra).tobytes())
        return SoftwareBitmap.create_copy_from_buffer(writer.detach_buffer(), BitmapPixelFormat.BGRA8, w, h)

    def close(self) -> None:
        self._loop.close()
