"""Post PsyNet release announcements to Slack (`psynet dev release announce`).

This module builds the release announcement message and posts it to the
``#psynet-support`` Slack channel. Like the other `psynet dev` modules it
only functions from a PsyNet source checkout: it reads ``CHANGELOG.md`` from
the current working directory. The sibling ``slack_announcement.md`` file is
runtime configuration (summary intro, upgrade instructions, and
include/exclude patterns for condensing changelog entries), so editing the
announcement style should not require code changes.

Posting requires the ``[slack]`` extra and a ``SLACK_BOT_TOKEN`` environment
variable with ``chat:write`` access to the target channel. The message
flavour (release candidate vs. final) is auto-detected from the version
string.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_CHANNEL = "psynet-support"
CHANGELOG_PATH = Path("CHANGELOG.md")
ANNOUNCEMENT_GUIDANCE_PATH = Path(__file__).with_suffix(".md")

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
    """Return True if *version* has a pre-release segment (rc/a/b)."""
    return bool(PRERELEASE_RE.search(version))


def extract_changelog_section(version: str) -> str | None:
    """Return the body of the CHANGELOG section for *version*, or None."""
    try:
        changelog = subprocess.check_output(
            ["git", "show", f"v{version}:CHANGELOG.md"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, OSError):
        if not CHANGELOG_PATH.exists():
            return None
        changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

    headings = list(RELEASE_HEADING_RE.finditer(changelog))

    for i, match in enumerate(headings):
        if f"[{version}]" in match.group(0):
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
    """Read Slack summary guidance from ``slack_announcement.md``."""
    if not ANNOUNCEMENT_GUIDANCE_PATH.exists():
        raise ValueError(
            f"Missing announcement guidance: {ANNOUNCEMENT_GUIDANCE_PATH.resolve()}. "
            "Run from a PsyNet source checkout."
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
        raise ValueError("slack_announcement.md must define include patterns.")
    if not exclude_patterns:
        raise ValueError("slack_announcement.md must define exclude patterns.")
    if not stable_release_description:
        raise ValueError(
            "slack_announcement.md must define a stable release description."
        )
    if not experimenter_summary_intro:
        raise ValueError(
            "slack_announcement.md must define an experimenter summary intro."
        )
    if not stable_upgrade_instructions:
        raise ValueError(
            "slack_announcement.md must define stable upgrade instructions."
        )
    if not category_order:
        raise ValueError("slack_announcement.md must define a category order.")

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
        # Not str.format, so that literal braces in the config file are safe.
        install = guidance.stable_upgrade_instructions.replace("{version}", version)

    links = f"*PyPI*: {pypi_url}\n*Documentation*: {docs_url}"
    if not is_prerelease(version):
        links += f"\n*Versioned documentation*: {versioned_docs_url}"

    section = extract_changelog_section(version)
    if section is None:
        print(
            f"Warning: no CHANGELOG.md section found for {version}; "
            "the announcement will not include a summary of changes. "
            "Run `psynet dev changelog release` first if the release "
            "section has not been generated yet.",
            file=sys.stderr,
        )
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


def render_dry_run(blocks: list[dict], channel: str) -> str:
    """Render the Block Kit payload as readable preview text."""
    lines = [f"# Would post to #{channel}:", ""]
    for block in blocks:
        if block["type"] == "divider":
            lines.append("---")
        elif block["type"] == "header":
            lines.append(f"# {block['text']['text']}")
            lines.append("")
        else:
            lines.append(block["text"]["text"])
            lines.append("")
    return "\n".join(lines)


def announce_command(
    version: str,
    channel: str = DEFAULT_CHANNEL,
    dry_run: bool = False,
    dry_run_json: bool = False,
) -> None:
    """Build the announcement for *version* and post or preview it.

    Raises ValueError for configuration problems and RuntimeError for
    Slack API failures.
    """
    blocks, fallback = build_blocks(version)

    if dry_run_json:
        print(json.dumps({"blocks": blocks}, indent=2))
        return

    if dry_run:
        print(render_dry_run(blocks, channel))
        return

    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
    except ImportError as exc:
        raise ValueError(
            "slack_sdk is not installed. Install the [slack] extra:\n"
            "    uv pip install -e '.[slack]'"
        ) from exc

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN is not set.")

    client = WebClient(token=token)
    try:
        resp = client.chat_postMessage(
            channel=channel,
            text=fallback,
            blocks=blocks,
        )
    except SlackApiError as exc:
        raise RuntimeError(f"Slack error: {exc.response['error']}") from exc

    print(f"Posted to #{channel} (ts={resp['ts']})")
