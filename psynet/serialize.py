import inspect
import pickle
import re
import warnings
from functools import cached_property

import dominate.tags
import jsonpickle
import jsonpickle.ext.numpy as jsonpickle_numpy
from jsonpickle import Pickler
from jsonpickle.unpickler import Unpickler, loadclass
from jsonpickle.util import importable_name
from markupsafe import Markup

from .data import SQLBase
from .utils import get_logger

logger = get_logger()


# Without jsonpickle.ext.numpy.register_handlers(), numpy arrays are serialized very verbosely, e.g.
# >>> serialize(np.array([1, 2, 3]))
# '{"py/reduce": [{"py/function": "numpy._core.multiarray._reconstruct"}, {"py/tuple": [{"py/type": "numpy.ndarray"},
# {"py/tuple": [0]}, {"py/b64": "Yg=="}]}, {"py/tuple": [1, {"py/tuple": [3]}, {"py/reduce": [{"py/type":
# "numpy.dtype"}, {"py/tuple": ["i8", false, true]}, {"py/tuple": [3, "<", null, null, null, -1, -1, 0]}]}, false,
# {"py/b64": "AQAAAAAAAAACAAAAAAAAAAMAAAAAAAAA"}]}]}'
#
# With jsonpickle.ext.numpy.register_handlers(), we get a much more concise representation:
# >>> serialize(np.array([1, 2, 3]))
# '{"py/object": "numpy.ndarray", "dtype": "int64", "values": [1, 2, 3]}'
jsonpickle_numpy.register_handlers()


def is_lambda_function(x):
    return callable(x) and hasattr(x, "__name__") and x.__name__ == "<lambda>"


class PsyNetPickler(Pickler):
    def flatten(self, obj, reset=True):
        if is_lambda_function(obj):
            try:
                source_file, source_line = (
                    obj.__code__.co_filename,
                    obj.__code__.co_firstlineno,
                )
            except Exception as e:
                source_file, source_line = "UNKNOWN", "UNKNOWN"
                logger.error(
                    msg="Failed to find source code for lambda function.", exc_info=e
                )
            raise TypeError(
                "Cannot pickle lambda functions. "
                "Can you replace this function with a named function defined by `def`?\n"
                f"The problematic function was defined in {source_file} "
                f"on line {source_line}."
            )
        else:
            return super().flatten(obj, reset=reset)


class PsyNetUnpickler(Unpickler):
    """
    The PsyNetUnpickler class
    """

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
        res = cls.query.filter_by(**identifiers).one_or_none()
        if res is None:
            warnings.warn(
                f"The unserializer failed to find the following object in the database: {obj}. "
                "Returning `None` instead."
            )
        return res

    @cached_property
    def experiment(self):
        from .experiment import import_local_experiment

        return import_local_experiment()


def serialize(x, **kwargs):
    pickler = PsyNetPickler()
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message="jsonpickle cannot pickle")
        return jsonpickle.encode(x, **kwargs, context=pickler, warn=True)


def to_dict(x):
    pickler = PsyNetPickler()
    return pickler.flatten(x)


def unserialize(x):
    # If we don't provide the custom classes directly, jsonpickle tries to find them itself,
    # and ends up messing up the SQLAlchemy mapper registration system,
    # producing duplicate mappers for each custom class.
    # import_local_experiment()
    # custom_classes = list(get_custom_sql_classes().values())
    # return jsonpickle.decode(x, context=unpickler, classes=custom_classes)
    unpickler = PsyNetUnpickler()
    return jsonpickle.decode(x, context=unpickler)
    # return jsonpickle.decode(x, classes=custom_classes)


# These classes cannot be reliably pickled by the `jsonpickle` library.
# Instead we fall back to Python's built-in pickle library.
no_json_classes = [Markup]


class NoJSONHandler(jsonpickle.handlers.BaseHandler):
    """
    The NoJSONHandler class
    """

    def flatten(self, obj, state):
        state["bytes"] = pickle.dumps(obj, 0).decode("latin-1")
        return state

    def restore(self, state):
        return pickle.loads(state["bytes"].encode("latin-1"))


for _cls in no_json_classes:
    jsonpickle.register(_cls, NoJSONHandler, base=True)


class SQLHandler(jsonpickle.handlers.BaseHandler):
    """
    The SQLHandler class
    """

    def get_primary_keys(self, obj):
        primary_key_cols = [c.name for c in obj.__class__.__table__.primary_key.columns]
        return {key: getattr(obj, key) for key in primary_key_cols}

    def flatten(self, obj, state):
        primary_keys = self.get_primary_keys(obj)
        if any(key is None for key in primary_keys.values()):
            raise ValueError(
                f"Cannot serialize {obj}. It has a `None` value for one of its primary keys: {primary_keys}. "
                "It might be possible to solve this problem by introducing a `db.session.flush()` call before pickling."
            )
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


class DominateHandler(jsonpickle.handlers.BaseHandler):
    """
    The DominateHandler class
    """

    def flatten(self, obj, state):
        return str(obj)


jsonpickle.register(dominate.dom_tag.dom_tag, DominateHandler, base=True)


def prepare_function_for_serialization(function, arguments):
    if inspect.ismethod(function):
        method_name = function.__name__
        method_caller = function.__self__
        if isinstance(method_caller, type):
            function, arguments = prepare_class_method_for_serialization(
                function, arguments
            )
        else:
            function, arguments = prepare_instance_method_for_serialization(
                method_caller, method_name, arguments
            )

    check_that_function_can_be_serialized(function)

    return function, arguments


def prepare_class_method_for_serialization(function, arguments):
    """
    Prepares a class method for serialization by jsonpickle.
    This is necessary because jsonpickle can't serialize class methods directly.
    Instead, we serialize the underlying function.
    """
    # Since we are converting the class method into an ordinary function, I had thought we would need to add `cls`
    # to the arguments, but it turns out that when jsonpickle unserializes the function, it automatically turns
    # it back into a classmethod, so we don't need to do this after all.
    function = function.__func__
    return function, arguments


def prepare_instance_method_for_serialization(method_caller, method_name, arguments):
    """
    Prepares an instance method for serialization by jsonpickle.
    This is necessary because jsonpickle can't serialize instance methods directly.
    Instead, we turn it into an ordinary function where ``self`` is an argument.
    """
    function = getattr(method_caller.__class__, method_name)
    arguments["self"] = method_caller
    return function, arguments


def check_that_function_can_be_serialized(function):
    assert callable(function)
    if "<locals>" in importable_name(function):
        raise ValueError(
            "You cannot serialize a lambda function or a function defined within another function."
        )
