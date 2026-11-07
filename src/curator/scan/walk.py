"""Find video files under a folder (no parsing here)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from curator.model import FileInfo, Parsed, Skipped
from curator.scan.parse import parse_file

VIDEO_EXTENSIONS = frozenset(
    {".mkv", ".mp4", ".m4v", ".mov", ".avi", ".webm", ".ts", ".wmv", ".mpg", ".mpeg"}
)


def walk_videos(root: Path) -> Iterator[FileInfo]:
    """Yield every video file under root. Skips hidden files/folders and app bundles;
    never follows symlinks."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not d.endswith(".app")]
        for name in filenames:
            if name.startswith(".") or Path(name).suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                continue
            st = os.stat(path)
            yield FileInfo(path=path, name=name, size_bytes=st.st_size, mtime=int(st.st_mtime))


def scan_folder(root: Path) -> Iterator[Parsed | Skipped]:
    for info in walk_videos(root):
        yield parse_file(info)
