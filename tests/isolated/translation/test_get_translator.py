# Test that calling get_translator within the PsyNet package returns a translator linked to the
# PsyNet locales directory.
import pytest

from psynet.experiment import import_local_experiment
from psynet.pytest_psynet import path_to_test_experiment
from psynet.utils import _get_translator_called_within_psynet


def test_get_translator_within_psynet():
    _ = _get_translator_called_within_psynet()
    assert _.namespace == "psynet"


# Test that calling get_translator within an experiment directory returns a translator linked to the
# experiment's locales directory.
@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("translation")], indirect=True
)
@pytest.mark.usefixtures("in_experiment_directory")
def test_get_translator_within_experiment():
    experiment_module = import_local_experiment()["module"]
    translator = experiment_module._
    assert translator.namespace == "experiment"
