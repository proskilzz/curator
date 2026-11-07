"""LocalModel against a fake llama-server (no process, no network)."""

from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from curator.llm import LlmError, LocalModel, default_model_path
from curator.llm import server as srv


class FakeServer:
    """Answers /health and chat; healthy `ready_after` health checks after start."""

    def __init__(self, up: bool = False, ready_after: int = 2, content: str = '{"a": 1}') -> None:
        self.up, self.ready_after, self.content = up, ready_after, content
        self.started: list[list[str]] = []
        self.stopped = 0
        self.bodies: list[dict[str, Any]] = []

    def post(self, url: str, body: dict[str, Any] | None) -> Any:
        if url.endswith("/health"):
            if not self.up and self.started:
                self.ready_after -= 1
                self.up = self.ready_after <= 0
            if not self.up:
                raise LlmError("local model: URLError")
            return {"status": "ok"}
        assert body is not None
        self.bodies.append(body)
        return {"choices": [{"message": {"content": self.content}}]}

    def start(self, argv: list[str]) -> FakeServer:
        self.started.append(argv)
        return self

    def terminate(self) -> None:
        self.stopped += 1

    def wait(self) -> None:
        pass


def _model(tmp_path: Path, fake: FakeServer) -> LocalModel:
    path = tmp_path / "gemma-test.gguf"
    path.write_bytes(b"gguf")
    return LocalModel(path, fake.post, fake.start, sleep=lambda s: None)


def test_starts_the_server_asks_with_the_schema_and_stops_it(tmp_path: Path) -> None:
    fake = FakeServer()
    with _model(tmp_path, fake) as m:
        assert m.chat([{"role": "user", "content": "hi"}], {"type": "object"}) == {"a": 1}
        assert m.name == "gemma-test"
    argv = fake.started[0]
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert argv[argv.index("--port") + 1] == "8099"
    shape = fake.bodies[0]["response_format"]["json_schema"]
    assert shape["strict"] is True and shape["schema"] == {"type": "object"}
    assert fake.bodies[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert fake.stopped == 1


def test_a_running_server_is_used_and_left_running(tmp_path: Path) -> None:
    fake = FakeServer(up=True)
    with LocalModel(tmp_path / "absent.gguf", fake.post, fake.start) as m:
        m.chat([], {})
    assert fake.started == [] and fake.stopped == 0


def test_missing_model_file(tmp_path: Path) -> None:
    fake = FakeServer()
    with pytest.raises(LlmError, match="no local model file"):
        LocalModel(tmp_path / "absent.gguf", fake.post, fake.start).__enter__()


def test_server_that_never_gets_ready_is_stopped(tmp_path: Path) -> None:
    fake = FakeServer(ready_after=10_000)
    with pytest.raises(LlmError, match="did not start"):
        _model(tmp_path, fake).__enter__()
    assert fake.stopped == 1


def test_reply_without_json(tmp_path: Path) -> None:
    fake = FakeServer(up=True, content="Sure! Here are picks")
    with pytest.raises(LlmError, match="no JSON"):
        _model(tmp_path, fake).chat([], {})


def test_http_post_and_model_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def ok(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        assert request.full_url == "http://127.0.0.1:8099/x" and request.data == b'{"q": 1}'
        return io.BytesIO(json.dumps({"ok": True}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", ok)
    assert srv.http_post("http://127.0.0.1:8099/x", {"q": 1}) == {"ok": True}

    def down(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        raise ConnectionRefusedError

    monkeypatch.setattr(urllib.request, "urlopen", down)
    with pytest.raises(LlmError, match="ConnectionRefusedError"):
        srv.http_post("http://127.0.0.1:8099/health", None)

    monkeypatch.setenv("CURATOR_MODEL", "~/m/test.gguf")
    assert default_model_path() == Path.home() / "m" / "test.gguf"
    monkeypatch.delenv("CURATOR_MODEL")
    assert default_model_path().name == "model.gguf"
