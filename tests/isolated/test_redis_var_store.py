import pytest

from psynet.pytest_psynet import path_to_test_experiment
from psynet.redis import RedisVarStore


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_redis(self):
        store = RedisVarStore()
        store.set("x", [1, 2, 3])

        store = RedisVarStore()
        assert store.get("x") == [1, 2, 3]

        with pytest.raises(KeyError):
            store.get("y")

        assert store.get("y", default=[1, 2, 3]) == [1, 2, 3]
