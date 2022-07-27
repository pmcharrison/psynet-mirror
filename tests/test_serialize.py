import pytest

import psynet.field  # noqa
from psynet.serialize import serialize, unserialize
from psynet.trial.static import StaticTrial, Stimulus


@pytest.mark.usefixtures("demo_static")
class Test:
    def test_config(self, trial, node, network, participant):
        # Checking that loading Dallinger config doesn't mess up the mappers in the way it used to
        self.check_mappers()

        from dallinger.config import get_config

        config = get_config()

        if not config.ready:
            config.load()

        self.check_mappers()

    def test_serialize_sql(self, trial, node, network, participant):
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

    def check_mappers(self):
        # If we don't manage the imports correctly, we can end up with a nasty bug where
        # SQLAlchemy ends up registering two mappers for every class in experiment.py.
        # The following test catches such cases.
        from dallinger.db import Base

        animal_trial_mappers = [
            m for m in Base.registry.mappers if m.class_.__name__ == "AnimalTrial"
        ]
        assert len(animal_trial_mappers) == 1
