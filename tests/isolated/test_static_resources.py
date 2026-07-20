from types import SimpleNamespace

import pytest

from psynet.static_resources import (
    STATIC_ENTRY_POINT_GROUP,
    _discover_static_packages,
    get_static_packages,
    package_static_url,
)


class FakeEntryPoint:
    def __init__(self, name, loaded, distribution="test-distribution"):
        self.name = name
        self._loaded = loaded
        self.dist = SimpleNamespace(name=distribution)

    def load(self):
        return self._loaded


def test_package_static_url_is_namespaced_and_escaped():
    assert (
        package_static_url("My_Component.Package", "icons/play button.js")
        == "/static/packages/my-component-package/icons/play%20button.js"
    )


@pytest.mark.parametrize(
    "namespace, path",
    [
        ("", "widget.js"),
        ("invalid namespace", "widget.js"),
        ("package", ""),
        ("package", "../widget.js"),
        ("package", "/widget.js"),
        ("package", r"scripts\widget.js"),
        ("package", "https://example.com/widget.js"),
        ("package", "widget.js?version=1"),
        ("package", "widget.js#fragment"),
    ],
)
def test_package_static_url_rejects_unsafe_values(namespace, path):
    with pytest.raises(ValueError):
        package_static_url(namespace, path)


def test_discovers_callable_static_root(tmp_path):
    root = tmp_path / "static"
    root.mkdir()
    (root / "widget.js").write_text("window.widget = true;", encoding="utf-8")
    entry_point = FakeEntryPoint("My_Component", lambda: root)

    packages = _discover_static_packages([entry_point])

    assert len(packages) == 1
    package = packages[0]
    assert package.namespace == "my-component"
    assert package.root == root
    assert package.distribution == "test-distribution"
    assert package.extra_file == (root, "/static/packages/my-component")


def test_discovery_is_deterministic(tmp_path):
    root = tmp_path / "static"
    root.mkdir()
    packages = _discover_static_packages(
        [
            FakeEntryPoint("z-package", lambda: root),
            FakeEntryPoint("a-package", lambda: root),
        ]
    )

    assert [package.namespace for package in packages] == [
        "a-package",
        "z-package",
    ]


def test_duplicate_canonical_names_are_rejected(tmp_path):
    root = tmp_path / "static"
    root.mkdir()

    with pytest.raises(
        ValueError,
        match="duplicate.*my-package.*first-distribution.*second-distribution",
    ):
        _discover_static_packages(
            [
                FakeEntryPoint("my_package", lambda: root, "first-distribution"),
                FakeEntryPoint("my.package", lambda: root, "second-distribution"),
            ]
        )


def test_missing_static_root_is_rejected(tmp_path):
    missing = tmp_path / "missing"

    with pytest.raises(ValueError, match="does not exist"):
        _discover_static_packages(
            [FakeEntryPoint("missing-package", lambda: missing)]
        )


def test_entry_point_group_name_is_stable():
    assert STATIC_ENTRY_POINT_GROUP == "psynet.static"


def test_psynet_registers_its_static_resource_root():
    package = next(
        package
        for package in get_static_packages()
        if package.namespace == "psynet"
    )

    assert package.root.joinpath("scripts/music-notation-prompt.js").is_file()
    assert package.extra_file[1] == "/static/packages/psynet"


def test_experiment_stages_registered_static_packages():
    from psynet.experiment import Experiment

    destinations = [destination for _, destination in Experiment.extra_files()]

    assert "/static/packages/psynet" in destinations
