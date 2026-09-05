"""Tests for asset subpath safety and LocalStorage serving."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask import Flask

from psynet.asset import Asset, LocalStorage, _safe_asset_subpath
from psynet.experiment import _redacted_asset_request_path


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


def test_asset_serve_rejects_unsafe_subpath_with_http_400():
    asset = Asset.__new__(Asset)
    app = Flask("test-asset-serve-unsafe")
    with app.test_request_context("/"):
        with pytest.raises(Exception) as exc:
            asset.serve("../secret.txt")
        assert getattr(exc.value, "code", None) == 400


def test_redacted_asset_request_path():
    assert _redacted_asset_request_path("/asset/tok_abc123") == "/asset/<access_token>"
    assert (
        _redacted_asset_request_path("/asset/tok_abc123/sub/file.wav")
        == "/asset/<access_token>/sub/file.wav"
    )
    assert _redacted_asset_request_path("/timeline") == "/timeline"


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
        try:
            assert response.status_code == 200
            response.direct_passthrough = False
            assert response.get_data() == b"payload"
        finally:
            # A real WSGI server closes the response; without this the file
            # handle opened by send_file leaks into pytest's teardown.
            response.close()


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


def test_s3_storage_serve_redirects_to_public_url():
    from psynet.asset import S3Storage

    storage = S3Storage("my-bucket", "prefix")
    asset = MagicMock()
    asset.object_path = "objects/sha256/deadbeef"
    asset.host_path = asset.object_path
    asset.is_folder = False

    app = Flask("test-s3-serve-redirect")
    with app.test_request_context("/"):
        response = storage.serve(asset)
        assert response.status_code in (301, 302)
        assert response.location.startswith(
            "https://s3.amazonaws.com/my-bucket/prefix/objects/sha256/deadbeef"
        )


def test_managed_asset_s3_get_url_is_direct_public_object():
    from psynet.asset import ManagedAsset, S3Storage

    storage = S3Storage("my-bucket", "prefix")

    class Stub:
        def __init__(self):
            self.storage = storage
            self.default_storage = storage
            self.object_path = "objects/sha256/abcd"
            self.host_path = self.object_path
            self.access_token = "tok_should_not_appear"

        def access_url(self, subpath=None):
            return f"/asset/{self.access_token}"

    url = ManagedAsset.get_url(Stub())
    assert url.startswith("https://s3.amazonaws.com/my-bucket/")
    assert "objects/sha256/abcd" in url
    assert "tok_should_not_appear" not in url
    assert not url.startswith("/asset/")
