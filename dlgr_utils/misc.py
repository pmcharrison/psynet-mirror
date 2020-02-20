import importlib_resources
from . import templates

from sqlalchemy import Boolean, String, Integer, exc
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

def get_template(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)
