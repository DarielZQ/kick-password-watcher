from kick_password_watcher.cli import parse_time
import pytest

from kick_password_watcher import config as config_module
from kick_password_watcher.config import (AppConfig, ConfigError, ConfirmConfig, SourceConfig,
                                          TriggerConfig, load_config)
from kick_password_watcher.confirm import WordConfirmer
from kick_password_watcher.trigger.discord_notifications import DiscordNotificationTrigger, Notification


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_confirmer_requires_consecutive_reads():
    c = WordConfirmer(ConfirmConfig(reads_required=2, cooldown_seconds=60), FakeClock())
    assert c.feed("girasl") is None
    assert c.feed("girasol") is None
    assert c.feed("girasol") == "girasol"
    assert c.feed("girasol") is None  # ya enviada


def test_confirmer_resets_on_missing_read():
    c = WordConfirmer(ConfirmConfig(reads_required=2), FakeClock())
    assert c.feed("girasol") is None
    assert c.feed(None) is None
    assert c.feed("girasol") is None


def test_confirmer_cooldown():
    clock = FakeClock()
    c = WordConfirmer(ConfirmConfig(reads_required=1, cooldown_seconds=60), clock)
    assert c.feed("girasol") == "girasol"
    c.feed(None)
    clock.now = 30
    assert c.feed("girasol") is None
    c.feed(None)
    clock.now = 100
    assert c.feed("girasol") == "girasol"


def test_confirmer_accepts_one_read_when_frames_are_sparse():
    c = WordConfirmer(ConfirmConfig(reads_required=2, sparse_frame_gap=3.0), FakeClock())
    assert c.feed("tortuga", frame_gap=2.0) is None        # canal con keyframes cada 2 s
    c.feed(None)
    assert c.feed("tortuga", frame_gap=4.2) == "tortuga"  # canal con keyframes cada 4.2 s


def test_trigger_matching():
    t = DiscordNotificationTrigger(TriggerConfig(keywords=["raffle", "CanalEjemplo"]))
    assert t.matches(Notification(1, "Discord", ["CanalEjemplo", "@everyone RAFFLE en 5 segundos"]))
    assert not t.matches(Notification(2, "Discord", ["Amigo", "hola"]))
    assert not t.matches(Notification(3, "WhatsApp", ["raffle"]))
    assert DiscordNotificationTrigger(TriggerConfig()).matches(Notification(4, "Discord", ["x"]))


def test_trigger_activation_window():
    t = DiscordNotificationTrigger(TriggerConfig(mode="discord"))
    assert not t.is_active()
    t.activate(5)
    assert t.is_active()
    assert DiscordNotificationTrigger(TriggerConfig(mode="always")).is_active()


def test_default_config_loads(monkeypatch, tmp_path):
    # Sin config/local.yaml: sólo los valores por defecto del repositorio.
    monkeypatch.setattr(config_module, "LOCAL_CONFIG", tmp_path / "no-existe.yaml")
    config = load_config()
    assert config.detection.anchor_text == "CONTRASEÑA DE LA RAFFLE"
    assert config.source.urls == []  # sin canales fijos en el código
    assert AppConfig().source.urls == []


def test_missing_urls_raise_clear_error():
    with pytest.raises(ConfigError, match="source.urls"):
        SourceConfig().require_urls()
    with pytest.raises(ConfigError):
        SourceConfig(urls=["  "]).require_urls()
    assert SourceConfig(urls=["https://kick.com/x"]).require_urls() == ["https://kick.com/x"]


def test_local_config_overrides_urls(monkeypatch, tmp_path):
    local = tmp_path / "local.yaml"
    local.write_text("source:\n  urls:\n    - https://kick.com/canal_a\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "LOCAL_CONFIG", local)
    assert load_config().source.urls == ["https://kick.com/canal_a"]


def test_source_accepts_old_single_url():
    assert SourceConfig.model_validate({"url": "https://kick.com/x"}).urls == ["https://kick.com/x"]


def test_parse_time():
    assert parse_time("1918") == 1918
    assert parse_time("31:58") == 1918
    assert parse_time("1:00:05") == 3605
