import pytest

from psynet.javascript import JSDependency, JSPageScript
from psynet.timeline import Page


def test_javascript_resource_descriptors_validate_source():
    assert JSDependency("/static/library.js").src == "/static/library.js"
    assert JSPageScript("/static/page.js").src == "/static/page.js"

    for resource_class in [JSDependency, JSPageScript]:
        with pytest.raises(ValueError, match="non-empty"):
            resource_class("")
        with pytest.raises(TypeError, match="string"):
            resource_class(123)


def test_page_normalizes_javascript_resources():
    page = Page(
        template_fragment_str="<p>Managed JavaScript page</p>",
        js_dependencies=[
            "/static/library.js",
            JSDependency("/static/other-library.js"),
        ],
        js_page_scripts=[
            "/static/page.js",
            JSPageScript("/static/other-page.js"),
        ],
    )

    assert page.js_dependencies == [
        JSDependency("/static/library.js"),
        JSDependency("/static/other-library.js"),
    ]
    assert page.js_page_scripts == [
        JSPageScript("/static/page.js"),
        JSPageScript("/static/other-page.js"),
    ]


def test_error_mode_rejects_legacy_page_javascript():
    page = Page(
        template_fragment_str="<p>Legacy JavaScript page</p>",
        js_links=["/static/legacy.js"],
        scripts=["window.legacySetup = true;"],
    )

    page._check_legacy_page_javascript("allow")
    page._check_legacy_page_javascript("warn")
    with pytest.raises(ValueError, match="js_dependencies.*js_page_scripts"):
        page._check_legacy_page_javascript("error")
