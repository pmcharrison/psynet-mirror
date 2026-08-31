import shutil
import sys
import uuid

import pytest
from dallinger import db
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import deferred

from psynet.command_line import clean_sys_modules, working_directory
from psynet.data import InvalidDefinitionError
from psynet.experiment import get_experiment, import_local_experiment
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment
from psynet.trial.static import StaticNode, StaticTrial

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


class ColumnOptionsTrial(StaticTrial):
    time_estimate = 1
    scalar_default_probe = Column(Integer, default=1)
    callable_default_probe = Column(Integer, default=lambda: 1)
    server_default_probe = Column(Integer, server_default=text("1"))
    onupdate_probe = Column(Integer, onupdate=2)
    constrained_probe = Column(Integer, CheckConstraint("constrained_probe >= 0"))

    def show_trial(self, experiment, participant):
        pass


class TypeOptionsTrial(StaticTrial):
    time_estimate = 1
    numeric_probe = Column(Numeric(precision=8, scale=2))
    collation_probe = Column(String(collation="C"))

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


@pytest.mark.parametrize(
    ("attribute", "column"),
    [
        ("numeric_probe", Column(Numeric(precision=10, scale=2))),
        ("numeric_probe", Column(Numeric(precision=8, scale=3))),
        ("collation_probe", Column(String(collation="POSIX"))),
    ],
)
def test_conflicting_type_options_are_rejected(attribute, column):
    with pytest.raises(InvalidDefinitionError, match="already exists"):
        type(
            f"Conflicting{attribute.title().replace('_', '')}Trial",
            (StaticTrial,),
            {attribute: column},
        )


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


@pytest.mark.parametrize(
    ("attribute", "column", "match"),
    [
        ("scalar_default_probe", Column(Integer, default=2), "default"),
        ("callable_default_probe", Column(Integer, default=lambda: 2), "default"),
        (
            "server_default_probe",
            Column(Integer, server_default=text("2")),
            "server_default",
        ),
        ("onupdate_probe", Column(Integer, onupdate=3), "onupdate"),
        (
            "constrained_probe",
            Column(Integer, CheckConstraint("constrained_probe > 0")),
            "constraints",
        ),
    ],
)
def test_conflicting_column_behavior_is_rejected(attribute, column, match):
    with pytest.raises(InvalidDefinitionError, match=match):
        type(
            f"Conflicting{attribute.title().replace('_', '')}Trial",
            (StaticTrial,),
            {attribute: column},
        )


def test_equivalent_column_behavior_is_reused():
    equivalent = type(
        "EquivalentColumnOptionsTrial",
        (StaticTrial,),
        {
            "scalar_default_probe": Column(Integer, default=1),
            "callable_default_probe": Column(Integer, default=lambda: 1),
            "server_default_probe": Column(Integer, server_default=text("1")),
            "onupdate_probe": Column(Integer, onupdate=2),
            "constrained_probe": Column(
                Integer,
                CheckConstraint("constrained_probe >= 0"),
            ),
            "numeric_probe": Column(Numeric(precision=8, scale=2)),
            "collation_probe": Column(String(collation="C")),
        },
    )

    for attribute in [
        "scalar_default_probe",
        "callable_default_probe",
        "server_default_probe",
        "onupdate_probe",
        "constrained_probe",
        "numeric_probe",
        "collation_probe",
    ]:
        assert getattr(ColumnOptionsTrial.__table__.c, attribute) is getattr(
            equivalent.__table__.c, attribute
        )


def test_conflicting_foreign_key_options_are_rejected():
    type(
        "ForeignKeyOptionsTrial",
        (StaticTrial,),
        {
            "foreign_key_options_probe": Column(
                Integer,
                ForeignKey("participant.id", ondelete="CASCADE"),
            )
        },
    )

    with pytest.raises(InvalidDefinitionError, match="foreign-key"):
        type(
            "ConflictingForeignKeyOptionsTrial",
            (StaticTrial,),
            {
                "foreign_key_options_probe": Column(
                    Integer,
                    ForeignKey("participant.id", ondelete="SET NULL"),
                )
            },
        )


def test_deferred_custom_columns_reuse_the_inherited_column():
    assert (
        FirstSiblingTrial.__table__.c.sibling_probe
        is DeferredSiblingTrial.__table__.c.sibling_probe
    )


def test_import_local_experiment_does_not_put_the_experiment_directory_on_sys_path():
    experiment_dir = path_to_test_experiment("custom_trial_column")
    with working_directory(experiment_dir):
        before = list(sys.path)
        import_local_experiment()
        assert sys.path == before


@pytest.mark.parametrize(
    "experiment_directory",
    [path_to_test_experiment("custom_trial_column")],
    indirect=True,
)
def test_custom_trial_column_persists_through_the_orm(
    in_experiment_directory,
    db_session,
):
    experiment = get_experiment()
    participant = Participant(
        experiment=experiment,
        recruiter_id="hotair",
        worker_id=str(uuid.uuid4()),
        hit_id=str(uuid.uuid4()),
        assignment_id=str(uuid.uuid4()),
        mode="debug",
    )
    node = StaticNode(
        definition={"probe": True},
        module_id="custom_column_test",
        experiment=experiment,
    )
    trial_class = experiment.__class__.__module__.rsplit(".", 1)[0]
    custom_trial_class = sys.modules[f"{trial_class}.experiment"].CustomColumnTrial
    trial = custom_trial_class(
        experiment=experiment,
        node=node,
        participant=participant,
        propagate_failure=False,
        is_repeat_trial=False,
    )
    trial.item_id = "item-42"
    db.session.add_all([participant, node, trial])
    db.session.commit()
    db.session.expire_all()

    assert custom_trial_class.query.one().item_id == "item-42"
