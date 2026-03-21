"""Inspect PsyNet demo directories against the standard essential-files layout."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from importlib import resources
from pathlib import Path

from psynet.command_line import (
    EXPERIMENT_SCAFFOLD_GENERATED_FILES,
    EXPERIMENT_SCAFFOLD_OPTIONAL_TEMPLATE_FILES,
    EXPERIMENT_SCAFFOLD_TEMPLATE_DIRECTORIES,
    EXPERIMENT_SCAFFOLD_TEMPLATE_FILES,
)
from psynet.utils import get_psynet_root

ROOT = get_psynet_root()
DEMOS_ROOT = ROOT / "demos"
README_TEMPLATE_PATH = "resources/experiment_scripts/README.md"
ESSENTIAL_DEMO_ROOT_FILES = {"README.md", "requirements.txt", "constraints.txt"}
IGNORED_ROOT_ENTRIES = {".git", "__pycache__"}


def _hash_bytes(contents: bytes) -> str:
    """Return a stable hash for raw file contents."""
    return sha256(contents).hexdigest()


def _resource_hash(relative_path: str) -> str:
    """Return the content hash of a packaged PsyNet resource file."""
    with resources.as_file(resources.files("psynet") / relative_path) as path:
        return _hash_bytes(Path(path).read_bytes())


def _file_hash(path: Path) -> str:
    """Return the content hash of a file on disk."""
    return _hash_bytes(path.read_bytes())


def _build_scaffold_dir_templates() -> dict[str, dict[str, str]]:
    """Build a hash map for scaffold-managed directory contents."""
    templates: dict[str, dict[str, str]] = {}

    for relative_path in EXPERIMENT_SCAFFOLD_TEMPLATE_FILES:
        path = Path(relative_path)
        if len(path.parts) <= 1:
            continue

        root_dir = path.parts[0]
        relative_file = Path(*path.parts[1:]).as_posix()
        templates.setdefault(root_dir, {})[relative_file] = _resource_hash(
            f"resources/experiment_scripts/{relative_path}"
        )

    for root_dir in EXPERIMENT_SCAFFOLD_TEMPLATE_DIRECTORIES:
        with resources.as_file(
            resources.files("psynet") / f"resources/experiment_scripts/{root_dir}"
        ) as template_dir:
            file_hashes = {}
            for file_path in Path(template_dir).rglob("*"):
                if file_path.is_file():
                    file_hashes[file_path.relative_to(template_dir).as_posix()] = (
                        _file_hash(file_path)
                    )
            templates[root_dir] = file_hashes

    return templates


SCAFFOLD_DIR_TEMPLATES = _build_scaffold_dir_templates()
SCAFFOLD_ROOT_DIRS = set(SCAFFOLD_DIR_TEMPLATES)
SCAFFOLD_REMOVABLE_ROOT_FILES = {
    Path(relative_path).name
    for relative_path in EXPERIMENT_SCAFFOLD_TEMPLATE_FILES
    if len(Path(relative_path).parts) == 1 and Path(relative_path).name != "README.md"
}
SCAFFOLD_REMOVABLE_ROOT_FILES.update(EXPERIMENT_SCAFFOLD_OPTIONAL_TEMPLATE_FILES)
SCAFFOLD_REMOVABLE_ROOT_FILES.update(EXPERIMENT_SCAFFOLD_GENERATED_FILES)
GENERIC_README_HASH = _resource_hash(README_TEMPLATE_PATH)


@dataclass
class DemoAuditRecord:
    """Store the audit classification for one demo directory."""

    path: str
    already_minimal: bool
    generic_readme: bool
    uses_relative_imports: bool
    removable_root_files: list[str]
    removable_root_dirs: list[str]
    preserved_root_files: list[str]
    preserved_root_dirs: list[str]
    customized_scaffold_files: list[str]
    customized_scaffold_dirs: list[str]


def _uses_relative_imports(demo_dir: Path) -> bool:
    """Report whether any top-level Python file uses explicit relative imports."""
    pattern = re.compile(r"^\s*from \.", re.MULTILINE)
    for file_path in demo_dir.glob("*.py"):
        if pattern.search(file_path.read_text()):
            return True
    return False


def _expected_generated_file_contents(demo_dir: Path, filename: str) -> str:
    """Return the expected contents of a generated scaffold-managed file."""
    if filename == "Dockertag":
        return f"{demo_dir.name}\n"
    return EXPERIMENT_SCAFFOLD_GENERATED_FILES[filename]()


def _classify_root_dir(path: Path) -> tuple[list[str], bool]:
    """Compare one scaffold-managed root directory against its template."""
    expected_files = SCAFFOLD_DIR_TEMPLATES[path.name]
    actual_files = {
        file_path.relative_to(path).as_posix(): _file_hash(file_path)
        for file_path in path.rglob("*")
        if file_path.is_file()
    }

    mismatched = sorted(
        {
            *[name for name in actual_files if name not in expected_files],
            *[name for name in expected_files if name not in actual_files],
            *[
                name
                for name in actual_files
                if name in expected_files and actual_files[name] != expected_files[name]
            ],
        }
    )
    return mismatched, bool(mismatched)


def audit_demo_directory(demo_dir: str | Path) -> DemoAuditRecord:
    """Classify one demo directory against the essential-files policy."""
    demo_dir = Path(demo_dir)
    preserved_root_files = []
    preserved_root_dirs = []
    removable_root_files = []
    removable_root_dirs = []
    customized_scaffold_files = []
    customized_scaffold_dirs = []

    for entry in sorted(demo_dir.iterdir()):
        if entry.name in IGNORED_ROOT_ENTRIES:
            continue

        if entry.is_dir():
            if entry.name in SCAFFOLD_ROOT_DIRS:
                removable_root_dirs.append(entry.name)
                _, customized = _classify_root_dir(entry)
                if customized:
                    customized_scaffold_dirs.append(entry.name)
            else:
                preserved_root_dirs.append(entry.name)
            continue

        if entry.name in ESSENTIAL_DEMO_ROOT_FILES:
            preserved_root_files.append(entry.name)
        elif entry.name in SCAFFOLD_REMOVABLE_ROOT_FILES:
            removable_root_files.append(entry.name)

            if entry.name in EXPERIMENT_SCAFFOLD_GENERATED_FILES:
                expected = _expected_generated_file_contents(demo_dir, entry.name)
                if entry.read_text() != expected:
                    customized_scaffold_files.append(entry.name)
            else:
                template_hash = _resource_hash(
                    f"resources/experiment_scripts/{entry.name}"
                )
                if _file_hash(entry) != template_hash:
                    customized_scaffold_files.append(entry.name)
        else:
            preserved_root_files.append(entry.name)

    readme_path = demo_dir / "README.md"
    generic_readme = (
        readme_path.exists() and _file_hash(readme_path) == GENERIC_README_HASH
    )

    return DemoAuditRecord(
        path=demo_dir.relative_to(ROOT).as_posix(),
        already_minimal=not removable_root_files and not removable_root_dirs,
        generic_readme=generic_readme,
        uses_relative_imports=_uses_relative_imports(demo_dir),
        removable_root_files=removable_root_files,
        removable_root_dirs=removable_root_dirs,
        preserved_root_files=preserved_root_files,
        preserved_root_dirs=preserved_root_dirs,
        customized_scaffold_files=customized_scaffold_files,
        customized_scaffold_dirs=customized_scaffold_dirs,
    )


def audit_demo_tree(demo_paths: list[str] | None = None) -> list[DemoAuditRecord]:
    """Audit either the requested demos or the entire demos tree."""
    if demo_paths:
        directories = []
        for path in demo_paths:
            demo_path = Path(path)
            if not demo_path.is_absolute():
                demo_path = ROOT / demo_path
            directories.append(demo_path.resolve())
    else:
        directories = sorted(
            experiment_file.parent.resolve()
            for experiment_file in DEMOS_ROOT.rglob("experiment.py")
        )
    return [audit_demo_directory(path) for path in directories]


def _print_text_report(records: list[DemoAuditRecord]) -> None:
    """Print a human-readable summary of audit results."""
    total = len(records)
    already_minimal = sum(record.already_minimal for record in records)
    generic_readmes = sum(record.generic_readme for record in records)
    customized = sum(
        bool(record.customized_scaffold_files or record.customized_scaffold_dirs)
        for record in records
    )
    relative_imports = sum(record.uses_relative_imports for record in records)

    print(f"Total demos: {total}")
    print(f"Already essential-only: {already_minimal}")
    print(f"Still carrying scaffold boilerplate: {total - already_minimal}")
    print(f"Generic READMEs: {generic_readmes}")
    print(f"Demos with customized scaffold-managed paths: {customized}")
    print(f"Demos using relative imports: {relative_imports}")
    print()

    for record in records:
        removable_count = len(record.removable_root_files) + len(
            record.removable_root_dirs
        )
        customized_count = len(record.customized_scaffold_files) + len(
            record.customized_scaffold_dirs
        )
        print(
            f"{record.path}: "
            f"{'essential-only' if record.already_minimal else 'full'}; "
            f"remove={removable_count}; "
            f"generic_readme={'yes' if record.generic_readme else 'no'}; "
            f"customized_scaffold={customized_count}; "
            f"relative_imports={'yes' if record.uses_relative_imports else 'no'}"
        )
        if removable_count:
            print(
                "  would remove: "
                + ", ".join(record.removable_root_files + record.removable_root_dirs)
            )
        if customized_count:
            print(
                "  customized scaffold paths: "
                + ", ".join(
                    record.customized_scaffold_files + record.customized_scaffold_dirs
                )
            )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the demo audit script."""
    parser = argparse.ArgumentParser(
        description="Audit PsyNet demos against the standard demo file layout."
    )
    parser.add_argument(
        "--demo",
        action="append",
        help="Audit only the given demo path(s), e.g. demos/features/api.",
    )
    parser.add_argument(
        "--only-nonminimal",
        action="store_true",
        help="Only show demos that still carry scaffold boilerplate files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the demo audit CLI and print the requested report format."""
    args = parse_args()
    records = audit_demo_tree(args.demo)

    if args.only_nonminimal:
        records = [record for record in records if not record.already_minimal]

    if args.json:
        print(json.dumps([asdict(record) for record in records], indent=2))
    else:
        _print_text_report(records)

    return 0


__all__ = [
    "DemoAuditRecord",
    "audit_demo_directory",
    "audit_demo_tree",
    "main",
    "parse_args",
]
