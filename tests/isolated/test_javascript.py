import pytest

from psynet.timeline import Page


@pytest.mark.parametrize("argument_name", ["js_dependencies", "js_page_scripts"])
@pytest.mark.parametrize(
    "invalid_value, error, match",
    [
        ([""], ValueError, "non-empty"),
        ([123], TypeError, "strings"),
        ("not-a-list", TypeError, "list or tuple"),
    ],
)
def test_page_validates_managed_javascript_urls(
    argument_name, invalid_value, error, match
):
    with pytest.raises(error, match=match):
        Page(
            template_fragment_str="<p>Managed JavaScript page</p>",
            **{argument_name: invalid_value},
        )


def test_page_normalizes_javascript_resources():
    page = Page(
        template_fragment_str="<p>Managed JavaScript page</p>",
        js_dependencies=[
            "/static/library.js",
            "/static/other-library.js",
            "/static/library.js",
        ],
        js_page_scripts=[
            "/static/page.js",
            "/static/other-page.js",
            "/static/page.js",
        ],
    )

    assert page.js_dependencies == [
        "/static/library.js",
        "/static/other-library.js",
    ]
    assert page.js_page_scripts == [
        "/static/page.js",
        "/static/other-page.js",
    ]


def test_page_rejects_javascript_url_with_conflicting_lifecycles():
    with pytest.raises(ValueError, match="both js_dependencies and js_page_scripts"):
        Page(
            template_fragment_str="<p>Conflicting JavaScript page</p>",
            js_dependencies=["/static/shared.js"],
            js_page_scripts=["/static/shared.js"],
        )


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
