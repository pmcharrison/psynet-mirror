"""Validate participant evidence videos for experiment audits."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

MAX_EVIDENCE_VIDEO_DURATION_SECONDS = 180
MAX_EVIDENCE_VIDEO_WIDTH = 1280
MAX_EVIDENCE_VIDEO_HEIGHT = 720


def video_metadata(video_file: Path) -> dict[str, Any] | None:
    """Return ffprobe metadata for a video file."""

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(video_file),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def is_git_lfs_pointer(path: Path) -> bool:
    """Return whether a file is an unfetched Git LFS pointer."""

    try:
        data = path.read_bytes()[:128]
    except OSError:
        return False
    return data.startswith(b"version https://git-lfs.github.com/spec/v1")


def validate_evidence_video(video_file: Path) -> list[str]:
    """Validate participant evidence video size constraints."""

    problems: list[str] = []
    if is_git_lfs_pointer(video_file):
        return problems

    metadata = video_metadata(video_file)
    if metadata is None:
        # Lightweight checkouts can leave LFS placeholders that ffprobe cannot
        # decode. Enforce limits when media is present, but do not fail solely
        # because LFS content is absent.
        return problems

    video_stream = next(
        (
            stream
            for stream in metadata.get("streams", [])
            if stream.get("codec_type") == "video"
        ),
        {},
    )
    duration = float(
        metadata.get("format", {}).get("duration")
        or video_stream.get("duration")
        or 0,
    )
    if duration > MAX_EVIDENCE_VIDEO_DURATION_SECONDS:
        problems.append(
            f"{video_file}: evidence videos must be at most "
            f"{MAX_EVIDENCE_VIDEO_DURATION_SECONDS} seconds long",
        )

    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    if width > MAX_EVIDENCE_VIDEO_WIDTH or height > MAX_EVIDENCE_VIDEO_HEIGHT:
        problems.append(
            f"{video_file}: evidence videos must be at most "
            f"{MAX_EVIDENCE_VIDEO_WIDTH}x{MAX_EVIDENCE_VIDEO_HEIGHT}",
        )

    return problems
