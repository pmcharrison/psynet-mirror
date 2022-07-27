import pytest

import psynet.field  # noqa
from psynet.serialize import serialize, unserialize
from psynet.trial.static import StaticTrial, Stimulus
from psynet.utils import get_custom_sql_classes


@pytest.mark.usefixtures("demo_static")
class Test:
    def test_custom_sql_classes(self, trial, node, network, participant):
        classes = get_custom_sql_classes()

        desired = [
            "AnimalTrial",
        ]

        assert desired == list(classes.keys())
        assert desired == list([c.__name__ for c in classes.values()])

    def test_config(self, trial, node, network, participant):
        # Checking that loading Dallinger config doesn't mess up the mappers in the way it used to
        self.check_mappers()

        from dallinger.config import get_config

        config = get_config()

        if not config.ready:
            config.load()

        self.check_mappers()

    def test_serialize_sql(self, trial, node, network, participant):
        # from psynet.utils import

        trial_serialized = serialize(trial)
        assert (
            trial_serialized
            == '{"py/object": "dallinger_experiment.experiment.AnimalTrial", "identifiers": {"id": 1}}'
        )

        trial_unserialized = unserialize(trial_serialized)
        assert isinstance(trial_unserialized, StaticTrial)
        assert trial.id == 1
        assert isinstance(trial.origin, Stimulus)

        self.check_mappers()

    # def test_serialize_method(self, trial):
    #     method_serialized = serialize(trial.show_trial)
    #
    #     import pydevd_pycharm
    #     pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)

    def check_mappers(self):
        # If we don't manage the imports correctly, we can end up with a nasty bug where
        # SQLAlchemy ends up registering two mappers for every class in experiment.py.
        # The following test catches such cases.
        from dallinger.db import Base

        animal_trial_mappers = [
            m for m in Base.registry.mappers if m.class_.__name__ == "AnimalTrial"
        ]
        assert len(animal_trial_mappers) == 1
