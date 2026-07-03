import pytest

from psynet.dev import slack_announcement

SAMPLE_SUMMARY = """*Added*
• A new demo experiment

*Fixed*
• A participant recruitment bug
"""


@pytest.mark.parametrize(
    "version,expected",
    [
        ("13.2.0", False),
        ("13.2.0rc0", True),
        ("13.2.0a1", True),
        ("13.2.0b2", True),
    ],
)
def test_is_prerelease(version, expected):
    assert slack_announcement.is_prerelease(version) is expected


def test_build_blocks_final_release():
    blocks, fallback = slack_announcement.build_blocks("13.2.0", summary=SAMPLE_SUMMARY)
    texts = [block["text"]["text"] for block in blocks if block["type"] != "divider"]
    joined = "\n".join(texts)

    assert "PsyNet 13.2.0 is out" in texts[0]
    assert "13.2.0" in fallback
    assert "A new demo experiment" in joined
    assert "pip install --upgrade psynet" in joined
    # The {version} placeholder from the guidance file must be substituted.
    assert "{version}" not in joined
    assert "release candidate" not in joined.lower()


def test_build_blocks_release_candidate():
    blocks, _ = slack_announcement.build_blocks("13.2.0rc1", summary=SAMPLE_SUMMARY)
    texts = [block["text"]["text"] for block in blocks if block["type"] != "divider"]
    joined = "\n".join(texts)

    assert "Release Candidate" in texts[0]
    assert "pip install psynet==13.2.0rc1" in joined
    assert "/rc/v13.2.0rc1/" in joined
    # RCs are tag-only on GitLab; release notes link to the CHANGELOG at the tag.
    assert "/-/blob/v13.2.0rc1/CHANGELOG.md" in joined


def test_build_blocks_without_summary_omits_highlights():
    blocks, _ = slack_announcement.build_blocks("13.2.0")
    joined = "\n".join(
        block["text"]["text"] for block in blocks if block["type"] != "divider"
    )
    assert "key changes relevant for experimenters" not in joined
    assert any(block["type"] == "header" for block in blocks)


def test_announce_command_rejects_missing_summary_file(tmp_path):
    with pytest.raises(ValueError, match="Summary file not found"):
        slack_announcement.announce_command(
            "13.2.0",
            summary_file=str(tmp_path / "nope.md"),
            dry_run=True,
        )


def test_announce_command_rejects_empty_summary_file(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("  \n", encoding="utf-8")
    with pytest.raises(ValueError, match="Summary file is empty"):
        slack_announcement.announce_command(
            "13.2.0",
            summary_file=str(empty),
            dry_run=True,
        )


def test_announce_command_dry_run_uses_summary_file(tmp_path, capsys):
    summary = tmp_path / "highlights.md"
    summary.write_text(SAMPLE_SUMMARY, encoding="utf-8")
    slack_announcement.announce_command(
        "13.2.0",
        summary_file=str(summary),
        dry_run=True,
    )
    out = capsys.readouterr().out
    assert "A new demo experiment" in out
    assert "Would post to #psynet-support" in out


def test_split_mrkdwn_short_text_is_single_chunk():
    assert slack_announcement._split_mrkdwn("hello\nworld") == ["hello\nworld"]


def test_split_mrkdwn_splits_on_line_boundaries_below_limit():
    lines = [f"• entry {i} " + "x" * 200 for i in range(30)]
    chunks = slack_announcement._split_mrkdwn("\n".join(lines))
    assert len(chunks) > 1
    assert all(len(chunk) <= slack_announcement.SECTION_TEXT_LIMIT for chunk in chunks)
    assert "\n".join(chunks).split("\n") == lines
