import importlib_resources
from . import templates

from sqlalchemy import Boolean, String, Integer, exc
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

def get_template(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)

def claim_field(db_index, type=None):
    if type is int:
        return IntField(db_index).function
    else:
        raise NotImplementedError
        
class Field():
    def __init__(self, db_index, from_db, to_db, sql_type):
        assert 1 <= db_index and db_index <= 5    
        db_field = f"property{db_index}"

        @hybrid_property
        def function(self):
            return from_db(getattr(self, db_field))
        
        @function.setter
        def function(self, value):
            setattr(self, db_field, to_db(value))

        @function.expression
        def function(self):
            return cast(getattr(self, db_field), sql_type)

        self.function = function

class IntField(Field):
    def __init__(self, db_index):
        super().__init__(db_index, int, int, Integer)
