import jsonpickle
import pytest

import psynet.field  # noqa
from psynet.trial.static import StaticTrial, Stimulus


@pytest.mark.usefixtures("demo_static")
def test_jsonpickle_sql(trial, node, network, participant):
    trial_pickled = jsonpickle.encode(trial)
    assert (
        trial_pickled
        == '{"py/object": "dallinger_experiment.experiment.AnimalTrial", "identifiers": {"id": 1}}'
    )

    trial_unpickled = jsonpickle.decode(trial_pickled, reset=False)
    assert isinstance(trial_unpickled, StaticTrial)
    assert trial.id == 1
    assert isinstance(trial.origin, Stimulus)
