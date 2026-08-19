"""Validate Agent Skill trigger-eval fixture files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

STOPWORDS = frozenset(
    {
        "about",
        "after",
        "also",
        "and",
        "asked",
        "before",
        "changes",
        "complete",
        "completed",
        "create",
        "draft",
        "from",
        "help",
        "into",
        "just",
        "make",
        "only",
        "please",
        "review",
        "run",
        "that",
        "the",
        "this",
        "through",
        "update",
        "using",
        "when",
        "with",
        "without",
        "your",
    }
)

TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def load_trigger_evals(eval_file: Path) -> tuple[list[dict[str, Any]], list[str]]:
    problems: list[str] = []
    if not eval_file.exists():
        return [], [f"{eval_file}: missing trigger eval file"]

    try:
        loaded = yaml.safe_load(eval_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [], [f"{eval_file}: invalid YAML: {exc}"]

    if loaded is None:
        return [], [f"{eval_file}: trigger eval file is empty"]
    if not isinstance(loaded, list):
        return [], [f"{eval_file}: trigger eval file must be a YAML list"]

    entries: list[dict[str, Any]] = []
    for index, item in enumerate(loaded, start=1):
        if not isinstance(item, dict):
            problems.append(f"{eval_file}: entry {index} must be a mapping")
            continue
        entries.append(item)
    return entries, problems


def _query_tokens(query: str) -> set[str]:
    tokens = {match.group(0) for match in TOKEN_RE.finditer(query.lower())}
    return {token for token in tokens if len(token) > 3 and token not in STOPWORDS}


def _description_tokens(description: str) -> set[str]:
    return _query_tokens(description)


def _skill_name_tokens(skill_name: str) -> set[str]:
    return {part for part in skill_name.split("-") if part}


def description_supports_trigger(description: str, skill_name: str, query: str) -> bool:
    query_tokens = _query_tokens(query)
    description_tokens = _description_tokens(description)
    name_tokens = _skill_name_tokens(skill_name)

    if query_tokens & description_tokens:
        return True
    if name_tokens & query_tokens:
        return True
    if skill_name.replace("-", " ") in query.lower():
        return True
    return False


def description_overmatches(description: str, skill_name: str, query: str) -> bool:
    query_tokens = _query_tokens(query)
    if not query_tokens:
        return False

    description_tokens = _description_tokens(description) | _skill_name_tokens(skill_name)
    overlap = query_tokens & description_tokens
    return len(overlap) >= max(2, len(query_tokens) - 1)


def validate_trigger_eval_file(
    eval_file: Path,
    *,
    skills_dir: Path,
    skill_names: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    entries, load_problems = load_trigger_evals(eval_file)
    problems.extend(load_problems)
    if load_problems:
        return problems, warnings

    if skill_names is None:
        skill_names = {
            path.parent.name
            for path in skills_dir.rglob("SKILL.md")
            if path.parent.is_dir()
        }

    descriptions: dict[str, str] = {}
    for skill_file in sorted(skills_dir.rglob("SKILL.md")):
        skill_name = skill_file.parent.name
        text = skill_file.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            continue
        parts = text.split("---\n", 2)
        if len(parts) < 3:
            continue
        loaded = yaml.safe_load(parts[1])
        if isinstance(loaded, dict):
            description = loaded.get("description", "")
            if isinstance(description, str):
                descriptions[skill_name] = description

    per_skill_counts: dict[str, int] = {}
    for index, entry in enumerate(entries, start=1):
        prefix = f"{eval_file}: entry {index}"
        skill = entry.get("skill")
        query = entry.get("query")
        should_trigger = entry.get("should_trigger")

        if not isinstance(skill, str) or not skill.strip():
            problems.append(f"{prefix}: missing skill")
            continue
        if skill not in skill_names and skill not in descriptions:
            problems.append(f"{prefix}: unknown skill {skill!r}")
            continue
        if not isinstance(query, str) or not query.strip():
            problems.append(f"{prefix}: missing query")
            continue
        if not isinstance(should_trigger, bool):
            problems.append(f"{prefix}: should_trigger must be a boolean")
            continue

        per_skill_counts[skill] = per_skill_counts.get(skill, 0) + 1
        description = descriptions.get(skill, "")
        if not description:
            warnings.append(f"{prefix}: no description loaded for skill {skill!r}")
            continue

        if should_trigger:
            if not description_supports_trigger(description, skill, query):
                problems.append(
                    f"{prefix}: should_trigger query lacks keyword overlap with "
                    f"{skill!r} description; tune the description or query"
                )
        elif description_overmatches(description, skill, query):
            warnings.append(
                f"{prefix}: should-not-trigger query overlaps heavily with "
                f"{skill!r} description; consider tightening the description"
            )

    for skill, count in sorted(per_skill_counts.items()):
        if count < 2:
            warnings.append(
                f"{eval_file}: skill {skill!r} has only {count} trigger eval; "
                "add at least one should_trigger and one should-not-trigger query"
            )

    return problems, warnings
