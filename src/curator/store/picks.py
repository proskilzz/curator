"""Seeds for picks, the TMDB title cache, and saving a batch of candidates + picks."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from curator.model import Candidate, Pick, Title, TitleInfo

Ref = tuple[str, int]  # (kind, tmdb_id)

TITLE_DAYS = 30
NOT_FOUND_DAYS = 3


def seed_refs(conn: sqlite3.Connection, limit: int = 10) -> list[Ref]:
    """The newest library titles that TMDB knows, newest first."""
    rows = conn.execute(
        """SELECT e.kind, e.tmdb_id FROM enrichment_cache e
           JOIN library_items li ON li.media_key = e.media_key
           WHERE e.tmdb_id IS NOT NULL
           GROUP BY e.kind, e.tmdb_id
           ORDER BY MAX(li.first_seen_at) DESC, MIN(e.title) LIMIT ?""",
        (limit,),
    )
    return [(kind, tmdb_id) for kind, tmdb_id in rows]


def library_refs(conn: sqlite3.Connection) -> set[Ref]:
    """Everything already in the library (never offered as a pick)."""
    rows = conn.execute(
        """SELECT kind, tmdb_id FROM enrichment_cache WHERE tmdb_id IS NOT NULL
           AND media_key IN (SELECT media_key FROM library_items)"""
    )
    return {(kind, tmdb_id) for kind, tmdb_id in rows}


def cached_titles(conn: sqlite3.Connection, now: datetime) -> dict[Ref, TitleInfo | None]:
    """Fresh cache entries; a None value means TMDB said 'not found'."""
    rows = conn.execute(
        "SELECT kind, tmdb_id, info_json FROM title_cache WHERE expires_at > ?", (_iso(now),)
    )
    return {(k, i): _info(json.loads(raw)) if raw else None for k, i, raw in rows}


def save_title(conn: sqlite3.Connection, ref: Ref, info: TitleInfo | None, now: datetime) -> None:
    days = TITLE_DAYS if info else NOT_FOUND_DAYS
    raw = json.dumps(asdict(info)) if info else None
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO title_cache VALUES (?, ?, ?, ?, ?)",
            (*ref, raw, _iso(now), _iso(now + timedelta(days=days))),
        )


def save_batch(
    conn: sqlite3.Connection,
    batch_id: str,
    candidates: list[Candidate],
    picks: list[Pick],
    model: str,
) -> None:
    """All candidates of one batch, then its picks (status 'picked'), in one transaction."""
    with conn:
        ids = {c.number: _insert_candidate(conn, batch_id, c) for c in candidates}
        for rank, pick in enumerate(picks, start=1):
            conn.execute(
                """INSERT INTO picks (batch_id, candidate_id, rank_order, slot_type, llm_model,
                   llm_reason, reason_by) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (batch_id, ids[pick.number], rank, pick.slot, model, pick.reason, pick.reason_by),
            )
            conn.execute(
                "UPDATE candidates SET status = 'picked' WHERE id = ?", (ids[pick.number],)
            )


def _insert_candidate(conn: sqlite3.Connection, batch_id: str, c: Candidate) -> int:
    t = c.title
    cursor = conn.execute(
        """INSERT INTO candidates (batch_id, number, kind, tmdb_id, title, release_year,
           seeds_json, shared_creators_json, shared_keywords_json, deterministic_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            *(batch_id, c.number, t.kind, t.tmdb_id, t.title, t.year),
            *(json.dumps(list(c.seeds)), json.dumps(list(c.shared_creators))),
            *(json.dumps(list(c.shared_keywords)), c.score),
        ),
    )
    return int(cursor.lastrowid or 0)


def _info(raw: dict[str, Any]) -> TitleInfo:
    return TitleInfo(_title(raw["title"]), tuple(_title(r) for r in raw["recommendations"]))


def _title(raw: dict[str, Any]) -> Title:
    lists: dict[str, Any] = {k: tuple(raw.pop(k, ())) for k in ("genres", "keywords", "creators")}
    return Title(**raw, **lists)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
