import inspect
import shutil
import sys

import pytest
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import deferred

from psynet.command_line import clean_sys_modules, working_directory
from psynet.data import InvalidDefinitionError
from psynet.experiment import import_local_experiment
from psynet.pytest_psynet import path_to_test_experiment
from psynet.trial.static import StaticTrial

pytest_plugins = ["pytest_dallinger", "pytest_psynet"]


class FirstSiblingTrial(StaticTrial):
    time_estimate = 1
    sibling_probe = Column(String)

    def show_trial(self, experiment, participant):
        pass


class SecondSiblingTrial(StaticTrial):
    time_estimate = 1
    sibling_probe = Column(String)

    def show_trial(self, experiment, participant):
        pass


class DeferredSiblingTrial(StaticTrial):
    time_estimate = 1
    sibling_probe = deferred(Column(String))

    def show_trial(self, experiment, participant):
        pass


# Reimporting an experiment redefines its classes, which SQLAlchemy reports for
# every experiment class, not just those with custom columns.
@pytest.mark.filterwarnings(
    "ignore:This declarative base already contains a class:sqlalchemy.exc.SAWarning"
)
@pytest.mark.filterwarnings(
    "ignore:Reassigning polymorphic association:sqlalchemy.exc.SAWarning"
)
def test_experiment_with_custom_trial_column_imports_from_two_directories(tmp_path):
    """PsyNet reimports experiment.py from its staging copy during debug and deploy."""
    source = path_to_test_experiment("custom_trial_column")
    staging_copy = tmp_path / "staging_copy"
    shutil.copytree(source, staging_copy, ignore=shutil.ignore_patterns("__pycache__"))

    with working_directory(source):
        first = import_local_experiment()["module"].CustomColumnTrial

    clean_sys_modules()

    with working_directory(str(staging_copy)):
        second = import_local_experiment()["module"].CustomColumnTrial

    assert first is not second
    assert first.__table__.c.item_id is second.__table__.c.item_id


def test_sibling_trial_classes_may_declare_the_same_column():
    assert (
        FirstSiblingTrial.__table__.c.sibling_probe
        is SecondSiblingTrial.__table__.c.sibling_probe
    )


def test_conflicting_column_types_are_rejected():
    with pytest.raises(InvalidDefinitionError, match="already exists as String"):

        class ClashingSiblingTrial(StaticTrial):
            sibling_probe = Column(Integer)


def test_conflicting_string_lengths_are_rejected():
    with pytest.raises(InvalidDefinitionError, match="length"):

        class LongerSiblingTrial(StaticTrial):
            sibling_probe = Column(String(200))


def test_conflicting_nullability_is_rejected():
    with pytest.raises(InvalidDefinitionError, match="nullable"):

        class RequiredSiblingTrial(StaticTrial):
            sibling_probe = Column(String, nullable=False)


def test_conflicting_uniqueness_is_rejected():
    with pytest.raises(InvalidDefinitionError, match="unique"):

        class UniqueSiblingTrial(StaticTrial):
            sibling_probe = Column(String, unique=True)


def test_conflicting_index_flag_is_rejected():
    with pytest.raises(InvalidDefinitionError, match="index"):

        class IndexedSiblingTrial(StaticTrial):
            sibling_probe = Column(String, index=True)


def test_conflicting_foreign_keys_are_rejected():
    with pytest.raises(InvalidDefinitionError, match="foreign-key"):

        class ForeignKeySiblingTrial(StaticTrial):
            sibling_probe = Column(String, ForeignKey("participant.id"))


def test_conflicting_primary_key_is_rejected():
    with pytest.raises(InvalidDefinitionError, match="primary_key"):

        class PrimaryKeySiblingTrial(StaticTrial):
            sibling_probe = Column(String, primary_key=True)


def test_deferred_custom_columns_reuse_the_inherited_column():
    assert (
        FirstSiblingTrial.__table__.c.sibling_probe
        is DeferredSiblingTrial.__table__.c.sibling_probe
    )


def test_import_local_experiment_does_not_put_the_experiment_directory_on_sys_path():
    source = inspect.getsource(import_local_experiment)
    assert "sys.path.append" not in source
    assert "sys.path.insert" not in source

    experiment_dir = path_to_test_experiment("custom_trial_column")
    with working_directory(experiment_dir):
        before = list(sys.path)
        import_local_experiment()
        assert sys.path == before
