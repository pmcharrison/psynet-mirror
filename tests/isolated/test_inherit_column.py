import pytest
from sqlalchemy import Column, String
from sqlalchemy.exc import ArgumentError

from psynet.field import inherit_column
from psynet.trial.static import StaticTrial


class InheritColumnBareFirst(StaticTrial):
    time_estimate = 1
    bare_probe_id = Column(String)

    def show_trial(self, experiment, participant):
        pass


def test_bare_column_conflicts_when_info_already_has_the_name():
    assert "bare_probe_id" in InheritColumnBareFirst.__table__.c

    with pytest.raises(ArgumentError, match="conflicts with existing column"):

        class InheritColumnBareSecond(StaticTrial):
            time_estimate = 1
            bare_probe_id = Column(String)

            def show_trial(self, experiment, participant):
                pass


class InheritColumnHelperFirst(StaticTrial):
    time_estimate = 1
    helper_probe_id = inherit_column(String, index=True)

    def show_trial(self, experiment, participant):
        pass


class InheritColumnHelperSecond(StaticTrial):
    time_estimate = 1
    helper_probe_id = inherit_column(String)

    def show_trial(self, experiment, participant):
        pass


def test_inherit_column_reuses_an_existing_info_column():
    assert (
        InheritColumnHelperFirst.__table__.c.helper_probe_id
        is InheritColumnHelperSecond.__table__.c.helper_probe_id
    )
