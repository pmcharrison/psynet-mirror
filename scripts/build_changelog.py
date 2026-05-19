#!/usr/bin/env python3
"""Thin CI wrapper for the source-checkout changelog builder.

The real implementation lives in `dev/build_changelog.py` and powers the
developer-facing `psynet dev changelog` command. This wrapper exists so
the lightweight GitLab `changelog_check` job can run the same logic with only
`python3` available, without installing PsyNet and its dependencies.
"""

import importlib.util
import sys
from pathlib import Path


def _load_build_changelog_module():
    module_path = Path(__file__).resolve().parents[1] / "dev" / "build_changelog.py"
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
