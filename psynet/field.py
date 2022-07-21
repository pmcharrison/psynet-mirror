import pickle
import re
from datetime import datetime

import flask
import jsonpickle
from sqlalchemy import Boolean, Column, Float, Integer, String, types
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.types import TypeDecorator

from .utils import get_logger

logger = get_logger()
marker = object()


class PythonObject(TypeDecorator):
    @property
    def python_type(self):
        return object

    impl = types.String

    def sanitize(self, value):
        return value

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        sanitized = self.sanitize(value)
        return jsonpickle.encode(sanitized)

    def process_literal_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return jsonpickle.decode(value)


class PythonDict(PythonObject):
    def sanitize(self, value):
        return dict(value)


class PythonList(PythonObject):
    def sanitize(self, value):
        return list(value)


# These classes cannot be reliably pickled by the `jsonpickle` library.
# Instead we fall back to Python's built-in pickle library.
no_json_classes = [flask.Markup]


class NoJSONHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, state):
        state["bytes"] = pickle.dumps(obj, 0).decode("ascii")
        return state

    def restore(self, state):
        return pickle.loads(state["bytes"].encode("ascii"))


for cls in no_json_classes:
    jsonpickle.register(cls, NoJSONHandler)


def register_extra_var(extra_vars, name, overwrite=False, **kwargs):
    if (not overwrite) and (name in extra_vars):
        raise ValueError(f"tried to overwrite the variable {name}")

    extra_vars[name] = {**kwargs}


# Don't apply this decorator to time consuming operations, especially database queries!
def extra_var(extra_vars):
    def real_decorator(function):
        register_extra_var(extra_vars, function.__name__, overwrite=True)
        return function

    return real_decorator


def claim_field(name: str, extra_vars: dict, field_type=object):
    # To do - add new argument corresponding to the default value of the field
    register_extra_var(extra_vars, name, field_type=field_type)

    if field_type is int:
        col = Column(Integer, nullable=True)
    elif field_type is float:
        col = Column(Float, nullable=True)
    elif field_type is bool:
        col = Column(Boolean, nullable=True)
    elif field_type is str:
        col = Column(String, nullable=True)
    elif field_type is list:
        col = Column(MutableList.as_mutable(PythonList), nullable=True)
    elif field_type is dict:
        col = Column(MutableDict.as_mutable(PythonDict), nullable=True)
    elif field_type is object:
        col = Column(PythonObject, nullable=True)
    else:
        raise NotImplementedError

    return col


def claim_var(
    name,
    extra_vars: dict,
    use_default=False,
    default=lambda: None,
    serialise=lambda x: x,
    unserialise=lambda x: x,
):
    @property
    def function(self):
        try:
            return unserialise(getattr(self.var, name))
        except UndefinedVariableError:
            if use_default:
                return default()
            raise

    @function.setter
    def function(self, value):
        setattr(self.var, name, serialise(value))

    register_extra_var(extra_vars, name)

    return function


def check_type(x, allowed):
    match = False
    for t in allowed:
        if isinstance(x, t):
            match = True
    if not match:
        raise TypeError(f"{x} did not have a type in the approved list ({allowed}).")


class UndefinedVariableError(Exception):
    pass


class BaseVarStore:
    def __getattr__(self, name):
        raise NotImplementedError

    def __setattr__(self, key, value):
        raise NotImplementedError

    def get(self, name: str, default=marker):
        """
        Gets a variable with a specified name.

        Parameters
        ----------

        name
            Name of variable to retrieve.

        default
            Optional default value to return when the variable is uninitialized.


        Returns
        -------

        object
            Retrieved variable.

        Raises
        ------

        UndefinedVariableError
            Thrown if the variable doesn't exist and no default value is provided.
        """
        try:
            return self.__getattr__(name)
        except UndefinedVariableError:
            if default == marker:
                raise
            else:
                return default

    def set(self, name, value):
        """
        Sets a variable. Calls can be chained, e.g.
        ``participant.var.set("a", 1).set("b", 2)``.

        Parameters
        ----------

        name
            Name of variable to set.

        value
            Value to assign to the variable.

        Returns
        -------

        VarStore
            The original ``VarStore`` object (useful for chaining).
        """
        self.__setattr__(name, value)
        return self

    def has(self, name):
        """
        Tests for the existence of a variable.

        Parameters
        ----------

        name
            Name of variable to look for.

        Returns
        -------

        bool
            ``True`` if the variable exists, ``False`` otherwise.
        """
        try:
            self.get(name)
            return True
        except UndefinedVariableError:
            return False

    def inc(self, name, value=1):
        """
        Increments a variable. Calls can be chained, e.g.
        ``participant.var.inc("a").inc("b")``.

        Parameters
        ----------

        name
            Name of variable to increment.

        value
            Value by which to increment the varibable (default = 1).

        Returns
        -------

        VarStore
            The original ``VarStore`` object (useful for chaining).

        Raises
        ------

        UndefinedVariableError
            Thrown if the variable doesn't exist.
        """
        original = self.get(name)
        new = original + value
        self.set(name, new)
        return self

    def new(self, name, value):
        """
        Like :meth:`~psynet.field.VarStore.set`, except throws
        an error if the variable exists already.

        Parameters
        ----------

        name
            Name of variable to set.

        value
            Value to assign to the variable.

        Returns
        -------

        VarStore
            The original ``VarStore`` object (useful for chaining).

        Raises
        ------

        UndefinedVariableError
            Thrown if the variable doesn't exist.
        """
        if self.has(name):
            raise ValueError(f"There is already a variable called {name}.")
        self.set(name, value)


class ImmutableVarStore(BaseVarStore, dict):
    def __init__(self, data):
        dict.__init__(self, **data)

    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, key, value):
        raise RuntimeError(
            "The variable store is locked and cannot currently be edited."
        )


class VarStore(BaseVarStore):
    """
    A repository for arbitrary variables which will be serialized to JSON for storage into the
    database, specifically in the ``details`` field. Variables can be set with the following syntax:
    ``participant.var.my_var_name = "value_to_set"``.
    The variable can then be accessed with ``participant.var.my_var_name``.
    See the methods below for an alternative API.

    **TIP 1:** the standard setter function is unavailable in lambda functions,
    which are otherwise convenient to use when defining e.g.
    :class:`~psynet.timeline.CodeBlock` objects.
    Use :meth:`psynet.field.VarStore.set` instead, for example:

    ::

        from psynet.timeline import CodeBlock

        CodeBlock(lambda participant: participant.var.set("my_var", 3))

    **TIP 2:** by convention, the ``VarStore`` object is placed in an object's ``var`` slot.
    You can add a ``VarStore`` object to a custom object (e.g. a Dallinger ``Node``) as follows:

    ::

        from dallinger.models import Node
        from psynet.field import VarStore

        class CustomNode(Node):
            __mapper_args__ = {"polymorphic_identity": "custom_node"}

            @property
            def var(self):
                return VarStore(self)


    **TIP 3:** avoid storing large objects here on account of the performance cost
    of converting to and from JSON.
    """

    def __init__(self, owner):
        self._owner = owner

    def __getattr__(self, name):
        owner = self.__dict__["_owner"]
        if name == "_owner":
            return owner
        elif name == "_all":
            return self.get_vars()
        else:
            return self.get_var(name)

    def encode_to_string(self, obj):
        return jsonpickle.encode(obj)

    def decode_string(self, string):
        return jsonpickle.decode(string)

    def get_var(self, name):
        vars_ = self.get_vars()
        try:
            return self.decode_string(vars_[name])
        except KeyError:
            raise UndefinedVariableError(f"Undefined variable: {name}.")

    def __setattr__(self, name, value):
        if name == "_owner":
            self.__dict__["_owner"] = value
        else:
            self.set_var(name, value)

    def set_var(self, name, value):
        vars_ = self.get_vars()
        value_encoded = self.encode_to_string(value)
        vars_[name] = value_encoded
        self.set_vars(vars_)

    def get_vars(self):
        vars_ = self.__dict__["_owner"].details
        if vars_ is None:
            vars_ = {}
        return vars_.copy()

    def set_vars(self, vars_):
        # We need to copy the dictionary otherwise
        # SQLAlchemy won't notice if we change it later.
        self.__dict__["_owner"].details = vars_.copy()

    def list(self):
        return list(self._all.keys())


def json_clean(x, details=False, contents=False):
    for i in range(5):
        try:
            del x[f"property{i + 1}"]
        except KeyError:
            pass

    if details:
        del x["details"]

    if contents:
        del x["contents"]

    if "metadata_" in x and "metadata" in x:
        del x["metadata_"]


def json_add_extra_vars(x, obj):
    def valid_key(key):
        return not re.search("^_", key)

    for key in obj.__extra_vars__.keys():
        if valid_key(key):
            try:
                val = getattr(obj, key)
            except UndefinedVariableError:
                val = None
            x[key] = val

    if hasattr(obj, "var") and isinstance(obj.var, VarStore):
        for key in obj.var.list():
            if valid_key(key):
                x[key] = obj.var.get(key)

    return x


def json_format_vars(x):
    for key, value in x.items():
        if isinstance(value, datetime):
            new_val = value.strftime("%Y-%m-%d %H:%M")
        elif not (
            (value is None)
            or isinstance(value, (int, float, str, bool, list, datetime))
        ):
            new_val = jsonpickle.encode(value)
        else:
            new_val = value
        x[key] = new_val
