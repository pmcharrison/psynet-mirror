import pytest

from psynet.dev import slack_announcement

SAMPLE_CHANGELOG = """# CHANGELOG

# [13.2.0](https://gitlab.com/PsyNetDev/PsyNet/-/releases/v13.2.0) Release - 2026-04-01

## Added

- Added a new demo experiment.

# [13.2.0rc0](https://gitlab.com/PsyNetDev/PsyNet/-/releases/v13.2.0rc0) Release candidate - 2026-03-20

## Fixed

- Fixed a participant recruitment bug.
"""


@pytest.fixture
def changelog(tmp_path, monkeypatch):
    changelog_path = tmp_path / "CHANGELOG.md"
    changelog_path.write_text(SAMPLE_CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(slack_announcement, "CHANGELOG_PATH", changelog_path)
    # Ensure `git show v<version>:CHANGELOG.md` fails so the file is used.
    monkeypatch.chdir(tmp_path)


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


def test_extract_changelog_section_returns_matching_section(changelog):
    section = slack_announcement.extract_changelog_section("13.2.0")
    assert "Added a new demo experiment." in section
    assert "recruitment bug" not in section

    rc_section = slack_announcement.extract_changelog_section("13.2.0rc0")
    assert "Fixed a participant recruitment bug." in rc_section


def test_extract_changelog_section_requires_exact_version(changelog):
    # "3.2.0" is a substring of "13.2.0" but must not match its heading.
    assert slack_announcement.extract_changelog_section("3.2.0") is None
    assert slack_announcement.extract_changelog_section("13.2.1") is None


def test_build_blocks_final_release(changelog):
    blocks, fallback = slack_announcement.build_blocks("13.2.0")
    texts = [block["text"]["text"] for block in blocks if block["type"] != "divider"]
    joined = "\n".join(texts)

    assert "PsyNet 13.2.0 is out" in texts[0]
    assert "13.2.0" in fallback
    # _concise strips the leading "Added " from changelog entries.
    assert "A new demo experiment" in joined
    assert "pip install --upgrade psynet" in joined
    # The {version} placeholder from the guidance file must be substituted.
    assert "{version}" not in joined
    assert "release candidate" not in joined.lower()


def test_build_blocks_release_candidate(changelog):
    blocks, _ = slack_announcement.build_blocks("13.2.0rc0")
    texts = [block["text"]["text"] for block in blocks if block["type"] != "divider"]
    joined = "\n".join(texts)

    assert "Release Candidate" in texts[0]
    assert "pip install psynet==13.2.0rc0" in joined
    assert "/rc/v13.2.0rc0/" in joined


def test_build_blocks_without_changelog_section_warns(changelog, capsys):
    blocks, _ = slack_announcement.build_blocks("13.9.9")
    assert "no CHANGELOG.md section found for 13.9.9" in capsys.readouterr().err
    # Announcement is still produced, just without the highlights block.
    assert any(block["type"] == "header" for block in blocks)


def test_concise_shortens_entries():
    assert (
        slack_announcement._concise(
            "Added a new `ChatRoom` element, including websocket support."
        )
        == "A new `ChatRoom` element"
    )
