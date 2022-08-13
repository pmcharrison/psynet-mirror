import os
import pytest
import psynet.test  # noqa -- registers test fixtures

experiment_dir = os.path.dirname(__file__)

@pytest.mark.parametrize("experiment_directory", [experiment_dir], indirect=True)
def test_experiment(launched_experiment):