import pytest
import requests

from psynet.pytest_psynet import path_to_demo


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_protected_routes(self):
        host = "http://localhost:5000"
        test_routes = [
            "/network/1",
            "/node/1/neighbors",
        ]
        for route in test_routes:
            url = host + route
            result = requests.get(url)
            assert result.status_code == 500  # Access forbidden
