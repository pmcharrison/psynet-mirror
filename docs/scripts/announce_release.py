#!/usr/bin/env python3
"""Announce a PsyNet release in the ``#psynet-support`` Slack channel.

Usage::

    python docs/scripts/announce_release.py 13.2.0               # final release
    python docs/scripts/announce_release.py 13.2.0rc0            # release candidate
    python docs/scripts/announce_release.py 13.2.0 --dry-run     # print, do not post
    python docs/scripts/announce_release.py 13.2.0 --dry-run-json  # raw Block Kit JSON

Requirements:

- The ``[slack]`` extra is installed (covered by the
  ``uv pip install -e '.[dev,slack]'`` line in the release prerequisites).
- ``SLACK_BOT_TOKEN`` is set in the environment to a bot token that has
  ``chat:write`` access to ``#psynet-support``.

The script chooses an RC-flavoured or final-flavoured message based on
whether the version contains a pre-release segment (``rc``/``a``/``b``).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CHANNEL = "psynet-support"
ROOT = Path(__file__).resolve().parents[2]
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
ANNOUNCEMENT_GUIDANCE_PATH = ROOT / "SLACK_ANNOUNCEMENT.md"

PRERELEASE_RE = re.compile(r"(rc|a|b)\d+$", re.IGNORECASE)
RELEASE_HEADING_RE = re.compile(r"^#{1,2} \[.*?\].*$", re.MULTILINE)
SECTION_HEADING_RE = re.compile(r"^#{2,3} (\w+)$", re.MULTILINE)


@dataclass(frozen=True)
class AnnouncementGuidance:
    stable_release_description: str
    experimenter_summary_intro: str
    stable_upgrade_instructions: str
    category_order: list[str]
    include_re: re.Pattern[str]
    exclude_re: re.Pattern[str]


def is_prerelease(version: str) -> bool:
    return bool(PRERELEASE_RE.search(version))


def extract_changelog_section(version: str) -> str | None:
    """Return the body of the CHANGELOG section for *version*, or None."""
    try:
        import subprocess

        changelog = subprocess.check_output(
            ["git", "show", f"v{version}:CHANGELOG.md"],
            cwd=ROOT,
            text=True,
        )
    except Exception:
        if not CHANGELOG_PATH.exists():
            return None
        changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

    headings = list(RELEASE_HEADING_RE.finditer(changelog))

    for i, match in enumerate(headings):
        if version in match.group(0):
            start = match.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(changelog)
            return changelog[start:end].strip()

    return None


def _concise(text: str) -> str:
    """Shorten a CHANGELOG entry to its essential point."""
    line = " ".join(text.split())
    line = re.sub(r"^(Added|Fixed) ", "", line)
    line = re.split(r"(?<=[.!;]) (?=[A-Z])", line, maxsplit=1)[0]
    line = re.sub(
        r",\s+(?:with|including|plus|so |causing |preventing |fixing ).*$", "", line
    )
    line = re.sub(r"\s*\([^)]*\)\s*$", "", line)
    line = re.sub(r"``([^`]+)``", r"`\1`", line)
    line = line.rstrip(".:; ")
    line = line[0].upper() + line[1:] if line else line
    return line


@lru_cache(maxsize=1)
def load_announcement_guidance() -> AnnouncementGuidance:
    """Read Slack summary guidance from ``SLACK_ANNOUNCEMENT.md``."""
    if not ANNOUNCEMENT_GUIDANCE_PATH.exists():
        raise FileNotFoundError(
            f"Missing announcement guidance: {ANNOUNCEMENT_GUIDANCE_PATH}"
        )

    markdown = ANNOUNCEMENT_GUIDANCE_PATH.read_text(encoding="utf-8")
    stable_release_description = _markdown_section_text(
        markdown, "Stable Release Description"
    )
    experimenter_summary_intro = _markdown_section_text(
        markdown, "Experimenter Summary Intro"
    )
    stable_upgrade_instructions = _markdown_section_message(
        markdown, "Stable Upgrade Instructions"
    )
    category_order = _markdown_section_items(markdown, "Category Order")
    include_patterns = _markdown_section_patterns(markdown, "Include Patterns")
    exclude_patterns = _markdown_section_patterns(markdown, "Exclude Patterns")

    if not include_patterns:
        raise ValueError("SLACK_ANNOUNCEMENT.md must define include patterns.")
    if not exclude_patterns:
        raise ValueError("SLACK_ANNOUNCEMENT.md must define exclude patterns.")
    if not stable_release_description:
        raise ValueError(
            "SLACK_ANNOUNCEMENT.md must define a stable release description."
        )
    if not experimenter_summary_intro:
        raise ValueError(
            "SLACK_ANNOUNCEMENT.md must define an experimenter summary intro."
        )
    if not stable_upgrade_instructions:
        raise ValueError(
            "SLACK_ANNOUNCEMENT.md must define stable upgrade instructions."
        )
    if not category_order:
        raise ValueError("SLACK_ANNOUNCEMENT.md must define a category order.")

    return AnnouncementGuidance(
        stable_release_description=stable_release_description,
        experimenter_summary_intro=experimenter_summary_intro,
        stable_upgrade_instructions=stable_upgrade_instructions,
        category_order=category_order,
        include_re=_compile_announcement_patterns(include_patterns),
        exclude_re=_compile_announcement_patterns(exclude_patterns),
    )


def _markdown_section_text(markdown: str, heading: str) -> str:
    section = _markdown_section(markdown, heading)
    lines = [
        line.strip()
        for line in section.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return " ".join(lines)


def _markdown_section_message(markdown: str, heading: str) -> str:
    section = _markdown_section(markdown, heading)
    lines = [
        line.rstrip()
        for line in section.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return "\n".join(lines)


def _markdown_section_patterns(markdown: str, heading: str) -> list[str]:
    section = _markdown_section(markdown, heading)
    patterns: list[str] = []
    for line in section.splitlines():
        match = re.match(r"^-\s+`(.+)`\s*$", line.strip())
        if match:
            patterns.append(match.group(1))
    return patterns


def _markdown_section_items(markdown: str, heading: str) -> list[str]:
    section = _markdown_section(markdown, heading)
    items: list[str] = []
    for line in section.splitlines():
        match = re.match(r"^-\s+(.+?)\s*$", line.strip())
        if match:
            items.append(match.group(1))
    return items


def _markdown_section(markdown: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(markdown)
    if not match:
        return ""

    next_heading = re.search(r"^##\s+", markdown[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(markdown)
    return markdown[match.end() : end].strip()


def _compile_announcement_patterns(patterns: list[str]) -> re.Pattern[str]:
    return re.compile(
        "|".join(f"(?:{pattern})" for pattern in patterns),
        re.IGNORECASE,
    )


def summarize_for_experimenters(section_body: str) -> str:
    """Condense a CHANGELOG section into experimenter-facing highlights."""
    guidance = load_announcement_guidance()
    categories: dict[str, list[str]] = {}
    current_category: str | None = None

    for line in section_body.splitlines():
        heading_match = SECTION_HEADING_RE.match(line)
        if heading_match:
            current_category = heading_match.group(1)
            continue

        if current_category and line.startswith("- "):
            entry = line[2:].strip()
            entry = re.sub(r"\s*\(author:.*?\)\.?", "", entry)
            if guidance.include_re.search(entry) and not guidance.exclude_re.search(
                entry
            ):
                categories.setdefault(current_category, []).append(entry)
        elif (
            current_category
            and line.startswith("  ")
            and categories.get(current_category)
        ):
            sub = line.strip()
            if sub.startswith("- "):
                sub = sub[2:].strip()
            if sub:
                sub = re.sub(r"\s*\(author:.*?\)\.?", "", sub)
                categories[current_category][-1] += " " + sub

    parts: list[str] = []
    for cat in guidance.category_order:
        entries = categories.get(cat, [])
        if not entries:
            continue
        parts.append(f"\n*{cat}*")
        for entry in entries:
            parts.append(f"• {_concise(entry)}")

    return "\n".join(parts).strip()


def build_blocks(version: str) -> tuple[list[dict], str]:
    """Return (blocks, fallback_text) for a Slack message."""
    guidance = load_announcement_guidance()
    release_url = f"https://gitlab.com/PsyNetDev/PsyNet/-/releases/v{version}"
    pypi_url = f"https://pypi.org/project/psynet/{version}/"

    if is_prerelease(version):
        final_version = PRERELEASE_RE.sub("", version)
        title = f":test_tube: PsyNet {version} — Release Candidate :test_tube:"
        subtitle = "A new release candidate is ready for testing!"
        docs_url = f"https://psynetdev.gitlab.io/PsyNet/rc/v{version}/"
        notice = (
            ":warning: *This is a release candidate.* "
            "It is not the latest release on PyPI; "
            f"opt in explicitly with `pip install psynet=={version}`. "
            "Please test against your studies and report any regressions "
            f"before the final `{final_version}` tag."
        )
        install = None
    else:
        title = f":tada: PsyNet {version} is out! :rocket:"
        subtitle = guidance.stable_release_description
        docs_url = "https://psynetdev.gitlab.io/PsyNet/"
        versioned_docs_url = f"https://psynetdev.gitlab.io/PsyNet/v{version}/"
        notice = None
        install = guidance.stable_upgrade_instructions.format(version=version)

    links = f"*PyPI*: {pypi_url}\n*Documentation*: {docs_url}"
    if not is_prerelease(version):
        links += f"\n*Versioned documentation*: {versioned_docs_url}"

    section = extract_changelog_section(version)
    summary = summarize_for_experimenters(section) if section else ""

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": title, "emoji": True},
        },
        _mrkdwn_block(f"_{subtitle}_"),
    ]

    if notice:
        blocks.append(_mrkdwn_block(notice))

    if summary:
        blocks.append({"type": "divider"})
        blocks.append(
            _mrkdwn_block(f"{guidance.experimenter_summary_intro}\n\n{summary}")
        )
        blocks.append(
            _mrkdwn_block(
                f"See the <{release_url}|full release notes> for all details."
            )
        )

    blocks.append({"type": "divider"})
    if install:
        blocks.append(_mrkdwn_block(install))
    blocks.append(_mrkdwn_block(links))

    fallback = f"{title} — {release_url}"
    return blocks, fallback


def _mrkdwn_block(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="e.g. 13.2.0 or 13.2.0rc0 (no leading 'v')")
    parser.add_argument(
        "--channel",
        default=CHANNEL,
        help=f"Slack channel name (default: {CHANNEL})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the message instead of posting",
    )
    parser.add_argument(
        "--dry-run-json",
        action="store_true",
        help=(
            "Print the raw Block Kit JSON payload (paste into "
            "https://app.slack.com/block-kit-builder to preview rendering)"
        ),
    )
    args = parser.parse_args()

    blocks, fallback = build_blocks(args.version)

    if args.dry_run_json:
        print(json.dumps({"blocks": blocks}, indent=2))
        return 0

    if args.dry_run:
        print(f"# Would post to #{args.channel}:\n")
        for block in blocks:
            if block["type"] == "divider":
                print("---")
            elif block["type"] == "header":
                print(f"# {block['text']['text']}")
                print()
            else:
                print(block["text"]["text"])
                print()
        return 0

    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
    except ImportError:
        print(
            "slack_sdk is not installed. Install the [slack] extra:\n"
            "    uv pip install -e '.[slack]'",
            file=sys.stderr,
        )
        return 2

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("SLACK_BOT_TOKEN is not set.", file=sys.stderr)
        return 2

    client = WebClient(token=token)
    try:
        resp = client.chat_postMessage(
            channel=args.channel,
            text=fallback,
            blocks=blocks,
        )
    except SlackApiError as e:
        print(f"Slack error: {e.response['error']}", file=sys.stderr)
        return 1

    print(f"Posted to #{args.channel} (ts={resp['ts']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
