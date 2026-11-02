import logging

from kick_password_watcher.config import OutputConfig
from kick_password_watcher.console import disable_quick_edit, setup_logging
from kick_password_watcher.output import handlers


def test_emit_sends_before_logging(monkeypatch):
    """Si escribir en la consola se bloquea, la palabra ya tiene que estar enviada."""
    order = []
    monkeypatch.setattr(handlers.pyperclip, "copy", lambda w: order.append("clipboard"))
    monkeypatch.setattr(handlers, "send_discord_webhook", lambda url, msg: order.append("discord"))
    monkeypatch.setattr(handlers.log, "info", lambda *a: order.append("log"))
    dispatcher = handlers.OutputDispatcher(OutputConfig(discord_webhook_url="https://x", beep=False))
    dispatcher.emit("cosplay")
    assert order == ["clipboard", "discord", "log"]


def test_emit_sends_to_every_webhook(monkeypatch):
    sent = []
    monkeypatch.setattr(handlers.pyperclip, "copy", lambda w: None)
    monkeypatch.setattr(handlers, "send_discord_webhook", lambda url, msg: sent.append((url, msg)))
    dispatcher = handlers.OutputDispatcher(OutputConfig(discord_webhook_url="https://todo", beep=False,
                                                        extra_webhook_urls=["https://extra"]))
    dispatcher.emit("cosplay")
    assert [url for url, _ in sent] == ["https://todo", "https://extra"]


def test_setup_logging_writes_file(tmp_path, monkeypatch):
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    log_file = tmp_path / "logs" / "bot.log"
    setup_logging(False, log_file)
    logging.getLogger("kick_password_watcher.test").info("CONTRASEÑA DETECTADA: cosplay")
    for h in root.handlers:
        h.flush()
    assert "CONTRASEÑA DETECTADA: cosplay" in log_file.read_text(encoding="utf-8")
    for h in root.handlers:
        h.close()


def test_disable_quick_edit_never_crashes():
    assert disable_quick_edit() in (True, False)
