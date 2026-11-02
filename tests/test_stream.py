import numpy as np
import pytest
from streamlink.exceptions import PluginError

from kick_password_watcher.capture import stream
from kick_password_watcher.capture.stream import (Frame, KickApiError, StreamOffline, live_frames,
                                   merged_live_frames, resolve)


class FakeSession:
    """Simula streamlink: devuelve (o lanza) las respuestas en orden."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self):  # se usa como reemplazo de streamlink.Streamlink
        return self

    def streams(self, url):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(stream.time, "sleep", lambda s: None)


def test_resolve_retries_after_kick_504(monkeypatch):
    session = FakeSession([PluginError("504 Server Error: Gateway Timeout"), {"best": "hls"}])
    monkeypatch.setattr(stream.streamlink, "Streamlink", session)
    assert resolve("https://kick.com/x", "best") == "hls"
    assert session.calls == 2


def test_resolve_raises_kick_api_error_when_api_keeps_failing(monkeypatch):
    monkeypatch.setattr(stream.streamlink, "Streamlink", FakeSession([PluginError("504")] * 3))
    with pytest.raises(KickApiError):
        resolve("https://kick.com/x", "best")


def test_resolve_offline_when_no_streams(monkeypatch):
    monkeypatch.setattr(stream.streamlink, "Streamlink", FakeSession([{}] * 3))
    with pytest.raises(StreamOffline) as info:
        resolve("https://kick.com/x", "best")
    assert not isinstance(info.value, KickApiError)


class FlakySource:
    """Falla de distintas formas antes de entregar un fotograma."""

    url = "https://kick.com/canal_b"

    def __init__(self, failures):
        self.failures = list(failures)

    def frames(self):
        if self.failures:
            raise self.failures.pop(0)
        yield Frame(np.zeros((1, 1, 3), np.uint8), 1.0)


def test_live_frames_survives_api_and_unexpected_errors():
    source = FlakySource([KickApiError("504"), PluginError("403"), StreamOffline("offline"), ValueError("raro")])
    frame = next(live_frames(source, offline_retry=0))
    assert frame.timestamp == 1.0
    assert frame.source == "canal_b"


class EndlessSource:
    def __init__(self, url):
        self.url = url

    def frames(self):
        t = 0.0
        while True:
            t += 2.0
            yield Frame(np.zeros((1, 1, 3), np.uint8), t)


def test_merged_live_frames_reads_every_channel():
    frames = merged_live_frames([EndlessSource("https://kick.com/canal_a"),
                                 EndlessSource("https://kick.com/canal_b")], offline_retry=0)
    seen = {next(frames).source for _ in range(50)}
    assert seen == {"canal_a", "canal_b"}


def test_channel_status_is_reported_to_listeners(monkeypatch):
    monkeypatch.setattr(stream, "channel_status", {})
    seen = []
    monkeypatch.setattr(stream, "status_listeners", [lambda s: seen.append(dict(s))])
    source = FlakySource([StreamOffline("offline")])
    next(live_frames(source, offline_retry=0))
    assert [s["canal_b"] for s in seen] == ["conectando", "offline", "EN DIRECTO"]


def test_describe_status():
    assert stream.describe_status({"canal_b": "EN DIRECTO", "canal_a": "offline"}) == \
        "canal_b: EN DIRECTO · canal_a: offline"
