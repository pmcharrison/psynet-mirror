#!/usr/bin/env python3
"""Announce a PsyNet release in the ``#psynet-support`` Slack channel.

Usage::

    python docs/scripts/announce_release.py 13.2.0          # final release
    python docs/scripts/announce_release.py 13.2.0rc0       # release candidate
    python docs/scripts/announce_release.py 13.2.0 --dry-run  # print, do not post

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
import os
import re
import sys

CHANNEL = "psynet-support"

PRERELEASE_RE = re.compile(r"(rc|a|b)\d+$", re.IGNORECASE)


def is_prerelease(version: str) -> bool:
    return bool(PRERELEASE_RE.search(version))


def build_message(version: str) -> str:
    release_url = f"https://gitlab.com/PsyNetDev/PsyNet/-/releases/v{version}"
    pypi_url = f"https://pypi.org/project/psynet/{version}/"

    if is_prerelease(version):
        title = f":test_tube: PsyNet {version} (release candidate) is out"
        docs_url = f"https://psynetdev.gitlab.io/PsyNet/rc/v{version}/"
        install = (
            f"Opt in with `pip install psynet=={version}`. "
            "Please test against your studies and report any regressions "
            "before the final tag."
        )
    else:
        title = f":tada: PsyNet {version} is out"
        docs_url = "https://psynetdev.gitlab.io/PsyNet/"
        install = "Upgrade with `pip install --upgrade psynet`."

    return (
        f"*{title}*\n\n"
        f"• <{release_url}|Release notes>\n"
        f"• <{pypi_url}|PyPI>\n"
        f"• <{docs_url}|Documentation>\n\n"
        f"{install}"
    )


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
    args = parser.parse_args()

    text = build_message(args.version)

    if args.dry_run:
        print(f"# Would post to #{args.channel}:\n")
        print(text)
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
        resp = client.chat_postMessage(channel=args.channel, text=text)
    except SlackApiError as e:
        print(f"Slack error: {e.response['error']}", file=sys.stderr)
        return 1

    print(f"Posted to #{args.channel} (ts={resp['ts']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
