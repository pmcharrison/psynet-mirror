from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from psynet.experiment import Experiment


def test_status_and_backups_skips_before_launch_finished():
    with (
        patch("psynet.db.transaction", return_value=nullcontext()),
        patch("psynet.experiment.is_experiment_launched", return_value=False),
        patch("psynet.experiment.get_experiment") as get_experiment,
    ):
        Experiment.status_and_backups()

    get_experiment.assert_not_called()


def test_get_hardware_status_handles_unavailable_cpu_frequency():
    """macOS can fail to read HW_CPU_FREQ; status reporting should continue."""

    config = {
        "mute_same_warning_for_n_hours": 1,
        "resource_warning_pct": 0.95,
        "resource_danger_pct": 0.99,
        "minimal_disk_space_warning_gb": 1,
        "minimal_disk_space_danger_gb": 0.5,
    }
    with (
        patch("psynet.experiment.psutil.cpu_freq", side_effect=FileNotFoundError),
        patch("psynet.experiment.psutil.cpu_count", return_value=4),
        patch("psynet.experiment.psutil.cpu_percent", return_value=3.0),
        patch(
            "psynet.experiment.psutil.virtual_memory",
            return_value=SimpleNamespace(total=16 * 1024**3, percent=20.0),
        ),
        patch(
            "psynet.experiment.psutil.disk_usage",
            return_value=SimpleNamespace(
                total=512 * 1024**3,
                free=256 * 1024**3,
                percent=50.0,
            ),
        ),
        patch("psynet.experiment.get_config", return_value=config),
    ):
        status = Experiment.get_hardware_status()

    assert status["cpu_specs"] == "4x @ N/A"
    assert status["cpu_usage_pct"] == 3.0
