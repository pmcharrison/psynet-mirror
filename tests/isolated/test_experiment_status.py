from unittest.mock import patch

from psynet.experiment import Experiment


def test_record_experiment_status_skips_before_launch_metadata():
    with patch("psynet.experiment.redis_vars.get", return_value=None):
        with patch.object(Experiment, "get_status") as get_status:
            with patch("psynet.experiment.db.session.add") as add:
                Experiment.record_experiment_status()

    get_status.assert_not_called()
    add.assert_not_called()
