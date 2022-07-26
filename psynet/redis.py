import jsonpickle
from dallinger.db import redis_conn


class RedisVarStore:
    def __getattr__(self, name):
        raw = redis_conn.get(name)
        if raw is None:
            raise KeyError
        return jsonpickle.decode(raw.decode("utf-8"))

    def __setattr__(self, name, value):
        redis_conn.set(name, jsonpickle.encode(value))
