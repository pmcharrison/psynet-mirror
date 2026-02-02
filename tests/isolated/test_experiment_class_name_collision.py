import importlib.util
import sys
from pathlib import Path

import pytest

from psynet import experiment as experiment_module


def _import_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_experiment_class_name_collision(tmp_path):
    exp_a = tmp_path / "exp_a"
    exp_b = tmp_path / "exp_b"
    exp_a.mkdir()
    exp_b.mkdir()

    module_a = exp_a / "mod_a.py"
    module_b = exp_b / "mod_b.py"

    module_a.write_text(
        "from sqlalchemy import Column, Integer\n"
        "from psynet.data import SQLBase, SQLMixin\n"
        "\n"
        "class DuplicateTrial(SQLBase, SQLMixin):\n"
        "    __tablename__ = 'duplicate_trial_a'\n"
        "    id = Column(Integer, primary_key=True)\n"
    )
    module_b.write_text(
        "from sqlalchemy import Column, Integer\n"
        "from psynet.data import SQLBase, SQLMixin\n"
        "\n"
        "class DuplicateTrial(SQLBase, SQLMixin):\n"
        "    __tablename__ = 'duplicate_trial_b'\n"
        "    id = Column(Integer, primary_key=True)\n"
    )

    try:
        _import_module(module_a, "exp_a_mod")
        experiment_module._register_experiment_sqlalchemy_classes(str(exp_a))

        _import_module(module_b, "exp_b_mod")
        with pytest.raises(RuntimeError, match="class name collision"):
            experiment_module._register_experiment_sqlalchemy_classes(str(exp_b))
    finally:
        experiment_module._EXPERIMENT_SQL_CLASS_REGISTRY.clear()
        sys.modules.pop("exp_a_mod", None)
        sys.modules.pop("exp_b_mod", None)
