"""Turn the model's reply into 3 safe picks. Never trusts it: an id outside the batch, a repeat,
or a reason that names nothing shared is replaced by plain code. An empty reply (model down)
gives 3 plain-code picks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from curator.model import SLOTS, Candidate, Pick

MAX_REASON = 160
WILDCARD_RATING = 7.3

Chooser = Callable[[list[Candidate]], Candidate | None]


def check(reply: Any, candidates: list[Candidate]) -> list[Pick]:
    """Valid model choices first (so a replacement never steals one), then fill the rest."""
    chosen = _model_choices(reply if isinstance(reply, dict) else {}, candidates)
    for slot in SLOTS:
        if slot not in chosen:
            taken = {p.number for p in chosen.values()}
            pick = _plain(slot, [c for c in candidates if c.number not in taken])
            if pick:
                chosen[slot] = pick
    return [chosen[slot] for slot in SLOTS if slot in chosen]


def _model_choices(reply: dict[str, Any], candidates: list[Candidate]) -> dict[str, Pick]:
    by_number = {c.number: c for c in candidates}
    chosen: dict[str, Pick] = {}
    for slot in SLOTS:
        raw = reply.get(slot)
        entry: dict[str, Any] = raw if isinstance(raw, dict) else {}
        c = by_number.get(entry.get("candidate_id", 0))
        if c and c.number not in {p.number for p in chosen.values()}:
            chosen[slot] = _with_reason(slot, c, entry.get("reason"))
    return chosen


def _with_reason(slot: str, c: Candidate, reason: Any) -> Pick:
    if isinstance(reason, str) and len(reason) <= MAX_REASON and names_evidence(reason, c):
        return Pick(slot, c.number, reason.strip(), "model")
    return Pick(slot, c.number, plain_reason(c), "code")


def names_evidence(reason: str, c: Candidate) -> bool:
    text = reason.lower()
    return any(e.lower() in text for e in c.evidence if e)


def _plain(slot: str, free: list[Candidate]) -> Pick | None:
    chosen = CHOOSERS[slot](free)
    return Pick(slot, chosen.number, plain_reason(chosen), "code") if chosen else None


def plain_reason(c: Candidate) -> str:
    text = f"Recommended from your {' and '.join(c.seeds[:2])}"
    if c.shared_creators:
        text += f"; also by {c.shared_creators[0]}"
    elif c.shared_keywords:
        text += f"; shares '{c.shared_keywords[0]}'"
    return text[: MAX_REASON - 1] + "…" if len(text) > MAX_REASON else text + "."


def _best(free: list[Candidate]) -> Candidate | None:
    return free[0] if free else None


def _creator_tone(free: list[Candidate]) -> Candidate | None:
    shared = [c for c in free if c.shared_creators] or [c for c in free if c.shared_keywords]
    return _best(shared or free)


def _wildcard(free: list[Candidate]) -> Candidate | None:
    rated = sorted(free, key=lambda c: -c.title.vote_average)
    return _best([c for c in rated if c.title.vote_average >= WILDCARD_RATING] or rated)


CHOOSERS: dict[str, Chooser] = {
    "high_affinity": _best,
    "creator_tone": _creator_tone,
    "wildcard": _wildcard,
}
