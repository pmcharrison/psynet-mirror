#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

SEMVER_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
PSYNET_VERSION_RE = re.compile(r'^psynet_version\s*=\s*"([^"]+)"', re.MULTILINE)


def parse_semver(tag):
    major, minor, patch = tag[1:].split(".")
    return int(major), int(minor), int(patch)


def get_tags():
    output = subprocess.check_output(
        ["git", "tag", "--list", "--sort=-version:refname"], text=True
    )
    tags = [tag.strip() for tag in output.splitlines() if SEMVER_TAG.match(tag.strip())]
    return tags


def parse_psynet_version(source_text):
    match = PSYNET_VERSION_RE.search(source_text)
    if match is None:
        raise RuntimeError("Could not parse psynet_version from psynet/version.py")
    return match.group(1)


def get_master_psynet_version(default_branch):
    try:
        source = subprocess.check_output(
            ["git", "show", f"origin/{default_branch}:psynet/version.py"], text=True
        )
    except subprocess.CalledProcessError:
        if os.environ.get("CI"):
            raise RuntimeError(
                f"Could not read psynet/version.py from origin/{default_branch} in CI."
            )
        source = Path("psynet/version.py").read_text()
    return parse_psynet_version(source)


def select_recent_patch_tags(tags, max_majors=2):
    parsed = [(tag, *parse_semver(tag)) for tag in tags]
    majors = sorted({major for _, major, _, _ in parsed}, reverse=True)[:max_majors]

    best_per_minor = {}
    for tag, major, minor, patch in parsed:
        if major not in majors:
            continue
        key = (major, minor)
        current = best_per_minor.get(key)
        if current is None or patch > current[2]:
            best_per_minor[key] = (tag, minor, patch)

    selected = [
        value[0]
        for _, value in sorted(
            best_per_minor.items(),
            key=lambda item: (item[0][0], item[0][1]),
            reverse=True,
        )
    ]
    return selected


def get_highest_stable_tag(tags):
    if not tags:
        return None
    parsed = sorted(
        ((tag, *parse_semver(tag)) for tag in tags),
        key=lambda item: (item[1], item[2], item[3]),
        reverse=True,
    )
    return parsed[0][0]


def build_entries(base_url, tags, alpha_version):
    base_url = base_url.rstrip("/")

    entries = [
        {
            "name": f"alpha ({alpha_version})",
            "version": alpha_version,
            "url": f"{base_url}/alpha/",
        }
    ]
    for tag in tags:
        entries.append(
            {
                "name": tag,
                "version": tag,
                "url": f"{base_url}/{tag}/",
            }
        )
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Output JSON path")
    parser.add_argument(
        "--base-url",
        default="https://psynetdev.gitlab.io/PsyNet",
        help="Base public URL for docs",
    )
    parser.add_argument(
        "--default-branch",
        default="master",
        help="Default branch name for reading alpha version",
    )
    parser.add_argument(
        "--print-highest-stable",
        action="store_true",
        help="Print the highest stable release tag and exit",
    )
    parser.add_argument(
        "--print-selected-stable-tags",
        action="store_true",
        help="Print selected stable tags (space-separated) and exit",
    )
    parser.add_argument(
        "--print-alpha-version",
        action="store_true",
        help="Print alpha version from default branch and exit",
    )
    args = parser.parse_args()

    stable_tags = get_tags()
    if args.print_highest_stable:
        highest_stable_tag = get_highest_stable_tag(stable_tags)
        if highest_stable_tag is None:
            raise RuntimeError("No stable release tags found.")
        print(highest_stable_tag)
        return

    if args.print_selected_stable_tags:
        print(" ".join(select_recent_patch_tags(stable_tags)))
        return

    if args.print_alpha_version:
        print(get_master_psynet_version(args.default_branch))
        return

    if not args.output:
        raise ValueError("--output is required unless a --print-* option is used.")

    tags = select_recent_patch_tags(stable_tags)
    alpha_version = get_master_psynet_version(args.default_branch)
    entries = build_entries(args.base_url, tags, alpha_version)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(entries, indent=2) + "\n")


if __name__ == "__main__":
    main()
