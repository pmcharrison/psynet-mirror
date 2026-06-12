import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from psynet.dev import page_preview


def test_parse_page_target_requires_module_and_attribute():
    assert page_preview.parse_page_target("experiment.py:preview_page") == (
        "experiment.py",
        "preview_page",
    )

    with pytest.raises(ValueError, match="MODULE:ATTRIBUTE"):
        page_preview.parse_page_target("preview_page")


def test_create_preview_experiment_writes_wrapper_and_mirrors_paths(tmp_path):
    experiment_root = tmp_path / "experiment"
    experiment_root.mkdir()
    (experiment_root / "experiment.py").write_text(
        "def preview_page():\n    pass\n", encoding="utf-8"
    )
    (experiment_root / "config.txt").write_text(
        "[Config variables]\ntitle = Preview\n", encoding="utf-8"
    )
    (experiment_root / "static").mkdir()
    (experiment_root / "static" / "stimulus.txt").write_text("hello", encoding="utf-8")

    preview_root = tmp_path / "preview"
    result = page_preview.create_preview_experiment(
        "experiment.py:preview_page",
        experiment_root=experiment_root,
        preview_root=preview_root,
    )

    assert result == preview_root
    source = (preview_root / "experiment.py").read_text(encoding="utf-8")
    assert '_PAGE_TARGET = "experiment.py:preview_page"' in source
    assert "class Exp(psynet.experiment.Experiment):" in source
    assert "PageMaker(" in source
    assert (preview_root / "config.txt").exists()
    assert (preview_root / "static" / "stimulus.txt").read_text(
        encoding="utf-8"
    ) == "hello"
    assert (preview_root / ".git").exists()


def test_create_preview_experiment_writes_required_defaults(tmp_path):
    preview_root = page_preview.create_preview_experiment(
        "experiment.py:preview_page",
        experiment_root=tmp_path,
        preview_root=tmp_path / "preview",
    )

    assert "title = PsyNet page preview" in (preview_root / "config.txt").read_text(
        encoding="utf-8"
    )
    assert "source_code.zip" in (preview_root / ".gitignore").read_text(
        encoding="utf-8"
    )
    assert (preview_root / "requirements.txt").read_text(encoding="utf-8") == ""
    assert (preview_root / "constraints.txt").read_text(encoding="utf-8") == ""
    assert (preview_root / ".git").exists()


def test_generated_preview_experiment_resolves_file_target(tmp_path):
    experiment_root = tmp_path / "experiment"
    experiment_root.mkdir()
    (experiment_root / "experiment.py").write_text(
        "from psynet.page import InfoPage\n\n"
        "def preview_page(participant=None, experiment=None):\n"
        "    return InfoPage('Hello preview', time_estimate=1)\n",
        encoding="utf-8",
    )

    preview_root = page_preview.create_preview_experiment(
        "experiment.py:preview_page",
        experiment_root=experiment_root,
        preview_root=tmp_path / "preview",
    )

    spec = importlib.util.spec_from_file_location(
        "generated_preview_experiment", preview_root / "experiment.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    participant = SimpleNamespace(
        module_state=None,
        in_module=False,
        current_trial=None,
    )
    page = module._preview_page(experiment=None, participant=participant)
    assert page.plain_text == "Hello preview"


def test_preview_experiment_directory_is_temporary(tmp_path):
    with page_preview.preview_experiment_directory(
        "experiment.py:preview_page", experiment_root=tmp_path
    ) as preview_root:
        assert preview_root.exists()
        assert (preview_root / "experiment.py").exists()
        preview_path = Path(preview_root)

    assert not preview_path.exists()
