import psynet.experiment  # noqa: F401
from dallinger.experiment import EXPERIMENT_TASK_REGISTRATIONS


def _scheduled_task_kwargs(func_name):
    registrations = [
        registration
        for registration in EXPERIMENT_TASK_REGISTRATIONS
        if registration.get("func_name") == func_name
    ]
    assert len(registrations) == 1
    return dict(registrations[0]["kwargs"])


def test_check_barriers_tolerates_one_stale_scheduler_instance():
    kwargs = _scheduled_task_kwargs("_check_barriers")

    assert kwargs["coalesce"] is True
    assert kwargs["max_instances"] == 2
    assert kwargs["misfire_grace_time"] is None
    assert kwargs["seconds"] == 0.5
