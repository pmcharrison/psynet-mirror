import re
import warnings

import pytest

from psynet.pytest_psynet import path_to_test_experiment
from psynet.utils import get_config

get_config


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_warnings_during_launch(self, debug_experiment):
        pattern = r"[^\n]*Warning: [^\n\r]*"
        warnings = re.findall(pattern, debug_experiment.before)
        if len(warnings) > 0:
            raise AssertionError(
                f"Encountered a warning in experiment launch: {warnings[0]}"
            )

    def test_warnings_during_experiment(self, launched_experiment):
        with warnings.catch_warnings():
            warnings.simplefilter("error", Warning)
            launched_experiment.test_experiment()
