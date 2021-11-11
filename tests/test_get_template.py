import importlib_resources

from psynet.timeline import get_template, templates


def get_template_legacy(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)


def test_get_template():
    page = "final-page.html"
    assert get_template(page) == get_template_legacy(page)
