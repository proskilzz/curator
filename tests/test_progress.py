from __future__ import annotations

from curator.model import Episode, Progress
from curator.progress import advance


def eps(season: int, *numbers: int) -> list[Episode]:
    return [Episode("Show", season, n) for n in numbers]


def test_first_episode_starts_tracking() -> None:
    assert advance(None, eps(2, 3)) == Progress(2, 3, "tracking")


def test_nothing_new_keeps_progress() -> None:
    current = Progress(1, 5, "tracking")
    assert advance(current, []) is current
    assert advance(None, []) is None


def test_never_goes_backwards() -> None:
    current = Progress(2, 3, "tracking")
    assert advance(current, eps(1, 1)) is current


def test_three_new_episodes_is_not_a_pack() -> None:
    assert advance(None, eps(1, 1, 2, 3)) == Progress(1, 3, "tracking")


def test_season_pack_points_at_first_episode() -> None:
    assert advance(None, eps(1, *range(1, 11))) == Progress(1, 1, "unverified_pack")


def test_pack_does_not_lower_existing_progress() -> None:
    current = Progress(1, 6, "tracking")
    assert advance(current, eps(1, *range(1, 11))) is current


def test_later_single_episode_beats_pack() -> None:
    result = advance(Progress(1, 1, "unverified_pack"), eps(1, 5))
    assert result == Progress(1, 5, "tracking")


def test_highest_season_wins() -> None:
    assert advance(None, eps(1, *range(1, 9)) + eps(2, 1)) == Progress(2, 1, "tracking")
