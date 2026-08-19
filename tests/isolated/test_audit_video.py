from pathlib import Path
from unittest.mock import patch

from psynet.audit.video import (
    VideoProbeResult,
    is_git_lfs_pointer,
    validate_evidence_video,
)


def test_validate_evidence_video_skips_git_lfs_pointer(tmp_path: Path) -> None:
    video = tmp_path / "participant.mp4"
    video.write_bytes(
        b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 1\n",
    )

    assert validate_evidence_video(video) == []


def test_validate_evidence_video_fails_for_unreadable_file(tmp_path: Path) -> None:
    video = tmp_path / "participant.mp4"
    video.write_bytes(b"not a video")

    with patch(
        "psynet.audit.video.probe_video_metadata",
        return_value=VideoProbeResult(None, "invalid"),
    ):
        problems = validate_evidence_video(video)

    assert any("unable to read video metadata" in problem for problem in problems)


def test_validate_evidence_video_fails_when_ffprobe_missing(tmp_path: Path) -> None:
    video = tmp_path / "participant.mp4"
    video.write_bytes(b"video bytes")

    with patch(
        "psynet.audit.video.probe_video_metadata",
        return_value=VideoProbeResult(None, "unavailable"),
    ):
        problems = validate_evidence_video(video)

    assert any("ffprobe is required" in problem for problem in problems)


def test_validate_evidence_video_enforces_duration_limit(tmp_path: Path) -> None:
    video = tmp_path / "participant.mp4"
    video.write_bytes(b"video")

    metadata = {
        "format": {"duration": "200"},
        "streams": [{"codec_type": "video", "width": 640, "height": 480}],
    }
    with patch(
        "psynet.audit.video.probe_video_metadata",
        return_value=VideoProbeResult(metadata, None),
    ):
        problems = validate_evidence_video(video)

    assert any("at most 180 seconds" in problem for problem in problems)


def test_is_git_lfs_pointer_detects_pointer(tmp_path: Path) -> None:
    path = tmp_path / "participant.mp4"
    path.write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
    assert is_git_lfs_pointer(path) is True
