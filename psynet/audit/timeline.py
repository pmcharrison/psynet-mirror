"""Parse audit timeline markdown entries."""

from __future__ import annotations

import re
from dataclasses import dataclass

TIMELINE_ENTRY_RE = re.compile(
    r"^- (?P<timestamp>T\+\d{2}:\d{2}:\d{2}) "
    r"\[(?P<actor>agent-start|agent|agent-stop|manual|system)\] "
    r"(?P<details>.+)$"
)
TIMELINE_TAG_RE = re.compile(r"^\[(?P<tag>[a-z][a-z0-9-]*)\]\s+")


@dataclass(frozen=True)
class TimelineEntry:
    """A structured audit timeline entry."""

    timestamp: str
    actor: str
    description: str
    tags: list[str]


def parse_timeline_entries(markdown: str) -> list[TimelineEntry]:
    """Parse structured entries from ``TIMELINE.md``."""
    entries: list[TimelineEntry] = []
    for line in markdown.splitlines():
        match = TIMELINE_ENTRY_RE.fullmatch(line)
        if match is None:
            continue
        details = match.group("details")
        tags: list[str] = []
        while tag_match := TIMELINE_TAG_RE.match(details):
            tags.append(tag_match.group("tag"))
            details = details[tag_match.end() :]
        entries.append(
            TimelineEntry(
                timestamp=match.group("timestamp"),
                actor=match.group("actor"),
                description=details,
                tags=tags,
            )
        )
    return entries
