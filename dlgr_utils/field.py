from sqlalchemy import Boolean, String, Integer, Float
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

import json

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

def claim_var(name):
    @property
    def function(self):
        return getattr(self.var, name)

    @function.setter
    def function(self, value):
        setattr(self.var, name, value)

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
            return bool(int(x))

        def to_db(x):
            return repr(int(x))

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
    def __init__(self, owner):
        self._owner = owner

    def __getattr__(self, name):
        owner = self.__dict__["_owner"]
        if name == "_owner":
            return owner
        try:
            return owner.details[name]
        except KeyError:
            raise UndefinedVariableError(f"Undefined variable: {name}.")

    def __setattr__(self, name, value):
        if name == "_owner":
            self.__dict__["_owner"] = value
        else:
            # We need to copy the dictionary otherwise
            # SQLAlchemy won't notice that we changed it.
            all_vars = self.__dict__["_owner"].details.copy()
            all_vars[name] = value
            self.__dict__["_owner"].details = all_vars
