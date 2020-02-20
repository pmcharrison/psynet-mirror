from sqlalchemy import Boolean, String, Integer, exc
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

import json
import rpdb

def claim_field(db_index, type=None):
    if type is int:
        return IntField(db_index).function
    elif type is bool:
        return BoolField(db_index).function
    elif type is dict:
        return DictField(db_index).function
    elif type is object:
        return ObjectField(db_index).function
    else:
        raise NotImplementedError
        
class Field():
    def __init__(self, db_index, from_db, to_db, python_type, sql_type, null_value=lambda: None):
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
                if not isinstance(value, python_type):
                    raise TypeError
                db_value = to_db(value)
            setattr(self, db_field, db_value)

        @function.expression
        def function(self):
            return cast(getattr(self, db_field), sql_type)

        self.function = function

class IntField(Field):
    def __init__(self, db_index):
        super().__init__(db_index, from_db=int, to_db=int, python_type=int, sql_type=Integer)

class BoolField(Field):
    def __init__(self, db_index):
        def from_db(x):
            return bool(int(x))

        def to_db(x):
            return repr(int(x))

        super().__init__(db_index, from_db, to_db, bool, Boolean)

class DictField(Field):
    def __init__(self, db_index):
        super().__init__(
            db_index,
            from_db=json.loads, 
            to_db=json.dumps, 
            python_type=dict, 
            sql_type=String, 
            null_value=lambda: {}
        )

class ObjectField(Field):
    def __init__(self, db_index):
        super().__init__(
            db_index, 
            from_db=json.loads, 
            to_db=json.dumps, 
            python_type=object, 
            sql_type=String
        )
