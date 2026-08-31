import pytest

from psynet.trial import _compile_nodes_from_directory, static_url_for
from psynet.utils import working_directory


class _FakeNode:
    def __init__(self, definition, participant_group, block):
        self.definition = definition
        self.participant_group = participant_group
        self.block = block


def test_static_url_for_maps_files_under_static(tmp_path):
    media = tmp_path / "static" / "stimuli" / "piano.mp3"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"x")

    with working_directory(tmp_path):
        assert static_url_for(media) == "/static/stimuli/piano.mp3"
        assert static_url_for("static/stimuli/piano.mp3") == "/static/stimuli/piano.mp3"


def test_static_url_for_rejects_files_outside_static(tmp_path):
    media = tmp_path / "data" / "piano.mp3"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"x")

    with working_directory(tmp_path), pytest.raises(ValueError, match="static"):
        static_url_for(media)


def test_compile_nodes_from_directory_uses_static_urls(tmp_path):
    media = tmp_path / "static" / "practice" / "group-a" / "block-1" / "tone.wav"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"RIFF")

    with working_directory(tmp_path):
        nodes = _compile_nodes_from_directory(
            "static/practice",
            ".wav",
            _FakeNode,
        )

    assert len(nodes) == 1
    node = nodes[0]
    assert node.participant_group == "group-a"
    assert node.block == "block-1"
    assert node.definition["name"] == "tone.wav"
    assert node.definition["prompt"] == "/static/practice/group-a/block-1/tone.wav"
    assert not hasattr(node, "assets") or getattr(node, "assets", None) in (
        None,
        {},
    )
