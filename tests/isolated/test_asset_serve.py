"""Tests for asset subpath safety and LocalStorage serving."""

from __future__ import annotations

import pytest
from flask import Flask

from psynet.asset import LocalStorage, _safe_asset_subpath


def test_safe_asset_subpath_none_and_empty():
    assert _safe_asset_subpath(None) is None
    assert _safe_asset_subpath("") is None
    assert _safe_asset_subpath(".") is None


def test_safe_asset_subpath_normalizes_relative_path():
    assert _safe_asset_subpath("a/b.txt") == "a/b.txt"
    assert _safe_asset_subpath("/a/b.txt") == "a/b.txt"
    assert _safe_asset_subpath("a/./b.txt") == "a/b.txt"


@pytest.mark.parametrize(
    "subpath",
    [
        "..",
        "../secret.txt",
        "a/../../secret.txt",
        "a/../b/../../x",
    ],
)
def test_safe_asset_subpath_rejects_traversal(subpath):
    with pytest.raises(ValueError, match="Unsafe asset subpath"):
        _safe_asset_subpath(subpath)


def test_local_storage_serve_file(tmp_path):
    root = tmp_path / "storage"
    object_rel = "objects/sha256/abc123"
    stored = root / object_rel
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"payload")

    class _Asset:
        object_path = object_rel
        host_path = object_rel
        is_folder = False

    storage = LocalStorage(root=str(root))
    app = Flask("test-local-storage-serve")
    with app.test_request_context("/"):
        response = storage.serve(_Asset())
        assert response.status_code == 200
        response.direct_passthrough = False
        assert response.get_data() == b"payload"


def test_local_storage_serve_rejects_subpath_on_file(tmp_path):
    root = tmp_path / "storage"
    object_rel = "objects/sha256/abc123"
    stored = root / object_rel
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"payload")

    class _Asset:
        object_path = object_rel
        host_path = object_rel
        is_folder = False

    storage = LocalStorage(root=str(root))
    app = Flask("test-local-storage-serve-subpath")
    with app.test_request_context("/"):
        with pytest.raises(Exception) as exc:
            storage.serve(_Asset(), "child.txt")
        # Flask abort(400) raises werkzeug.exceptions.BadRequest
        assert getattr(exc.value, "code", None) == 400
