from dallinger.experiment import EXPERIMENT_TASK_REGISTRATIONS

from psynet.experiment import scheduled_task


def _registered_task_kwargs(func_name):
    """Return scheduler keyword arguments for a registered task."""
    task = next(
        task
        for task in EXPERIMENT_TASK_REGISTRATIONS
        if task.get("func_name") == func_name
    )
    return dict(task["kwargs"])


def test_scheduled_task_defaults_to_unlimited_misfire_grace_time(tasks_with_cleanup):
    @scheduled_task("interval", seconds=1, max_instances=1)
    def task_with_default_misfire_grace_time():
        pass

    assert (
        _registered_task_kwargs("task_with_default_misfire_grace_time")[
            "misfire_grace_time"
        ]
        is None
    )


def test_scheduled_task_preserves_explicit_misfire_grace_time(tasks_with_cleanup):
    @scheduled_task("interval", seconds=1, max_instances=1, misfire_grace_time=5)
    def task_with_explicit_misfire_grace_time():
        pass

    assert (
        _registered_task_kwargs("task_with_explicit_misfire_grace_time")[
            "misfire_grace_time"
        ]
        == 5
    )


def test_check_barriers_uses_unlimited_misfire_grace_time():
    assert _registered_task_kwargs("_check_barriers")["misfire_grace_time"] is None
