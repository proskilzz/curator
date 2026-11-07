"""File name → Movie / Episode, or a reason to skip. Offline, deterministic."""

from __future__ import annotations

import re
from typing import Any

import guessit

from curator.model import Episode, FileInfo, Movie, Parsed, Skipped, SkipReason

# Phones, cameras, screen recorders. guessit reads IMG_1234 as "S12E34", so these go first.
PERSONAL = re.compile(
    r"^(IMG|VID|PXL|MVI|DSC|DSCF|DJI|GOPR|GX\d|GH\d|RPReplay|ScreenRecording|Screen Recording"
    r"|video-\d{6,})",
    re.IGNORECASE,
)
# Only explicit downloader templates (Argon §1.1); a loose 11-char match hits scene tags.
YOUTUBE = re.compile(r"(?:YTDown\.com_YouTube_Media_|\[)[A-Za-z0-9_-]{11}(?:_|\])")
# guessit happily invents episodes; we only trust an explicit S01E02 / 1x02 in the name.
EPISODE_TAG = re.compile(r"(?:\bS\d{1,2}\s?E\d{1,3}|\b\d{1,2}x\d{2,3}\b)", re.IGNORECASE)
SAMPLE = re.compile(r"\bsample\b", re.IGNORECASE)
RELEASE_TAGS = ("screen_size", "source", "video_codec")


def parse_file(info: FileInfo) -> Parsed | Skipped:
    reason = _pre_skip(info.name)
    if reason:
        return Skipped(info, reason)
    guess: dict[str, Any] = dict(guessit.guessit(info.name))
    media = _episode(guess, info.name) or _movie(guess)
    if media is None:
        return Skipped(info, SkipReason.NO_SIGNAL)
    return Parsed(
        file=info,
        media=media,
        resolution=_str(guess.get("screen_size")),
        video_codec=_str(guess.get("video_codec")),
    )


def _pre_skip(name: str) -> SkipReason | None:
    if PERSONAL.match(name):
        return SkipReason.PERSONAL
    if YOUTUBE.search(name):
        return SkipReason.YOUTUBE
    if SAMPLE.search(name):
        return SkipReason.SAMPLE
    return None


def _episode(guess: dict[str, Any], name: str) -> Episode | None:
    if guess.get("type") != "episode" or not EPISODE_TAG.search(name):
        return None
    season, episode, title = guess.get("season"), guess.get("episode"), guess.get("title")
    if not isinstance(season, int) or episode is None or not title:
        return None
    last = max(episode) if isinstance(episode, list) else episode
    return Episode(show=str(title), season=season, episode=int(last))


def _movie(guess: dict[str, Any]) -> Movie | None:
    title = guess.get("title")
    if guess.get("type") != "movie" or not title:
        return None
    year = guess.get("year")
    if not isinstance(year, int) and not any(guess.get(t) for t in RELEASE_TAGS):
        return None
    return Movie(title=str(title), year=year if isinstance(year, int) else None)


def _str(value: object) -> str | None:
    return str(value) if value else None
