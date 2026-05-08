#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRAGMENTS_DIR = ROOT / "changelog.d"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
MIGRATION_START_ID = 9001

SECTION_ORDER = [
    ("breaking", "Breaking Changes"),
    ("added", "Added"),
    ("changed", "Changed"),
    ("deprecated", "Deprecated"),
    ("removed", "Removed"),
    ("fixed", "Fixed"),
    ("updated", "Updated"),
    ("documentation", "Documentation"),
]
SECTION_KEYS = {key for key, _title in SECTION_ORDER}
HEADER_TO_SECTION = {title: key for key, title in SECTION_ORDER}
SECTION_PATTERN = "|".join(key for key, _title in SECTION_ORDER)

FILENAME_RE = re.compile(rf"^(?P<mr>\d+)\.(?P<section>{SECTION_PATTERN})\.md$")
UNRELEASED_RE = re.compile(r"(?ms)^## Unreleased\n.*?(?=^## |\Z)")
MANAGED_BLOCK_RE = re.compile(
    r"(?ms)^<!-- changelog\.d:start -->\n.*?^<!-- changelog\.d:end -->\n?"
)
SECTION_HEADER_RE = re.compile(r"^### (?P<title>[A-Za-z][A-Za-z ]*?)\n", re.MULTILINE)


@dataclass(frozen=True)
class Fragment:
    path: Path
    section: str
    entry: str


def format_entry(text: str) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    if not lines:
        raise ValueError("Fragment is empty.")

    formatted = [f"- {lines[0]}"]
    formatted.extend(f"  {line}" if line else "" for line in lines[1:])
    return "\n".join(formatted)


def list_fragment_paths() -> list[Path]:
    if not FRAGMENTS_DIR.exists():
        return []

    paths: list[Path] = []
    invalid_files: list[str] = []

    for path in FRAGMENTS_DIR.iterdir():
        if not path.is_file() or path.name == "README.md" or path.name.startswith("."):
            continue

        if not FILENAME_RE.match(path.name):
            invalid_files.append(path.name)
            continue

        paths.append(path)

    if invalid_files:
        raise ValueError(
            "Invalid changelog fragment filename(s): "
            + ", ".join(sorted(invalid_files))
            + f". Expected <id>.({SECTION_PATTERN}).md"
        )

    paths.sort(key=lambda p: (int(FILENAME_RE.match(p.name)["mr"]), p.name))
    return paths


def load_fragments() -> list[Fragment]:
    fragments: list[Fragment] = []

    for path in list_fragment_paths():
        match = FILENAME_RE.match(path.name)
        assert match is not None

        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"{path} is empty.")

        fragments.append(
            Fragment(
                path=path,
                section=match.group("section"),
                entry=format_entry(content),
            )
        )

    return fragments


def group_entries(fragments: list[Fragment]) -> dict[str, list[str]]:
    entries: dict[str, list[str]] = defaultdict(list)
    for fragment in fragments:
        entries[fragment.section].append(fragment.entry)
    return entries


def render_sections(entries: dict[str, list[str]]) -> str:
    parts: list[str] = []

    for key, title in SECTION_ORDER:
        if not entries.get(key):
            continue
        parts.extend([f"### {title}", "", "\n".join(entries[key]), ""])

    if not parts:
        return ""
    return "\n".join(parts).rstrip() + "\n"


def render_managed_block(entries: dict[str, list[str]]) -> str:
    sections = render_sections(entries)
    body = [
        "<!-- changelog.d:start -->",
        "<!-- Generated from changelog.d fragments by docs/scripts/build_changelog.py -->",
    ]
    if sections:
        body.extend(["", sections.rstrip(), ""])
    body.extend(["<!-- changelog.d:end -->", ""])
    return "\n".join(body)


def parse_section_entries(body: str) -> list[str]:
    entries: list[list[str]] = []

    for line in body.splitlines():
        if line.startswith("- "):
            entries.append([line[2:]])
            continue

        if not entries:
            if line.strip():
                raise ValueError(
                    f"Unexpected content before first changelog bullet: {line!r}"
                )
            continue

        if line.startswith("  "):
            entries[-1].append(line[2:])
        elif not line.strip():
            entries[-1].append("")
        else:
            raise ValueError(f"Unexpected changelog line format: {line!r}")

    return [
        "\n".join(entry).strip()
        for entry in entries
        if any(part.strip() for part in entry)
    ]


def get_unreleased_section(changelog: str) -> re.Match[str]:
    match = UNRELEASED_RE.search(changelog)
    if not match:
        raise ValueError("Could not find '## Unreleased' section in CHANGELOG.md")
    return match


def get_unreleased_unmanaged_body(changelog: str) -> str:
    unreleased = get_unreleased_section(changelog).group(0)
    return (
        MANAGED_BLOCK_RE.sub("", unreleased).replace("## Unreleased\n", "", 1).strip()
    )


def parse_unreleased_entries(changelog: str) -> dict[str, list[str]]:
    body = get_unreleased_unmanaged_body(changelog)
    if not body:
        return defaultdict(list)

    matches = list(SECTION_HEADER_RE.finditer(body))
    if not matches:
        raise ValueError(
            "Could not find changelog subsection headings under '## Unreleased'"
        )

    entries: dict[str, list[str]] = defaultdict(list)
    for index, match in enumerate(matches):
        title = match.group("title").strip()
        if title not in HEADER_TO_SECTION:
            raise ValueError(
                f"Unsupported changelog subsection under Unreleased: {title}"
            )

        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        section_body = body[start:end].strip()
        if section_body:
            entries[HEADER_TO_SECTION[title]].extend(
                parse_section_entries(section_body)
            )

    return entries


def next_migration_id() -> int:
    max_id = MIGRATION_START_ID - 1
    for path in list_fragment_paths():
        match = FILENAME_RE.match(path.name)
        assert match is not None
        max_id = max(max_id, int(match.group("mr")))
    return max_id + 1


def write_migrated_fragments(entries: dict[str, list[str]]) -> int:
    FRAGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    existing = list_fragment_paths()
    if existing:
        raise ValueError(
            "Refusing to migrate unreleased changelog entries because changelog.d already "
            "contains fragment files."
        )

    next_id = next_migration_id()
    written = 0

    for key, _title in SECTION_ORDER:
        for entry in entries.get(key, []):
            path = FRAGMENTS_DIR / f"{next_id}.{key}.md"
            path.write_text(entry + "\n", encoding="utf-8")
            next_id += 1
            written += 1

    return written


def replace_unreleased_with_managed_block(changelog: str, managed_block: str) -> str:
    match = get_unreleased_section(changelog)
    replacement = f"## Unreleased\n\n{managed_block}\n"
    return changelog[: match.start()] + replacement + changelog[match.end() :]


def rebuild_unreleased(changelog: str, entries: dict[str, list[str]]) -> str:
    return replace_unreleased_with_managed_block(
        changelog, render_managed_block(entries)
    )


def classify_release(version: str) -> str:
    lowered = version.lower()
    if "rc" in lowered:
        return "Release candidate"
    if "alpha" in lowered or re.search(r"\ba\d+\b", lowered):
        return "Alpha"
    if "beta" in lowered or re.search(r"\bb\d+\b", lowered):
        return "Beta"
    return "Release"


def render_release_heading(version: str, date: str) -> str:
    label = classify_release(version)
    return (
        f"## [{version}]"
        f"(https://gitlab.com/PsyNetDev/PsyNet/-/releases/v{version}) {label} - {date}\n"
    )


def build_release_section(
    version: str, date: str, entries: dict[str, list[str]]
) -> str:
    return "\n".join(
        [
            render_release_heading(version, date).rstrip(),
            "",
            render_sections(entries).rstrip(),
            "",
        ]
    )


def insert_release_section(changelog: str, release_section: str) -> str:
    match = get_unreleased_section(changelog)
    insertion_point = match.end()
    prefix = changelog[:insertion_point].rstrip("\n")
    suffix = changelog[insertion_point:].lstrip("\n")
    section = release_section.strip()
    return f"{prefix}\n\n{section}\n\n{suffix}"


def build_command() -> int:
    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
    fragments = load_fragments()
    entries = group_entries(fragments)
    updated = rebuild_unreleased(changelog, entries)
    CHANGELOG_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated {CHANGELOG_PATH} from fragments in {FRAGMENTS_DIR}")
    return 0


def migrate_command() -> int:
    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
    entries = parse_unreleased_entries(changelog)
    written = write_migrated_fragments(entries)
    updated = rebuild_unreleased(changelog, entries)
    CHANGELOG_PATH.write_text(updated, encoding="utf-8")
    print(
        f"Migrated {written} changelog entries into {FRAGMENTS_DIR} and updated "
        f"{CHANGELOG_PATH}"
    )
    return 0


def release_command(version: str, date: str) -> int:
    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
    fragments = load_fragments()
    if not fragments:
        raise ValueError("No changelog fragments found to release.")

    entries = group_entries(fragments)
    rebuilt = rebuild_unreleased(changelog, defaultdict(list))
    release_section = build_release_section(version, date, entries)
    updated = insert_release_section(rebuilt, release_section)
    CHANGELOG_PATH.write_text(updated, encoding="utf-8")

    for fragment in fragments:
        fragment.path.unlink()

    print(
        f"Released {len(fragments)} changelog fragments into {CHANGELOG_PATH} as "
        f"{version} and cleared {FRAGMENTS_DIR}"
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build and manage PsyNet changelog fragments. Contributors commit "
            "only fragments in their MRs (never a regenerated CHANGELOG.md); "
            "the rendered Unreleased block is refreshed by maintainers at "
            "release time via --release."
        )
    )
    parser.add_argument(
        "--migrate-unreleased",
        action="store_true",
        help="Migrate the current manual Unreleased section into fragment files.",
    )
    parser.add_argument(
        "--release",
        nargs=2,
        metavar=("VERSION", "DATE"),
        help="Create a release section from current fragments and clear Unreleased.",
    )
    return parser.parse_args()


def main() -> int:
    if not CHANGELOG_PATH.exists():
        print(f"Missing {CHANGELOG_PATH}", file=sys.stderr)
        return 1

    try:
        args = parse_args()
        if args.migrate_unreleased and args.release:
            raise ValueError("Use either --migrate-unreleased or --release, not both.")
        if args.migrate_unreleased:
            return migrate_command()
        if args.release:
            version, date = args.release
            return release_command(version, date)
        return build_command()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
