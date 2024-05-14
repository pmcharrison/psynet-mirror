import pytest
import requests

from psynet.experiment import get_experiment
from psynet.pytest_psynet import path_to_test_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
def test_app_deployment_id(launched_experiment):
    exp = get_experiment()
    id_1 = exp.deployment_id
    id_2 = requests.get("http://localhost:5000/app_deployment_id").text
    assert id_1 == id_2
