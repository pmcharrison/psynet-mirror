import copy
import re

from sqlalchemy import Boolean, String, Integer, Float
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast
from datetime import datetime

import json

from .utils import get_logger
logger = get_logger()

def claim_field(db_index, field_type=object):
    if field_type is int:
        return IntField(db_index).function
    elif field_type is float:
        return FloatField(db_index).function
    elif field_type is bool:
        return BoolField(db_index).function
    elif field_type is str:
        return StrField(db_index).function
    elif field_type is dict:
        return DictField(db_index).function
    elif field_type is list:
        return ListField(db_index).function
    elif field_type is object:
        return ObjectField(db_index).function
    else:
        raise NotImplementedError

class Field():
    def __init__(self, db_index, from_db, to_db, permitted_python_types, sql_type, null_value=lambda: None):
        assert 1 <= db_index and db_index <= 5
        db_field = f"property{db_index}"

        @hybrid_property
        def function(self):
            val = getattr(self, db_field)
            if val is None:
                return null_value()
            else:
                return from_db(val)

        @function.setter
        def function(self, value):
            if value is null_value():
                db_value = None
            else:
                check_type(value, permitted_python_types)
                db_value = to_db(value)
            setattr(self, db_field, db_value)

        @function.expression
        def function(self):
            return cast(getattr(self, db_field), sql_type)

        self.function = function

def claim_var(
        name,
        extra_vars: dict,
        use_default=False,
        default=lambda: None,
        serialise=lambda x: x,
        unserialise=lambda x: x,
        overwrite=False
    ):
    if name in extra_vars and not overwrite:
        raise ValueError(f"tried to overwrite the variable {name} but overwrite was False")

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

    extra_vars[name] = {
        "function": function
    }

    return function

def check_type(x, allowed):
    match = False
    for t in allowed:
        if isinstance(x, t):
            match = True
    if not match:
        raise TypeError(f"{x} did not have a type in the approved list ({allowed}).")

class IntField(Field):
    def __init__(self, db_index):
        super().__init__(db_index, from_db=int, to_db=int, permitted_python_types=[int], sql_type=Integer)

class FloatField(Field):
    def __init__(self, db_index):
        super().__init__(db_index, from_db=float, to_db=float, permitted_python_types=[int, float], sql_type=Float)

class BoolField(Field):
    def __init__(self, db_index):
        def from_db(x):
            if x == "True":
                return True
            elif x == "False":
                return False
            else:
                raise TypeError(f"Invalid value for BoolField: '{x}'.")

        def to_db(x):
            # return repr(int(x))
            return repr(bool(x))

        super().__init__(db_index, from_db, to_db, [bool], Boolean)

class StrField(Field):
    def __init__(self, db_index):
        super().__init__(db_index, from_db=str, to_db=str, permitted_python_types=[str], sql_type=String)

class DictField(Field):
    def __init__(self, db_index):
        super().__init__(
            db_index,
            from_db=json.loads,
            to_db=json.dumps,
            permitted_python_types=[dict],
            sql_type=String,
            null_value=lambda: {}
        )

class ListField(Field):
    def __init__(self, db_index):
        super().__init__(
            db_index,
            from_db=json.loads,
            to_db=json.dumps,
            permitted_python_types=[list],
            sql_type=String,
            null_value=lambda: []
        )

class ObjectField(Field):
    def __init__(self, db_index):
        super().__init__(
            db_index,
            from_db=json.loads,
            to_db=json.dumps,
            permitted_python_types=[object],
            sql_type=String
        )

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

    **WARNING 1:** avoid in-place modification (e.g. ``participant.var.my_var_name[3] = "d"``),
    as such modifications will (probably) not get propagated to the database.
    Support could be added in the future if Dallinger takes advantage of
    `mutable structures in SQLAlchemy <https://docs.sqlalchemy.org/en/13/orm/extensions/mutable.html#module-sqlalchemy.ext.mutable>`_.

    **WARNING 2:** avoid storing large objects here on account of the performance cost
    of converting to and from JSON.
    """
    def __init__(self, owner):
        self._owner = owner

    def __getattr__(self, name):
        owner = self.__dict__["_owner"]
        if name == "_owner":
            return owner
        try:
            return copy.deepcopy(owner.details[name])
        except KeyError:
            raise UndefinedVariableError(f"Undefined variable: {name}.")

    def __setattr__(self, name, value):
        if name == "_owner":
            self.__dict__["_owner"] = value
        else:
            # We need to copy the dictionary otherwise
            # SQLAlchemy won't notice that we changed it.
            all_vars = self.__dict__["_owner"].details
            if all_vars is None:
                all_vars = {}
            all_vars = all_vars.copy()
            all_vars[name] = value
            self.__dict__["_owner"].details = all_vars

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

def json_clean(x, details=False, contents=False):
    for i in range(5):
        del x[f"property{i + 1}"]

    del x["object_type"]

    if details:
        del x["details"]

    if contents:
        del x["contents"]

def json_add_extra_vars(x, obj):
    for key in obj.__extra_vars__.keys():
        if not re.search("^__", key):
            try:
                val = getattr(obj, key)
            except UndefinedVariableError:
                val = None
            x[key] = val
    return x

def json_format_vars(x):
    for key, value in x.items():
        if not isinstance(value, (int, float, str, bool, datetime)):
            x[key] = json.dumps(value)
        elif isinstance(value, datetime):
            x[key] = value.strftime("%Y-%m-%d %H:%M")

