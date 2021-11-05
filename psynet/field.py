import copy
import json
import jsonpickle
import re
from datetime import datetime

from sqlalchemy import Boolean, Column, Float, Integer, String, TypeDecorator, types
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import JSONB

from .utils import get_logger

logger = get_logger()


class PythonObject(TypeDecorator):

    @property
    def python_type(self):
        return object

    impl = types.String

    def process_bind_param(self, value, dialect):
        return jsonpickle.encode(value)

    def process_literal_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return jsonpickle.decode(value)


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


class VarStore:
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
    The :class:`psynet.participant.Participant` object comes with one by default
    (unfortunately the :class:`psynet.experiment.Experiment` object doesn't,
    because it is not stored in the database).
    You can add a ``VarStore`` object to a custom object (e.g. a Dallinger ``Node``) as follows:

    ::

        from dallinger.models import Node
        from psynet.field import VarStore

        class CustomNode(Node):
            __mapper_args__ = {"polymorphic_identity": "custom_node"}

            @property
            def var(self):
                return VarStore(self)


    **WARNING:** avoid storing large objects here on account of the performance cost
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

    def get(self, name: str, unserialise: bool = True):
        """
        Gets a variable with a specified name.

        Parameters
        ----------

        name
            Name of variable to retrieve.


        Returns
        -------

        object
            Retrieved variable.

        Raises
        ------

        UndefinedVariableError
            Thrown if the variable doesn't exist.
        """
        return self.__getattr__(name)

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

    def list(self):
        return list(self._all.keys())


def json_clean(x, details=False, contents=False):
    for i in range(5):
        del x[f"property{i + 1}"]

    if details:
        del x["details"]

    if contents:
        del x["contents"]


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
            new_val = json.dumps(value)
        else:
            new_val = value
        x[key] = new_val
