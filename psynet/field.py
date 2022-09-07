import re
from datetime import datetime

from sqlalchemy import Boolean, Column, Float, Integer, String, types
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.types import TypeDecorator

from .serialize import serialize, unserialize
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
        try:
            return self.serialize(value)
        except Exception:
            logger.error(
                f"An error occurred when trying to serialize the following Python object to the database: {value}"
            )
            raise

    def process_literal_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return self.unserialize(value)
        except Exception:
            pass

    @classmethod
    def serialize(cls, value):
        return serialize(value)

    @classmethod
    def unserialize(cls, value):
        return unserialize(value)


class _PythonList(PythonObject):
    def serialize(self, value):
        return super().serialize(list(value))


PythonList = MutableList.as_mutable(_PythonList)


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
        col = Column(PythonList, nullable=True)
    elif field_type is dict:
        col = Column(PythonDict, nullable=True)
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
        except KeyError:
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

        KeyError
            Thrown if the variable doesn't exist and no default value is provided.
        """
        try:
            return self.__getattr__(name)
        except KeyError:
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
        except KeyError:
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

        KeyError
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

        KeyError
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

    def __repr__(self):
        # data = {
        #     key: self.decode_string(value) for key, value in self.get_vars().items()
        # }
        return f"VarStore: {self.__dict__['_owner'].vars}"

    def __getattr__(self, name):
        owner = self.__dict__["_owner"]
        if name == "_owner":
            return owner
        else:
            data = self.__dict__["_owner"].vars
            if data is None:
                raise KeyError("The VarStore has not been initialized yet")
            else:
                return data[name]

    def items(self):
        return self.__dict__["_owner"].vars.items()

    def __setattr__(self, name, value):
        if name == "_owner":
            self.__dict__["_owner"] = value
        else:
            if self.__dict__["_owner"].vars is None:
                self.__dict__["_owner"].vars = {}
            self.__dict__["_owner"].vars[name] = value
            # self[name] = value
            # self.set_var(name, value)


# class DotDict(dict, BaseVarStore):
#     def __setattr__(self, key, value):
#         self[key] = value
#
#     def __getattr__(self, key):
#         return self[key]
#
#
# class _PythonDotDict(_PythonDict):
#     def unserialize(cls, value):
#         return DotDict(super().unserialize(value))
#
#
# PythonDotDict = MutableDict.as_mutable(_PythonDotDict)


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


def json_unpack_answer(x):
    if "answer" in x and isinstance(x["answer"], dict):
        answer = x["answer"]
        del x["answer"]
        for key, value in answer.items():
            x[f"answer__{key}"] = value

    return x


def json_add_extra_vars(x, obj):
    def valid_key(key):
        return not re.search("^_", key)

    for key in obj.__extra_vars__.keys():
        if valid_key(key):
            try:
                val = getattr(obj, key)
            except KeyError:
                val = None
            x[key] = val

    if hasattr(obj, "var") and isinstance(obj.var, VarStore):
        for key, value in obj.var.items():
            if valid_key(key):
                x[key] = value

    return x


def is_basic_type(value):
    return value is None or isinstance(value, (int, float, str, bool))


def json_format_vars(x):
    for key, value in x.items():
        # TODO - revisit this? Will need some concurrent edits in Dallinger,
        # e.g. the logic for sending __json__() outputs to the dashboard.
        if isinstance(value, datetime):
            value = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, MutableList):
            value = list(value)
        elif isinstance(value, MutableDict):
            value = dict(value)

        # if not is_basic_type(value):
        #     value = serialize(value)

        x[key] = value


# class MutableDotDict(MutableDict, dict, BaseVarStore):
#     def __setattr__(self, key, value):
#         if self.is_internal(key):
#             super().__setattr__(key, value)
#         else:
#             self[key] = value
#
#     def __getattr__(self, item):
#         if self.is_internal(item):
#             return super().__getattr__(item)
#         return self[item]
#
#     def is_internal(self, key):
#         return key.startswith("_")


class _PythonDict(PythonObject):
    def serialize(cls, value):
        return super().serialize(dict(value))


PythonDict = MutableDict.as_mutable(_PythonDict)
