import pytest

from psynet.redis import RedisVarStore


@pytest.mark.usefixtures("demo_mcmcp")
class TestExp:
    def test_redis(self, active_config, debug_experiment):
        store = RedisVarStore()
        store.x = [1, 2, 3]

        store = RedisVarStore()
        assert store.x == [1, 2, 3]

        with pytest.raises(KeyError):
            store.y
