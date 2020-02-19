import importlib_resources
from . import templates

def get_template(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)
