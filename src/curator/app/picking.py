"""One batch of picks: newest library titles -> TMDB details + recommendations (cached 30 days)
-> plain-code top 15 -> local model fills 3 slots -> checked in code -> saved."""

from __future__ import annotations

import secrets
import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any, Protocol

from curator.llm import LlmError
from curator.model import Candidate, Pick, TitleInfo
from curator.picks import check, messages, rank, schema, shortlist
from curator.store import cached_titles, library_refs, save_batch, save_title, seed_refs

Ref = tuple[str, int]
TitleSource = Callable[[str, int], TitleInfo | None]


class Chat(Protocol):
    name: str

    def chat(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> Any: ...


ModelFactory = Callable[[], AbstractContextManager[Chat]]

SLOT_LABELS = {
    "high_affinity": "Most like your library",
    "creator_tone": "Same people or feel",
    "wildcard": "Wildcard",
}
NO_SEEDS = "Check new episodes first, so Curator knows what your titles are."
NO_MODEL = "The local model didn't answer, so these picks are plain-code only."


class _Titles:
    """Cache first; the TMDB source is only built on a miss (it may need the key)."""

    def __init__(self, conn: sqlite3.Connection, source: Callable[[], TitleSource], now: datetime):
        self._conn, self._make, self._now = conn, source, now
        self._cache = cached_titles(conn, now)
        self._source: TitleSource | None = None

    def get(self, ref: Ref) -> TitleInfo | None:
        if ref not in self._cache:
            self._source = self._source or self._make()
            self._cache[ref] = self._source(*ref)
            save_title(self._conn, ref, self._cache[ref], self._now)
        return self._cache[ref]


def make_picks(
    conn: sqlite3.Connection,
    source: Callable[[], TitleSource],
    model: ModelFactory,
    now: datetime,
) -> dict[str, Any]:
    titles = _Titles(conn, source, now)
    seeds = [info for ref in seed_refs(conn) if (info := titles.get(ref))]
    if not seeds:
        return {"error": NO_SEEDS, "picks": []}
    pooled = shortlist(seeds, library_refs(conn))
    detailed = [((titles.get(t.ref) or TitleInfo(t)).title, by) for t, by in pooled]
    candidates = rank([s.title for s in seeds], detailed)
    library = [s.title for s in seeds]
    reply, model_name = _ask(model, messages(library, candidates), schema(candidates))
    picks = check(reply, candidates)
    batch_id = f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')}-{secrets.token_hex(3)}"
    save_batch(conn, batch_id, candidates, picks, model_name)
    return {
        "error": "" if model_name else NO_MODEL,
        "candidates": len(candidates),
        "picks": [_card(p, candidates) for p in picks],
    }


def _ask(model: ModelFactory, prompt: list[dict[str, str]], shape: dict[str, Any]) -> Any:
    try:
        with model() as m:
            return m.chat(prompt, shape), m.name
    except LlmError:
        return {}, ""


def _card(pick: Pick, candidates: list[Candidate]) -> dict[str, Any]:
    c = next(c for c in candidates if c.number == pick.number)
    return {
        "slot": SLOT_LABELS[pick.slot],
        "title": c.title.title,
        "year": c.title.year,
        "kind": c.title.kind,
        "reason": pick.reason,
        "reason_by": pick.reason_by,
        "rating": round(c.title.vote_average, 1),
        "score": c.score,
    }
