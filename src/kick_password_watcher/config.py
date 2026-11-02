"""Configuración del bot. Se carga de config/default.yaml y, opcionalmente,
de un archivo local (config/local.yaml) que sobreescribe valores."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "default.yaml"
LOCAL_CONFIG = PROJECT_ROOT / "config" / "local.yaml"


class ConfigError(ValueError):
    """Falta un ajuste imprescindible o tiene un valor no válido."""


class HsvRange(BaseModel):
    """Rango de color en HSV de OpenCV (H: 0-179, S y V: 0-255)."""

    h_min: int = 65
    h_max: int = 95
    s_min: int = 70
    s_max: int = 255
    v_min: int = 100
    v_max: int = 255


class RoiConfig(BaseModel):
    """Zona debajo del título, en múltiplos del tamaño del título."""

    expand_x: float = 0.25  # margen a cada lado (x ancho del título)
    gap: float = 0.1  # espacio entre título y zona (x alto del título)
    height: float = 2.4  # alto de la zona (x alto del título)


class DetectionConfig(BaseModel):
    anchor_text: str = "CONTRASEÑA DE LA RAFFLE"
    anchor_min_similarity: float = 0.75
    text_color: HsvRange = Field(default_factory=HsvRange)
    roi: RoiConfig = Field(default_factory=RoiConfig)
    upscale: float = 3.0
    min_text_pixels: int = 25
    max_word_length: int = 40
    allow_spaces: bool = False
    language: str = "es"


class SourceConfig(BaseModel):
    type: Literal["stream", "screen"] = "stream"
    # Canales vigilados a la vez (p. ej. https://kick.com/<canal>). El mismo stream
    # puede salir por cualquiera de ellos. Sin valor por defecto: van en config/local.yaml.
    urls: list[str] = Field(default_factory=list)
    quality: str = "1080p60,1080p,best"
    keyframes_only: bool = True
    sample_interval: float = 1.0  # segundos entre fotogramas analizados
    offline_retry: float = 30.0  # segundos entre reintentos si el canal está offline
    monitor: int = 1  # sólo para type=screen

    @model_validator(mode="before")
    @classmethod
    def _accept_single_url(cls, data):
        # Compatibilidad con configuraciones antiguas que usaban `url: ...`.
        if isinstance(data, dict) and "url" in data:
            data = dict(data)
            single = data.pop("url")
            data.setdefault("urls", [single] if isinstance(single, str) else single)
        return data

    def require_urls(self) -> list[str]:
        """Devuelve las URLs configuradas o lanza ConfigError si no hay ninguna."""
        urls = [u.strip() for u in self.urls if u and u.strip()]
        if not urls:
            raise ConfigError(
                "No hay canales configurados. Añade al menos una URL en `source.urls` de "
                "config/local.yaml (por ejemplo https://kick.com/<canal>); "
                "tienes un modelo en config/local.example.yaml.")
        return urls


class TriggerConfig(BaseModel):
    mode: Literal["discord", "always"] = "discord"
    app_name: str = "Discord"
    keywords: list[str] = Field(default_factory=list)  # vacío = cualquier notificación de Discord
    active_seconds: float = 90.0  # tiempo de búsqueda intensiva tras una notificación
    idle_interval: float = 2.0  # segundos entre revisiones sin notificación (0 = no revisar)
    poll_interval: float = 0.5


class ConfirmConfig(BaseModel):
    reads_required: int = 2  # lecturas iguales seguidas para aceptar la palabra
    # Si el canal entrega fotogramas cada N s o más (keyframes espaciados), basta 1 lectura.
    sparse_frame_gap: float = 3.0
    cooldown_seconds: float = 300.0  # no repetir la misma palabra en este tiempo


class OutputConfig(BaseModel):
    clipboard: bool = True
    discord_webhook_url: str = ""
    extra_webhook_urls: list[str] = Field(default_factory=list)  # otros canales con el mismo mensaje
    message_template: str = "Contraseña del sorteo: **{word}**"
    beep: bool = True
    save_frames_dir: str = ""  # vacío = no guardar fotogramas (sólo para depurar)


class AppConfig(BaseModel):
    source: SourceConfig = Field(default_factory=SourceConfig)
    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    confirm: ConfirmConfig = Field(default_factory=ConfirmConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def _merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path | None = None) -> AppConfig:
    data: dict = {}
    for file in (DEFAULT_CONFIG, LOCAL_CONFIG, path):
        if file and Path(file).exists():
            data = _merge(data, yaml.safe_load(Path(file).read_text(encoding="utf-8")) or {})
    return AppConfig.model_validate(data)
