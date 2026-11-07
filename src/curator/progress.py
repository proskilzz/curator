"""Show progress rules (pure, no IO). Argon review §1.2.

- Progress only moves forward: deleting files never lowers it.
- 4+ new episodes of one season in a single scan = a season pack. The user has probably
  not watched them all, so progress points at the pack's FIRST episode, marked
  'unverified_pack' until they confirm.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from curator.model import Episode, Progress

PACK_SIZE = 4


def advance(current: Progress | None, new_episodes: Iterable[Episode]) -> Progress | None:
    """Progress after a scan that found `new_episodes` (files not seen before) of one show."""
    candidate = _candidate(new_episodes)
    if candidate is None:
        return current
    if current is None or _pos(candidate) > _pos(current):
        return candidate
    return current


def _candidate(episodes: Iterable[Episode]) -> Progress | None:
    by_season: dict[int, set[int]] = defaultdict(set)
    for ep in episodes:
        by_season[ep.season].add(ep.episode)
    options = [_season_candidate(season, eps) for season, eps in by_season.items()]
    return max(options, key=_pos, default=None)


def _season_candidate(season: int, episodes: set[int]) -> Progress:
    if len(episodes) >= PACK_SIZE:
        return Progress(season, min(episodes), "unverified_pack")
    return Progress(season, max(episodes), "tracking")


def _pos(p: Progress) -> tuple[int, int]:
    return (p.season, p.episode)
