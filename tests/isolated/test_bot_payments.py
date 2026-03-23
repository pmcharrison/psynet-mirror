from types import SimpleNamespace

import pytest

from psynet.experiment import Experiment
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_demo_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo_experiment("hello_world")], indirect=True
)
def test_bot_payments_are_persisted(launched_experiment):
    launched_experiment.test_experiment()

    participant = Participant.query.one()
    assert participant.base_payment is not None
    assert participant.bonus is not None


def test_default_test_experiment_enforces_soft_max_payment(monkeypatch):
    calls = []
    dummy = SimpleNamespace(
        test_mode="serial",
        test_n_bots=1,
        var=SimpleNamespace(soft_max_experiment_payment=999.0),
        _test_experiment_serial=lambda: calls.append("serial"),
        _test_experiment_parallel=lambda: calls.append("parallel"),
        _report_request_statistics=lambda: calls.append("stats"),
        amount_spent=lambda: 2.5,
    )

    monkeypatch.setattr(
        "psynet.experiment.get_config",
        lambda: SimpleNamespace(get=lambda key, default=None: 2.0),
    )

    with pytest.raises(AssertionError):
        Experiment.test_experiment(dummy)

    assert calls == ["serial", "stats"]
