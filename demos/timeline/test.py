import os

import pytest

pytest_plugins = ["pytest_dallinger", "psynet.test"]

experiment_dir = os.path.dirname(__file__)


@pytest.mark.parametrize("experiment_directory", [experiment_dir], indirect=True)
def test_experiment(launched_experiment):
    launched_experiment.test_experiment()
