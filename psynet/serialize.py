import pickle
import re

import flask
import jsonpickle
from jsonpickle.unpickler import loadclass

from .data import SQLBase
from .utils import get_custom_sql_classes, import_local_experiment


def serialize(x):
    return jsonpickle.encode(x)


def unserialize(x):
    # If we don't provide the custom classes directly, jsonpickle tries to find them itself,
    # and ends up messing up the SQLAlchemy mapper registration system,
    # producing duplicate mappers for each custom class.
    custom_classes = list(get_custom_sql_classes().values())
    return jsonpickle.decode(x, classes=custom_classes)


# These classes cannot be reliably pickled by the `jsonpickle` library.
# Instead we fall back to Python's built-in pickle library.
no_json_classes = [flask.Markup]


class NoJSONHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, state):
        state["bytes"] = pickle.dumps(obj, 0).decode("ascii")
        return state

    def restore(self, state):
        return pickle.loads(state["bytes"].encode("ascii"))


for _cls in no_json_classes:
    jsonpickle.register(_cls, NoJSONHandler, base=True)


class SQLHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, state):
        primary_key_cols = [c.name for c in obj.__class__.__table__.primary_key.columns]
        primary_keys = {key: getattr(obj, key) for key in primary_key_cols}
        state["identifiers"] = primary_keys
        return state

    def restore(self, state):
        cls_definition = state["py/object"]
        is_custom_cls = cls_definition.startswith("dallinger_experiment")

        if is_custom_cls:
            cls_name = re.sub(".*\\.", "", cls_definition)
            exp = import_local_experiment()
            cls = getattr(exp["module"], cls_name)
        else:
            cls = loadclass(state["py/object"])
        identifiers = state["identifiers"]
        return cls.query.filter_by(**identifiers).one()


jsonpickle.register(SQLBase, SQLHandler, base=True)
