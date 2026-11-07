"""HTTP GET for JSON, and the TMDB key from the macOS Keychain. Never logs the key."""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

Fetch = Callable[[str], Any]  # url -> parsed JSON, None on 404; raises EnrichError otherwise

KEYCHAIN_SERVICE = "curator-tmdb"


class EnrichError(Exception):
    """A lookup failed (network down, rate limit, bad reply). Message never holds the URL."""


class KeyMissing(EnrichError):
    """No TMDB key in the Keychain."""


def http_fetch(url: str) -> Any:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Curator/0.1", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as reply:
            return json.load(reply)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        # `from None`: the original error carries the URL, and the URL carries the key.
        raise EnrichError(f"HTTP {err.code}") from None
    except (OSError, ValueError):
        raise EnrichError("network error") from None


def tmdb_key() -> str:
    try:
        done = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        raise KeyMissing("no TMDB key in the Keychain") from None
    key = done.stdout.strip()
    if not key:
        raise KeyMissing("empty TMDB key in the Keychain")
    return key
