from pathlib import Path

from psynet.command_line import clean_sys_modules
from psynet.experiment import import_local_experiment
from psynet.trial.static import StaticNetwork
from psynet.utils import get_psynet_root, working_directory


def _expected_polymorphic_identity(relative_path, class_name):
    root = get_psynet_root()
    relative_path = (root / Path(relative_path)).relative_to(root).as_posix()
    return f"{relative_path}:{class_name}"


def test_polymorphic_identity_uses_repo_relative_path():
    assert StaticNetwork.__mapper__.polymorphic_identity == _expected_polymorphic_identity(
        "psynet/trial/static.py",
        "StaticNetwork",
    )


def test_multiple_experiment_imports_do_not_conflict():
    root = get_psynet_root()
    experiment_dirs = [
        root / "tests/experiments/static",
        root / "tests/experiments/static_big",
    ]

    clean_sys_modules()
    for directory in experiment_dirs:
        with working_directory(directory):
            import_local_experiment()
        clean_sys_modules()
