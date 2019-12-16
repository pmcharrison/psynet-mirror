import importlib_resources
from dlgr_utils import templates

def get_template(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)
