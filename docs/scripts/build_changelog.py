#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRAGMENTS_DIR = ROOT / "changelog.d"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
MAX_SLUG_LENGTH = 60

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
SECTION_TITLE_TO_KEY = {title: key for key, title in SECTION_ORDER}
SECTION_PATTERN = "|".join(key for key, _title in SECTION_ORDER)

FILENAME_RE = re.compile(
    rf"^(?P<id>[A-Za-z0-9][A-Za-z0-9_-]*)\.(?P<section>{SECTION_PATTERN})\.md$"
)


def fragment_sort_key(name: str) -> tuple:
    """Sort all-numeric IDs first (numerically), then slug IDs (lexicographically)."""
    match = FILENAME_RE.match(name)
    if match is None:
        return (2, name)
    fragment_id = match["id"]
    if fragment_id.isdigit():
        return (0, int(fragment_id), name)
    return (1, fragment_id, name)


UNRELEASED_RE = re.compile(r"(?ms)^## Unreleased\n.*?(?=^## |\Z)")
RELEASE_HEADING_RE = re.compile(r"^## \[(?P<version>[^\]]+)\].*$", re.MULTILINE)
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

    paths.sort(key=lambda p: fragment_sort_key(p.name))
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


def parse_sectioned_entries(body: str) -> dict[str, list[str]]:
    entries: dict[str, list[str]] = defaultdict(list)
    matches = list(SECTION_HEADER_RE.finditer(body))

    for index, match in enumerate(matches):
        title = match.group("title").strip()
        if title not in SECTION_TITLE_TO_KEY:
            raise ValueError(f"Unsupported changelog subsection: {title}")

        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        section_body = body[start:end].strip()
        if section_body:
            entries[SECTION_TITLE_TO_KEY[title]].extend(
                parse_section_entries(section_body)
            )

    return entries


def add_entries(
    target: dict[str, list[str]], source: dict[str, list[str]]
) -> dict[str, list[str]]:
    for key, _title in SECTION_ORDER:
        target[key].extend(source.get(key, []))
    return target


def get_unreleased_section(changelog: str) -> re.Match[str]:
    match = UNRELEASED_RE.search(changelog)
    if not match:
        raise ValueError("Could not find '## Unreleased' section in CHANGELOG.md")
    return match


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
    if "alpha" in lowered or re.search(r"(?<=[0-9._-])a\d+\b", lowered):
        return "Alpha"
    if "beta" in lowered or re.search(r"(?<=[0-9._-])b\d+\b", lowered):
        return "Beta"
    return "Release"


def matching_release_candidate_sections(
    changelog: str, version: str
) -> list[tuple[int, int, int, dict[str, list[str]]]]:
    sections: list[tuple[int, int, int, dict[str, list[str]]]] = []
    headings = list(RELEASE_HEADING_RE.finditer(changelog))
    rc_version_re = re.compile(rf"^{re.escape(version)}rc(?P<number>\d+)$")

    for index, heading in enumerate(headings):
        match = rc_version_re.match(heading.group("version"))
        if match is None:
            continue

        body_start = heading.end()
        end = (
            headings[index + 1].start() if index + 1 < len(headings) else len(changelog)
        )
        sections.append(
            (
                int(match.group("number")),
                heading.start(),
                end,
                parse_sectioned_entries(changelog[body_start:end]),
            )
        )

    return sorted(sections, key=lambda item: item[0])


def remove_spans(text: str, spans: list[tuple[int, int]]) -> str:
    for start, end in sorted(spans, reverse=True):
        prefix = text[:start].rstrip("\n")
        suffix = text[end:].lstrip("\n")
        text = f"{prefix}\n\n{suffix}" if suffix else f"{prefix}\n"
    return text


def render_release_heading(version: str, date: str) -> str:
    label = classify_release(version)
    return (
        f"## [{version}]"
        f"(https://gitlab.com/PsyNetDev/PsyNet/-/releases/v{version}) {label} - {date}\n"
    )


def build_release_section(
    version: str, date: str, entries: dict[str, list[str]]
) -> str:
    parts = [render_release_heading(version, date).rstrip()]
    sections = render_sections(entries).rstrip()
    if sections:
        parts.extend(["", sections])
    parts.append("")
    return "\n".join(parts)


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


def release_command(version: str, date: str) -> int:
    if classify_release(version) == "Alpha":
        raise ValueError(
            "Alpha versions do not get changelog release sections. Keep fragments "
            "in changelog.d until the first release candidate or stable release."
        )

    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
    fragments = load_fragments()
    fragment_entries = group_entries(fragments)
    entries: dict[str, list[str]] = defaultdict(list)
    remove_release_candidate_spans: list[tuple[int, int]] = []
    if classify_release(version) == "Release":
        for _rc_number, start, end, rc_entries in matching_release_candidate_sections(
            changelog, version
        ):
            add_entries(entries, rc_entries)
            remove_release_candidate_spans.append((start, end))
    add_entries(entries, fragment_entries)

    if not any(entries.values()):
        raise ValueError("No changelog fragments or matching release candidates found.")

    changelog = remove_spans(changelog, remove_release_candidate_spans)
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


def slugify(text: str) -> str:
    """Convert free-form text into a kebab-case ASCII slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if not text:
        raise ValueError(
            "Description must contain at least one alphanumeric character."
        )
    if len(text) > MAX_SLUG_LENGTH:
        text = text[:MAX_SLUG_LENGTH].rstrip("-")
    return text


def new_command(category: str, description: str) -> int:
    if category not in SECTION_KEYS:
        raise ValueError(
            f"Unknown category {category!r}. Must be one of: "
            + ", ".join(key for key, _title in SECTION_ORDER)
        )

    slug = slugify(description)
    date = time.strftime("%Y%m%d")
    FRAGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    path = FRAGMENTS_DIR / f"{date}-{slug}.{category}.md"
    if path.exists():
        raise ValueError(
            f"Fragment {path} already exists. "
            "Use a more specific description (the slug must be unique within "
            "the day) or rename the existing fragment."
        )

    path.write_text(f"{description.strip()} (author: [Your Name])\n", encoding="utf-8")
    print(path)
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
        "--new",
        nargs=2,
        metavar=("CATEGORY", "DESCRIPTION"),
        help=(
            "Create a new fragment file with a date-prefixed slug filename "
            "(e.g. --new fixed 'fix Selenium flake')."
        ),
    )
    parser.add_argument(
        "--release",
        nargs=2,
        metavar=("VERSION", "DATE"),
        help="Create a release section from current fragments and clear Unreleased.",
    )
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        modes = sum(1 for x in (args.new, args.release) if x)
        if modes > 1:
            raise ValueError("Use only one of --new, --release.")

        if args.new:
            category, description = args.new
            return new_command(category, description)

        if not CHANGELOG_PATH.exists():
            print(f"Missing {CHANGELOG_PATH}", file=sys.stderr)
            return 1

        if args.release:
            version, date = args.release
            return release_command(version, date)
        return build_command()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
