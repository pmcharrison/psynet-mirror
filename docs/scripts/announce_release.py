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
from pathlib import Path

CHANNEL = "psynet-support"
ROOT = Path(__file__).resolve().parents[2]
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

PRERELEASE_RE = re.compile(r"(rc|a|b)\d+$", re.IGNORECASE)
RELEASE_HEADING_RE = re.compile(r"^#{1,2} \[.*?\].*$", re.MULTILINE)
SECTION_HEADING_RE = re.compile(r"^#{2,3} (\w+)$", re.MULTILINE)

INTERNAL_RE = re.compile(
    "|".join(
        [
            # CI / testing / developer tooling
            r"AGENTS\.md",
            r"CI[ _]job",
            r"CI[ _]test",
            r"CI[ _]config",
            r"pre-commit",
            r"Playwright",
            r"Sphinx",
            r"GitLab CI",
            r"Ruff",
            r"PgBadger",
            r"pytest",
            r"bot WebDriver",
            r"moto",
            r"S3 emulator",
            r"performance.test",
            r"Cursor workflow",
            r"branch-review",
            r"CHANGELOG",
            r"perf_test",
            r"PerformanceTester",
            r"demo coverage",
            r"failure diagnostics",
            r"bump-my-version",
            r"\.bumpversion",
            r"formatting from black",
            # internal code cleanup / docstrings / types
            r"docstring",
            r"type hint",
            r"@classmethod",
            r"unreachable code",
            r"variable shadowing",
            r"f-string prefix",
            r"super\(\)",
            r"quote escaping",
            r"Unicode typo",
            r"Removed unused(?! participant)",
            r"Removed redundant",
            r"Removed unreachable",
            r"regression test",
            r"test code",
            r"test failure",
            r"`test_",
            r"version-checking helper",
            r"Reformatted",
            # performance test internals
            r"WaitPage time",
            r"AsyncProcess duration",
            r"trial count stats",
            r"scaling slowdown",
            r"requests/sec",
            r"bot initialization",
            r"detection and reporting of bots",
            r"RQ worker count",
            r"performance-test",
            r"bot duration",
            r"bot output",
            r"tabulate-based",
            r"ANSI-colored",
            r"Refactored performance",
            r"Separated bot",
            r"Redirected bot",
            r"Improved performance",
            # internal utility / helper fixes
            r"`_Py",
            r"`get_package",
            r"`get_locales",
            r"`check_translations",
            r"`linspace",
            r"`format_timedelta",
            r"`get_fitting_font",
            r"`pretty_format",
            r"`S3Storage",
            r"`NumpySerializer",
            r"`SVGLogo",
            r"`os\.path\.remove",
            r"translation validation",
            r"translation_contains",
            r"_experiment_variables",
            r"pybabel",
            r"Installed demo dependencies",
            r"`@local_only",
            r"`@ci_only",
            r"docs/scripts",
            r"documentation navigation",
            r"documentation builds for",
            r"strip_url_parameters",
            r"custom `cache`",
            r"dict_to_js_vars",
            # minor cosmetic / wording / docs-only
            r"Standardized.*capitalization",
            r"IDE recommendations",
            r"experiment scripts where they were unused",
            r"generate_version_switcher",
            r"Refactored timeline page",
            r"Updated S3 test",
            r"Replaced.*S3 emulator",
            r"Switched docs deployment",
            r"auto-cancel redundant",
            r"Expanded Playwright",
            r"stabilized visual snapshots",
            r"Disallow PsyNet requirements pinned to master",
            r"Exported datetimes",
            r"Suppressed.*DeprecationWarning",
            r"`CI` environment variable",
            r"StretchedTimbre",
            r"Lucid.*error message",
            r"incorrect Sphinx",
            r"malformed Sphinx",
            r"experiment status payload",
            r"chatroom to Rock",
            r"websocket support",
            r"getting started.*section",
            r"\.vscode",
            r"demo/docs example",
            r"async process queue delay",
            r"Removed.*\bCI\b",
            r"Removed `dict_to_js_vars`",
            r"Removed the PgBadger",
            # internal bugfixes unlikely to affect experiment code
            r"`generate_text_file`",
            r"`WorkerAsyncProcess",
            r"`Notifier`.*memory",
            r"`Participant\.fail`.*wrong argument",
            r"resource type mismatch",
            r"incorrect property name",
        ]
    ),
    re.IGNORECASE,
)

MAX_ITEMS_PER_SECTION = 10


def is_prerelease(version: str) -> bool:
    return bool(PRERELEASE_RE.search(version))


def extract_changelog_section(version: str) -> str | None:
    """Return the body of the CHANGELOG section for *version*, or None."""
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


def summarize_for_experimenters(section_body: str) -> str:
    """Condense a CHANGELOG section into experimenter-facing highlights."""
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
            if not INTERNAL_RE.search(entry):
                categories.setdefault(current_category, []).append(entry)
        elif (
            current_category
            and line.startswith("  ")
            and categories.get(current_category)
        ):
            sub = line.strip()
            if sub and not sub.startswith("- "):
                sub = re.sub(r"\s*\(author:.*?\)\.?", "", sub)
                categories[current_category][-1] += " " + sub

    display_order = ["Added", "Changed", "Fixed", "Removed"]
    parts: list[str] = []
    for cat in display_order:
        entries = categories.get(cat, [])
        if not entries:
            continue
        parts.append(f"\n*{cat}*")
        shown = entries[:MAX_ITEMS_PER_SECTION]
        for entry in shown:
            parts.append(f"• {_concise(entry)}")
        remaining = len(entries) - len(shown)
        if remaining > 0:
            parts.append(f"_…and {remaining} more in the release notes_")

    return "\n".join(parts).strip()


def build_blocks(version: str) -> tuple[list[dict], str]:
    """Return (blocks, fallback_text) for a Slack message."""
    release_url = f"https://gitlab.com/PsyNetDev/PsyNet/-/releases/v{version}"
    pypi_url = f"https://pypi.org/project/psynet/{version}/"

    if is_prerelease(version):
        title = f":test_tube: PsyNet {version} — Release Candidate :test_tube:"
        subtitle = "A new release candidate is ready for testing!"
        docs_url = f"https://psynetdev.gitlab.io/PsyNet/rc/v{version}/"
        install = (
            f"Opt in with `pip install psynet=={version}`. "
            "Please test against your studies and report any regressions "
            "before the final tag."
        )
    else:
        title = f":tada: PsyNet {version} is out! :rocket:"
        subtitle = "A new stable release is now available."
        docs_url = "https://psynetdev.gitlab.io/PsyNet/"
        install = "Upgrade with `pip install --upgrade psynet`."

    links = f"*PyPI*: {pypi_url}\n*Documentation*: {docs_url}"

    section = extract_changelog_section(version)
    summary = summarize_for_experimenters(section) if section else ""

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": title, "emoji": True},
        },
        _mrkdwn_block(f"_{subtitle}_"),
    ]

    if summary:
        blocks.append({"type": "divider"})
        blocks.append(
            _mrkdwn_block(
                f"Here are the key changes relevant for experimenters:\n\n{summary}"
            )
        )
        blocks.append(
            _mrkdwn_block(
                f"See the <{release_url}|full release notes> for all details."
            )
        )

    blocks.append({"type": "divider"})
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
