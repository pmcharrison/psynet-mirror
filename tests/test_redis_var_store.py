import pytest

from psynet.redis import RedisVarStore


@pytest.mark.parametrize("experiment_directory", ["../demos/mcmpc"], indirect=True)
class TestExp:
    def test_redis(self, active_config, debug_experiment):
        store = RedisVarStore()
        store.set("x", [1, 2, 3])

        store = RedisVarStore()
        assert store.get("x") == [1, 2, 3]

        with pytest.raises(KeyError):
            store.get("y")

        assert store.get("y", default=[1, 2, 3]) == [1, 2, 3]
