import pytest
import requests

from psynet.experiment import get_experiment


@pytest.mark.usefixtures("demo_mcmcp")
def test_app_deployment_id(debug_experiment):
    exp = get_experiment()
    id_1 = exp.deployment_id
    id_2 = requests.get("http://localhost:5000/app_deployment_id").text
    assert id_1 == id_2
