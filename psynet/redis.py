import jsonpickle
from dallinger.db import redis_conn

from .utils import NoArgumentProvided


class RedisVarStore:
    def get(self, name, default=NoArgumentProvided):
        raw = redis_conn.get(name)
        if raw is None:
            if default == NoArgumentProvided:
                raise KeyError
            else:
                return default
        return jsonpickle.decode(raw.decode("utf-8"))

    def set(self, name, value):
        redis_conn.set(name, jsonpickle.encode(value))

    def clear(self):
        for key in redis_conn.keys():
            redis_conn.delete(key)


redis_vars = RedisVarStore()
