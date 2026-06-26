import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = ROOT / "docs" / "scripts" / "generate_version_switcher.py"


spec = importlib.util.spec_from_file_location(
    "generate_version_switcher", GENERATOR_PATH
)
generate_version_switcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_version_switcher)


def test_alpha_switcher_name_uses_base_version():
    assert generate_version_switcher.format_alpha_name("13.3.0a0") == "13.3.0 alpha"
    assert generate_version_switcher.format_alpha_name("13.4.2a7") == "13.4.2 alpha"


def test_alpha_switcher_name_rejects_non_alpha_version():
    with pytest.raises(ValueError, match="Expected an alpha version"):
        generate_version_switcher.format_alpha_name("13.3.0")


def test_alpha_switcher_entry_keeps_raw_version_for_matching():
    entries = generate_version_switcher.build_entries(
        "https://psynetdev.gitlab.io/PsyNet",
        tags=["v13.2.0"],
        alpha_version="13.3.0a0",
    )

    assert entries[0] == {
        "name": "13.3.0 alpha",
        "version": "13.3.0a0",
        "url": "https://psynetdev.gitlab.io/PsyNet/alpha/",
    }
