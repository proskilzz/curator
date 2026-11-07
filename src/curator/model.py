"""Core data shapes shared by every module. Imports nothing from curator."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class SkipReason(StrEnum):
    NOT_VIDEO = "not a video file"
    PERSONAL = "camera or screen recording"
    YOUTUBE = "YouTube download (handled in a later slice)"
    SAMPLE = "sample clip"
    NO_SIGNAL = "name has no year, episode or release tags"


@dataclass(frozen=True)
class FileInfo:
    """A file found on disk."""

    path: str
    name: str
    size_bytes: int
    mtime: int


@dataclass(frozen=True)
class Movie:
    title: str
    year: int | None


@dataclass(frozen=True)
class Episode:
    show: str
    season: int
    episode: int  # last episode in the file (a double episode E01-E02 counts as 2)


@dataclass(frozen=True)
class Parsed:
    """A file the scanner recognised as a movie or a TV episode."""

    file: FileInfo
    media: Movie | Episode
    resolution: str | None = None
    video_codec: str | None = None

    @property
    def kind(self) -> str:
        return "episode" if isinstance(self.media, Episode) else "movie"

    @property
    def media_key(self) -> str:
        """Offline key, e.g. 'local:tv:severance' or 'local:movie:dune-2024'.

        The enricher (slice 4) maps these to TMDB ids; the local key never changes.
        """
        if isinstance(self.media, Episode):
            return f"local:tv:{slug(self.media.show)}"
        year = f"-{self.media.year}" if self.media.year else ""
        return f"local:movie:{slug(self.media.title)}{year}"

    @property
    def title(self) -> str:
        return self.media.show if isinstance(self.media, Episode) else self.media.title


@dataclass(frozen=True)
class Skipped:
    file: FileInfo
    reason: SkipReason


@dataclass(frozen=True)
class Progress:
    """How far the user has got in one show. Never moves backwards."""

    season: int
    episode: int
    state: str  # 'tracking' or 'unverified_pack' (others come later)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# --- Enrichment (slice 4): what crosses scan/store -> enrich -> store -> app ---


@dataclass(frozen=True)
class Lookup:
    """One library title the enricher should match online."""

    media_key: str  # offline key, e.g. 'local:tv:severance'
    kind: str  # 'movie' or 'tv'
    title: str
    year: int | None = None


@dataclass(frozen=True)
class EpisodeRef:
    season: int
    episode: int
    air_date: str | None  # 'YYYY-MM-DD', or None when not announced


@dataclass(frozen=True)
class Enrichment:
    """What TMDB + TVmaze said about one library title. tmdb_id None = not found."""

    media_key: str
    kind: str  # 'movie' or 'tv'
    title: str
    tmdb_id: int | None = None
    year: int | None = None
    imdb_id: str | None = None
    tvdb_id: int | None = None
    tvmaze_id: int | None = None
    overview: str = ""  # sanitised, at most 300 chars
    genres: tuple[str, ...] = ()
    poster_path: str | None = None  # TMDB image path like '/abc.jpg'
    show_status: str | None = None  # TVmaze: 'Running', 'Ended', ...
    latest: EpisodeRef | None = None  # last episode that has aired
    upcoming: EpisodeRef | None = None  # next announced episode

    @property
    def found(self) -> bool:
        return self.tmdb_id is not None


# --- Picks (slice 5): enrich -> store -> picks -> llm -> store -> app ---

SLOTS = ("high_affinity", "creator_tone", "wildcard")


@dataclass(frozen=True)
class Title:
    """One TMDB title with what the scorer needs. Text is already cleaned by enrich."""

    kind: str  # 'movie' or 'tv'
    tmdb_id: int
    title: str
    year: int | None = None
    overview: str = ""  # cleaned, at most 250 chars
    genres: tuple[str, ...] = ()  # names; empty for a bare recommendation
    keywords: tuple[str, ...] = ()
    creators: tuple[str, ...] = ()  # directors + writers (movie), created_by (tv)
    popularity: float = 0.0
    vote_average: float = 0.0
    vote_count: int = 0
    runtime_minutes: int | None = None
    adult: bool = False

    @property
    def ref(self) -> tuple[str, int]:
        return (self.kind, self.tmdb_id)


@dataclass(frozen=True)
class TitleInfo:
    """A title plus what TMDB recommends for it (one call: details + recommendations)."""

    title: Title
    recommendations: tuple[Title, ...] = ()


@dataclass(frozen=True)
class Candidate:
    """A scored title that is not in the library. `number` is its id in the LLM prompt (1..15)."""

    number: int
    title: Title
    score: float
    seeds: tuple[str, ...]  # library titles that recommended it
    shared_creators: tuple[str, ...] = ()
    shared_keywords: tuple[str, ...] = ()

    @property
    def evidence(self) -> tuple[str, ...]:
        """What a reason must name: a shared creator or keyword; a seed title only when there
        is none (naming the seed alone let a made-up keyword through, 2026-11-06)."""
        return (self.shared_creators + self.shared_keywords) or self.seeds


@dataclass(frozen=True)
class Pick:
    slot: str  # one of SLOTS
    number: int  # Candidate.number
    reason: str  # at most 160 chars, names something in Candidate.evidence
    reason_by: str  # 'model', or 'code' when the model's reason was missing or vague
