import importlib.util
import runpy
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "build_changelog.py"
BASE_CHANGELOG = """# CHANGELOG

## Unreleased

## [13.1.1](url) Release - 2026-02-18
"""


@pytest.fixture
def build_changelog(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("build_changelog_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    fragments_dir = tmp_path / "changelog.d"
    fragments_dir.mkdir()
    changelog_path = tmp_path / "CHANGELOG.md"
    changelog_path.write_text(BASE_CHANGELOG, encoding="utf-8")

    monkeypatch.setattr(module, "FRAGMENTS_DIR", fragments_dir)
    monkeypatch.setattr(module, "CHANGELOG_PATH", changelog_path)
    return module


def read_changelog(build_changelog):
    return build_changelog.CHANGELOG_PATH.read_text(encoding="utf-8")


def test_root_points_to_repository_root(build_changelog):
    assert build_changelog.ROOT == Path(__file__).parents[2]


def test_build_command_renders_fragments_without_consuming_them(build_changelog):
    added = build_changelog.FRAGMENTS_DIR / "10.added.md"
    fixed = build_changelog.FRAGMENTS_DIR / "2.fixed.md"
    added.write_text("Added alpha\n", encoding="utf-8")
    fixed.write_text("Fixed beta\n", encoding="utf-8")

    assert build_changelog.build_command() == 0

    rendered = read_changelog(build_changelog)
    assert "### Added\n\n- Added alpha" in rendered
    assert "### Fixed\n\n- Fixed beta" in rendered
    assert rendered.index("Added alpha") < rendered.index("Fixed beta")
    assert added.exists()
    assert fixed.exists()


def test_new_command_creates_date_prefixed_slug_and_detects_collisions(
    build_changelog, monkeypatch
):
    monkeypatch.setattr(build_changelog.time, "strftime", lambda _format: "20260516")

    assert build_changelog.new_command("fixed", "Fix Selenium flake!") == 0
    fragment = build_changelog.FRAGMENTS_DIR / "20260516-fix-selenium-flake.fixed.md"
    assert fragment.read_text(encoding="utf-8") == (
        "Fix Selenium flake! (author: [Your Name])\n"
    )

    with pytest.raises(ValueError, match="already exists"):
        build_changelog.new_command("fixed", "Fix Selenium flake!")


def test_alpha_release_is_rejected_and_keeps_fragments(build_changelog):
    fragment = build_changelog.FRAGMENTS_DIR / "20260516-keep-until-rc.fixed.md"
    fragment.write_text("Fixed later thing\n", encoding="utf-8")
    before = read_changelog(build_changelog)

    with pytest.raises(ValueError, match="Alpha versions do not get changelog"):
        build_changelog.release_command("13.2.0a0", "2026-05-16")

    assert read_changelog(build_changelog) == before
    assert fragment.exists()


def test_release_candidate_consumes_fragments_and_keeps_unreleased_block(
    build_changelog,
):
    fragment = build_changelog.FRAGMENTS_DIR / "20260516-rc-fragment.fixed.md"
    fragment.write_text("RC fixed entry\n", encoding="utf-8")

    assert build_changelog.release_command("13.2.0rc1", "2026-05-16") == 0

    text = read_changelog(build_changelog)
    assert text.startswith("# CHANGELOG\n\n## Unreleased\n\n## [13.2.0rc1]")
    assert "Release candidate - 2026-05-16" in text
    assert "- RC fixed entry" in text
    assert not fragment.exists()


def test_stable_release_consumes_prerelease_sections_and_remaining_fragments(
    build_changelog,
):
    build_changelog.CHANGELOG_PATH.write_text(
        """# CHANGELOG

## Unreleased

## [13.2.0rc1](url) Release candidate - 2026-05-07

### Changed

- RC1 changed entry

### Fixed

- RC1 fixed entry

## [13.2.0rc0](url) Release candidate - 2026-04-27

### Added

- RC0 added entry

### Fixed

- RC0 fixed entry

## [13.2.0b0](url) Beta - 2026-04-20

### Added

- Beta0 added entry

## [13.1.1](url) Release - 2026-02-18
""",
        encoding="utf-8",
    )
    fragment = build_changelog.FRAGMENTS_DIR / "20260516-final-leftover.fixed.md"
    fragment.write_text("Final leftover fixed entry\n", encoding="utf-8")

    assert build_changelog.release_command("13.2.0", "2026-05-16") == 0

    text = read_changelog(build_changelog)
    assert text.startswith("# CHANGELOG\n\n## [13.2.0]")
    assert "## Unreleased" not in text
    assert "## [13.2.0b0]" not in text
    assert "## [13.2.0rc1]" not in text
    assert "## [13.2.0rc0]" not in text
    assert "## [13.1.1]" in text

    final_section = text.split("## [13.2.0]", 1)[1].split("## [13.1.1]", 1)[0]
    assert "Beta0 added entry" in final_section
    assert "RC0 added entry" in final_section
    assert (
        final_section.index("Beta0 added entry")
        < final_section.index("RC0 fixed entry")
        < final_section.index("RC1 fixed entry")
        < final_section.index("Final leftover fixed entry")
    )
    assert not fragment.exists()


def test_stable_release_requires_fragments_or_matching_prerelease_sections(
    build_changelog,
):
    with pytest.raises(
        ValueError, match="No changelog fragments or matching prerelease sections found"
    ):
        build_changelog.release_command("13.2.0", "2026-05-16")


def test_fragment_listing_edge_cases(build_changelog, monkeypatch, tmp_path):
    assert build_changelog.fragment_sort_key("not-a-fragment") == (2, "not-a-fragment")

    missing_dir = tmp_path / "missing"
    monkeypatch.setattr(build_changelog, "FRAGMENTS_DIR", missing_dir)
    assert build_changelog.list_fragment_paths() == []

    fragments_dir = tmp_path / "fragments"
    fragments_dir.mkdir()
    monkeypatch.setattr(build_changelog, "FRAGMENTS_DIR", fragments_dir)
    (fragments_dir / "README.md").write_text("docs\n", encoding="utf-8")
    (fragments_dir / ".ignored.md").write_text("hidden\n", encoding="utf-8")
    (fragments_dir / "subdir").mkdir()
    valid = fragments_dir / "1.fixed.md"
    valid.write_text("Fixed bug\n", encoding="utf-8")
    assert build_changelog.list_fragment_paths() == [valid]

    (fragments_dir / "bad.fragment").write_text("bad\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid changelog fragment filename"):
        build_changelog.list_fragment_paths()


def test_empty_fragment_and_empty_entry_errors(build_changelog):
    with pytest.raises(ValueError, match="Fragment is empty"):
        build_changelog.format_entry("")

    empty = build_changelog.FRAGMENTS_DIR / "20260516-empty.fixed.md"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="is empty"):
        build_changelog.load_fragments()


def test_section_entry_parsing_edge_cases(build_changelog):
    assert build_changelog.parse_section_entries(
        "\n- First line\n  continuation\n\n- Second line\n"
    ) == ["First line\ncontinuation", "Second line"]

    with pytest.raises(ValueError, match="Unexpected content before first"):
        build_changelog.parse_section_entries("not a bullet")

    with pytest.raises(ValueError, match="Unexpected changelog line format"):
        build_changelog.parse_section_entries("- First\nbad continuation")

    with pytest.raises(ValueError, match="Unsupported changelog subsection"):
        build_changelog.parse_sectioned_entries("### Security\n\n- Secret fix\n")


def test_changelog_section_helpers_raise_for_missing_unreleased(build_changelog):
    changelog = "# CHANGELOG\n\n## [1.0.0](url) Release - 2026-01-01\n"
    with pytest.raises(ValueError, match="Could not find '## Unreleased'"):
        build_changelog.get_unreleased_section(changelog)


def test_release_labels_and_insertion_without_existing_release(build_changelog):
    assert build_changelog.classify_release("13.2.0b1") == "Beta"

    changelog = "# CHANGELOG\n\n## Unreleased\n\n"
    inserted = build_changelog.insert_release_section(
        changelog,
        build_changelog.build_release_section(
            "13.2.0b1", "2026-05-16", {"fixed": ["- Fixed beta"]}
        ),
    )
    assert inserted.endswith("### Fixed\n\n- Fixed beta\n\n")


def test_slugify_and_new_command_validation(build_changelog):
    with pytest.raises(ValueError, match="at least one alphanumeric"):
        build_changelog.slugify("!!!")

    long_slug = build_changelog.slugify("a" * 80)
    assert long_slug == "a" * build_changelog.MAX_SLUG_LENGTH

    with pytest.raises(ValueError, match="Unknown category"):
        build_changelog.new_command("security", "Fix issue")


def test_main_dispatches_to_modes_and_errors(build_changelog, monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["build_changelog.py", "--new", "fixed", "CLI fix"]
    )
    assert build_changelog.main() == 0
    assert any(build_changelog.FRAGMENTS_DIR.glob("*-cli-fix.fixed.md"))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_changelog.py",
            "--new",
            "fixed",
            "x",
            "--release",
            "13.2.0",
            "2026-05-16",
        ],
    )
    assert build_changelog.main() == 1
    assert "Use only one of" in capsys.readouterr().err

    build_changelog.CHANGELOG_PATH.unlink()
    monkeypatch.setattr(sys, "argv", ["build_changelog.py"])
    assert build_changelog.main() == 1
    assert "Missing" in capsys.readouterr().err


def test_main_dispatches_to_release(build_changelog, monkeypatch):
    fragment = build_changelog.FRAGMENTS_DIR / "20260516-cli-release.fixed.md"
    fragment.write_text("CLI release fix\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_changelog.py", "--release", "13.2.0rc1", "2026-05-16"],
    )

    assert build_changelog.main() == 0
    assert "## [13.2.0rc1]" in read_changelog(build_changelog)
    assert not fragment.exists()


def test_main_defaults_to_build_command(build_changelog, monkeypatch):
    fragment = build_changelog.FRAGMENTS_DIR / "20260516-default-build.fixed.md"
    fragment.write_text("Default build fix\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["build_changelog.py"])

    assert build_changelog.main() == 0
    assert "Default build fix" in read_changelog(build_changelog)
    assert fragment.exists()


def test_module_main_help_path(monkeypatch):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), "--help"])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")
    assert exc_info.value.code == 0
