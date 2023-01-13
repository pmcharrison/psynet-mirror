import pickle
import re
from functools import cached_property

import flask
import jsonpickle
from jsonpickle import Pickler
from jsonpickle.unpickler import Unpickler, loadclass

from .data import SQLBase

# old_loadclass = jsonpickle.unpickler.loadclass
#
#
# def check_mappers():
#     # If we don't manage the imports correctly, we can end up with a nasty bug where
#     # SQLAlchemy ends up registering two mappers for every class in experiment.py.
#     # The following test catches such cases.
#     from dallinger.db import Base
#
#     animal_trial_mappers = [
#         m for m in Base.registry.mappers if m.class_.__name__ == "AnimalTrial"
#     ]
#     assert len(animal_trial_mappers) == 1
#
#
# def loadclass(module_and_name, classes=None):
#     check_mappers()
#     old_loadclass(module_and_name, classes)
#     check_mappers()


jsonpickle.unpickler.loadclass = loadclass


class PsyNetUnpickler(Unpickler):
    # def _restore(self, obj):
    #     print(obj)
    #     if isinstance(obj, dict) and "py/object" in obj:
    #         if obj["py/object"].startswith("dallinger_experiment"):
    #             cls = self.get_experiment_object(obj["py/object"])
    #             if hasattr(cls, "_sa_registry"):
    #                 return self.load_sql_object(cls, obj)
    #             else:
    #                 self.register_classes(cls)
    #                 return super()._restore(obj)
    #
    #     if isinstance(obj, dict) and "py/function" in obj:
    #         if obj["py/function"].startswith("dallinger_experiment"):
    #             return self.get_experiment_object(obj["py/function"])
    #
    #             # import pydevd_pycharm
    #             # pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)
    #
    #     return super()._restore(obj)

    def _restore_object(self, obj):
        cls_id = obj["py/object"]
        if cls_id.startswith("dallinger_experiment"):
            cls = self.get_experiment_object(cls_id)
        else:
            cls = loadclass(cls_id)
        is_sql_object = hasattr(cls, "_sa_registry")
        if is_sql_object:
            return self.load_sql_object(cls, obj)
        else:
            self.register_classes(cls)
            return super()._restore_object(obj)

    def _restore_function(self, obj):
        if isinstance(obj, dict) and "py/function" in obj:
            if obj["py/function"].startswith("dallinger_experiment"):
                return self.get_experiment_object(obj["py/function"])
        return super()._restore_function(obj)

    def get_experiment_object(self, spec):
        split = spec.split(".")
        package_spec = split[0]
        remainder_spec = split[1:]

        assert package_spec == "dallinger_experiment"

        current = self.experiment["package"]
        for x in remainder_spec:
            current = getattr(current, x)

        return current

    def load_sql_object(self, cls, obj):
        identifiers = obj["identifiers"]
        return cls.query.filter_by(**identifiers).one()

    @cached_property
    def experiment(self):
        from .experiment import import_local_experiment

        return import_local_experiment()


def serialize(x, **kwargs):
    return jsonpickle.encode(x, **kwargs)


pickler = Pickler()


def to_dict(x):
    return pickler.flatten(x)


def unserialize(x):
    # If we don't provide the custom classes directly, jsonpickle tries to find them itself,
    # and ends up messing up the SQLAlchemy mapper registration system,
    # producing duplicate mappers for each custom class.
    # import_local_experiment()
    # custom_classes = list(get_custom_sql_classes().values())
    unpickler = PsyNetUnpickler()
    # return jsonpickle.decode(x, context=unpickler, classes=custom_classes)
    return jsonpickle.decode(x, context=unpickler)
    # return jsonpickle.decode(x, classes=custom_classes)


# These classes cannot be reliably pickled by the `jsonpickle` library.
# Instead we fall back to Python's built-in pickle library.
no_json_classes = [flask.Markup]


class NoJSONHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, state):
        state["bytes"] = pickle.dumps(obj, 0).decode("latin-1")
        return state

    def restore(self, state):
        return pickle.loads(state["bytes"].encode("latin-1"))


for _cls in no_json_classes:
    jsonpickle.register(_cls, NoJSONHandler, base=True)


class SQLHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, state):
        primary_key_cols = [c.name for c in obj.__class__.__table__.primary_key.columns]
        primary_keys = {key: getattr(obj, key) for key in primary_key_cols}
        state["identifiers"] = primary_keys
        return state

    def restore(self, state):
        from .experiment import import_local_experiment

        raise RuntimeError("This should not be called directly")

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
