#!/usr/bin/env python3

import importlib.util
import sys
from pathlib import Path


def _load_build_changelog_module():
    module_path = (
        Path(__file__).resolve().parents[1] / "psynet" / "dev" / "build_changelog.py"
    )
    spec = importlib.util.spec_from_file_location("psynet_build_changelog", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load changelog builder from {module_path}.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    return _load_build_changelog_module().main()


if __name__ == "__main__":
    raise SystemExit(main())
