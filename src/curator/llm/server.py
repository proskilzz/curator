"""The local model: llama.cpp's llama-server on 127.0.0.1, started for one batch of picks and
stopped afterwards (frees ~15 GB). A server that was already running is used and left running."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import Any

HOST = "127.0.0.1"
PORT = 8099
CONTEXT = 8192
START_SECONDS = 180

Post = Callable[[str, dict[str, Any] | None], Any]  # url, JSON body (None = GET) -> JSON reply
Launch = Callable[[list[str]], Any]  # argv -> something with terminate() and wait()


class LlmError(Exception):
    """The model could not be started or gave no usable reply."""


def default_model_path() -> Path:
    """$CURATOR_MODEL, else model.gguf next to the database."""
    env = os.environ.get("CURATOR_MODEL")
    if env:
        return Path(env).expanduser()
    return Path.home() / "Library" / "Application Support" / "Curator" / "model.gguf"


def http_post(url: str, body: dict[str, Any] | None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as reply:
            return json.load(reply)
    except (OSError, ValueError) as err:
        raise LlmError(f"local model: {type(err).__name__}") from None


def launch(argv: list[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class LocalModel:
    """`with LocalModel(path) as m: m.chat(messages, schema)`."""

    def __init__(
        self,
        model_path: Path,
        post: Post = http_post,
        start: Launch = launch,
        sleep: Callable[[float], None] = time.sleep,
        port: int = PORT,
    ) -> None:
        self.model_path = model_path
        self.name = model_path.stem
        self._post, self._start, self._sleep = post, start, sleep
        self._port = port
        self._url = f"http://{HOST}:{port}"
        self._process: Any = None

    def __enter__(self) -> LocalModel:
        if self._healthy():
            return self
        if not self.model_path.is_file():
            raise LlmError("no local model file (set CURATOR_MODEL)")
        binary = shutil.which("llama-server") or "llama-server"
        argv = [binary, "-m", str(self.model_path), "--host", HOST, "--port", str(self._port)]
        self._process = self._start([*argv, "-c", str(CONTEXT)])
        self._wait_until_ready()
        return self

    def __exit__(
        self, kind: type[BaseException] | None, err: BaseException | None, tb: TracebackType | None
    ) -> None:
        if self._process is not None:
            self._process.terminate()
            self._process.wait()
            self._process = None

    def chat(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> Any:
        """The model's JSON answer, shaped by `schema` (llama.cpp grammar)."""
        body = {
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 600,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "curator_picks", "strict": True, "schema": schema},
            },
            "chat_template_kwargs": {"enable_thinking": False},
        }
        reply = self._post(f"{self._url}/v1/chat/completions", body)
        try:
            return json.loads(reply["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, ValueError):
            raise LlmError("local model gave no JSON") from None

    def _healthy(self) -> bool:
        try:
            reply = self._post(f"{self._url}/health", None)
        except LlmError:
            return False
        return isinstance(reply, dict) and reply.get("status") == "ok"

    def _wait_until_ready(self) -> None:
        for _ in range(START_SECONDS):
            if self._healthy():
                return
            self._sleep(1)
        self.__exit__(None, None, None)
        raise LlmError("local model did not start")
