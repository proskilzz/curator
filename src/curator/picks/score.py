"""Plain-code candidate score (Argon review §6). No model, no network, no SQL.

score = 2.5 * seeds that recommend it + 3.0 * shared creators (max 2)
      + 1.5 * sum of keyword taste + 1.0 * sum of genre taste - 0.8 * log10(max(10, popularity))
Taste of a keyword/genre = share of library seeds that have it (0..1).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace

from curator.model import Candidate, Title, TitleInfo

Ref = tuple[str, int]
Pooled = tuple[Title, tuple[str, ...]]  # title + the seed titles that recommended it

SHORTLIST = 30  # how many get a details call before the full score
TOP = 15  # how many the local model sees
MIN_VOTES = 150
MIN_RATING = 6.2
SHOWN_KEYWORDS = 5


def shortlist(seeds: list[TitleInfo], exclude: set[Ref], size: int = SHORTLIST) -> list[Pooled]:
    """Recommendations not in the library and good enough, most-recommended first."""
    titles: dict[Ref, Title] = {}
    seeds_for: dict[Ref, list[str]] = {}
    for seed in seeds:
        for rec in seed.recommendations:
            if _eligible(rec, exclude) and seed.title.title not in seeds_for.get(rec.ref, []):
                titles.setdefault(rec.ref, rec)
                seeds_for.setdefault(rec.ref, []).append(seed.title.title)

    def first_pass(ref: Ref) -> tuple[float, float]:
        t = titles[ref]
        return (-(2.5 * len(seeds_for[ref]) - _popularity_penalty(t)), -t.vote_average)

    ranked = sorted(titles, key=first_pass)[:size]
    return [(titles[ref], tuple(seeds_for[ref])) for ref in ranked]


@dataclass(frozen=True)
class Taste:
    keywords: dict[str, float]
    genres: dict[str, float]
    creators: frozenset[str]

    @classmethod
    def of(cls, seeds: list[Title]) -> Taste:
        n = max(1, len(seeds))
        kws = Counter(k for s in seeds for k in set(s.keywords))
        genres = Counter(g for s in seeds for g in set(s.genres))
        return cls(
            {k: c / n for k, c in kws.items()},
            {g: c / n for g, c in genres.items()},
            frozenset(c for s in seeds for c in s.creators),
        )


def rank(seeds: list[Title], pooled: list[Pooled], top: int = TOP) -> list[Candidate]:
    """Full score for each detailed title; best `top`, numbered 1.. for the prompt."""
    taste = Taste.of(seeds)
    scored = sorted(
        (score(t, s, taste) for t, s in pooled), key=lambda c: (-c.score, c.title.title)
    )
    best: dict[str, Candidate] = {}  # one per name: TMDB has 'Top Boy' 2011 and 2019
    for c in scored:
        best.setdefault(c.title.title.casefold(), c)
    return [replace(c, number=i) for i, c in enumerate(list(best.values())[:top], start=1)]


def score(title: Title, seeds: tuple[str, ...], taste: Taste) -> Candidate:
    creators = tuple(c for c in title.creators if c in taste.creators)
    keywords = sorted(
        (k for k in title.keywords if k in taste.keywords), key=lambda k: (-taste.keywords[k], k)
    )
    points = (
        2.5 * len(seeds)
        + 3.0 * min(len(creators), 2)
        + 1.5 * sum(taste.keywords[k] for k in keywords)
        + 1.0 * sum(taste.genres.get(g, 0.0) for g in title.genres)
        - _popularity_penalty(title)
    )
    return Candidate(0, title, round(points, 3), seeds, creators, tuple(keywords[:SHOWN_KEYWORDS]))


def _eligible(title: Title, exclude: set[Ref]) -> bool:
    good = title.vote_count >= MIN_VOTES and title.vote_average >= MIN_RATING
    return good and not title.adult and title.ref not in exclude


def _popularity_penalty(title: Title) -> float:
    return 0.8 * math.log10(max(10.0, title.popularity))
