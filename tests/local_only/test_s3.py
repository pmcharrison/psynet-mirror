import os
import tempfile
import uuid

import pytest

from psynet.asset import ExperimentAsset, S3Storage


@pytest.fixture
def s3_storage(config):
    # Config gives us our AWS credentials
    root = "tests/" + str(uuid.uuid4())
    storage = S3Storage("psynet-tests", root)
    try:
        yield storage
    finally:
        storage.delete_all()


@pytest.fixture
def text_file_1():
    with tempfile.NamedTemporaryFile("w") as f:
        f.write("Hello!")
        f.flush()
        yield f.name


@pytest.fixture()
def text_folder():
    with tempfile.TemporaryDirectory() as tempdir:
        path_1 = os.path.join(tempdir, "file_1.txt")
        path_2 = os.path.join(tempdir, "file_2.txt")

        with open(path_1, "w") as f:
            f.write("File 1")

        with open(path_2, "w") as f:
            f.write("File 2")

        yield tempdir


def test_upload_file(s3_storage, text_file_1):
    host_path = "test-1.txt"
    s3_key = s3_storage.get_s3_key(host_path)

    s3_storage.upload_file(text_file_1, s3_key)
    assert s3_storage.check_cache(host_path, is_folder=False, use_cache=False)
    assert not s3_storage.check_cache("test-2.txt", is_folder=False, use_cache=False)


def test_upload_folder(s3_storage, text_folder):
    host_path = "text-folder"
    s3_key = s3_storage.get_s3_key(host_path)

    s3_storage.upload_folder(text_folder, s3_key)
    assert s3_storage.check_cache(host_path, is_folder=True, use_cache=False)
    assert s3_storage.check_cache(
        host_path + "/file_1.txt", is_folder=False, use_cache=False
    )
    assert s3_storage.check_cache(
        host_path + "/file_2.txt", is_folder=False, use_cache=False
    )
    assert not s3_storage.check_cache("text-folder-2", is_folder=True, use_cache=False)


def test_list_files_nonexistent_bucket():
    storage = S3Storage("psynet-f83jf93jf930a", root="test")

    assert storage.list_files_with_prefix("", use_cache=False) == []


@pytest.mark.parametrize("experiment_directory", ["../demos/gibbs"], indirect=True)
def test_s3_asset_file(s3_storage, text_file_1):
    asset = ExperimentAsset(
        "test_asset",
        text_file_1,
    )

    asset.deposit(s3_storage)

    assert s3_storage.check_cache(asset.host_path, is_folder=False)

    with tempfile.NamedTemporaryFile() as f:
        asset.export(f.name)
        with open(f.name, "r") as reader:
            assert reader.read() == "Hello!"


@pytest.mark.parametrize("experiment_directory", ["../demos/gibbs"], indirect=True)
def test_s3_asset_folder(s3_storage, text_folder):
    asset = ExperimentAsset(
        "test_folder_asset",
        text_folder,
    )

    asset.deposit(s3_storage)

    assert s3_storage.check_cache(asset.host_path, is_folder=True)

    with tempfile.TemporaryDirectory() as tempdir:
        asset.export(tempdir + "/asset")

        with open(tempdir + "/asset/file_1.txt") as f:
            assert f.read() == "File 1"

        with open(tempdir + "/asset/file_2.txt") as f:
            assert f.read() == "File 2"
