"""Make outside text safe to show and (later) to hand to the local model."""

from __future__ import annotations

import re

_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_CHAT_TOKEN = re.compile(r"<\|[^|>]*\|>|\[/?INST\]|</?s>", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(text: str | None, limit: int = 300) -> str:
    """No URLs, no chat-template tokens, no control characters, at most `limit` chars."""
    text = _CHAT_TOKEN.sub(" ", _URL.sub(" ", text or ""))
    text = " ".join(_CONTROL.sub(" ", text).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
