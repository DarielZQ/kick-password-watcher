"""Bucle principal con varios canales, sin OCR real."""

import numpy as np
import pytest

from kick_password_watcher import app
from kick_password_watcher.capture.stream import Frame
from kick_password_watcher.config import AppConfig, ConfigError
from kick_password_watcher.detection.raffle import Detection
from kick_password_watcher.ocr.windows_ocr import Box


class FakeDetector:
    """La "imagen" lleva la palabra escrita en su primer píxel (índice en WORDS)."""

    WORDS = [None, "cosplay", "wanted"]

    def detect(self, image):
        word = self.WORDS[int(image[0, 0, 0])]
        return Detection(word, Box(0, 0, 1, 1), None, "fake") if word else None


def frame(source, t, word_index):
    img = np.zeros((1, 1, 3), np.uint8)
    img[0, 0, 0] = word_index
    return Frame(img, t, source)


def make_bot(monkeypatch):
    monkeypatch.setattr(app, "WindowsOcr", lambda lang: None)
    bot = app.RaffleBot(AppConfig())
    bot.config.trigger.mode = "always"
    bot.detector = FakeDetector()
    sent = []
    bot.output.emit = lambda word, image=None: sent.append(word)
    return bot, sent


def test_same_password_on_two_channels_is_sent_once(monkeypatch):
    bot, sent = make_bot(monkeypatch)
    # Ambos canales emiten el mismo stream con relojes distintos, intercalados.
    bot.process([frame("canal_a", 100, 1), frame("canal_b", 7, 1),
                 frame("canal_a", 102, 1), frame("canal_b", 9, 1), frame("canal_b", 11, 1)])
    assert sent == ["cosplay"]


def test_each_channel_confirms_on_its_own(monkeypatch):
    bot, sent = make_bot(monkeypatch)
    # Una lectura en cada canal no son "dos lecturas seguidas": hace falta repetir en el mismo.
    bot.process([frame("canal_a", 100, 2), frame("canal_b", 7, 2)])
    assert sent == []
    bot.process([frame("canal_b", 9, 2)])
    assert sent == ["wanted"]


def test_channel_timestamps_do_not_block_each_other(monkeypatch):
    bot, sent = make_bot(monkeypatch)
    # canal_b va "atrasado" en su reloj: no debe saltarse por el intervalo de canal_a.
    bot.process([frame("canal_a", 5000, 0), frame("canal_b", 10, 1), frame("canal_b", 12, 1)])
    assert sent == ["cosplay"]


def test_sparse_keyframes_channel_needs_one_read(monkeypatch):
    bot, sent = make_bot(monkeypatch)
    # canal_b: un keyframe cada 4.2 s; la palabra sólo cae en un fotograma.
    bot.process([frame("canal_b", 100.0, 0), frame("canal_b", 104.2, 1), frame("canal_b", 108.4, 0)])
    assert sent == ["cosplay"]


def test_dense_keyframes_channel_still_needs_two_reads(monkeypatch):
    bot, sent = make_bot(monkeypatch)
    bot.process([frame("canal_a", 100.0, 0), frame("canal_a", 102.0, 1), frame("canal_a", 104.0, 0)])
    assert sent == []


def test_logs_still_live_every_ten_minutes(monkeypatch, caplog):
    bot, _ = make_bot(monkeypatch)
    caplog.set_level("INFO", logger="kick_password_watcher.app")
    bot.process([frame("canal_b", t, 0) for t in range(0, 1300, 4)])
    notices = [r.getMessage() for r in caplog.records if "Sigo en directo" in r.getMessage()]
    assert len(notices) == 2
    assert notices[0].startswith("[canal_b] Sigo en directo: 150 fotogramas")


def test_run_without_channels_fails_clearly(monkeypatch):
    monkeypatch.setattr(app, "WindowsOcr", lambda lang: None)
    bot = app.RaffleBot(AppConfig())  # sin source.urls
    with pytest.raises(ConfigError, match="source.urls"):
        bot.run()
