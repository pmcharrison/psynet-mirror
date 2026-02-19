import shutil
import tempfile
from glob import glob
from os import makedirs
from os.path import basename, join

from psynet.asset import S3Storage


def get_s3_storage(transfer_backend):
    return S3Storage("psynet-tests", "s3-tests", transfer_backend)


def create_test_file(test_folder, test_file_path):
    makedirs(test_folder, exist_ok=True)
    with open(test_file_path, "w") as file:
        file.write("Test")


def file_exists_on_s3(storage, s3_key):
    return storage.check_cache_for_file(s3_key, False)


def folder_exists_on_s3(storage, s3_key):
    return storage.check_cache_for_folder(s3_key, False)


def remove_test_folder(test_folder):
    shutil.rmtree(test_folder)


def get_test_files(test_folder):
    return sorted(glob(test_folder + "/*"))


def run_test(storage):
    with tempfile.TemporaryDirectory() as tempdir:
        test_folder = join(tempdir, "test_folder")
        test_file_name = "test_file"
        test_file_path = join(test_folder, test_file_name)
        test_file_path_downloaded = test_file_path + "_downloaded"
        remote_test_file_name = test_file_name + "_remote"
        remote_test_folder = "test_folder_remote"

        create_test_file(test_folder, test_file_path)

        # File test
        storage.upload_file(test_file_path, remote_test_file_name)
        assert file_exists_on_s3(
            storage, remote_test_file_name
        ), "File was not uploaded to S3"
        storage.download_file(remote_test_file_name, test_file_path_downloaded)
        listed_files = get_test_files(test_folder)
        assert len(listed_files) == 2
        storage.delete_file(remote_test_file_name)
        assert not file_exists_on_s3(
            storage, remote_test_file_name
        ), "File was not removed on S3"

        # Folder test
        storage.upload_folder(test_folder, remote_test_folder)
        assert folder_exists_on_s3(storage, remote_test_folder)
        for file_path in listed_files:
            remote_file_path = join(remote_test_folder, basename(file_path))
            assert file_exists_on_s3(storage, remote_file_path)
        remove_test_folder(test_folder)
        storage.download_folder(remote_test_folder, test_folder)
        assert listed_files == get_test_files(test_folder)
        storage.delete_folder(remote_test_folder)
        assert not folder_exists_on_s3(storage, remote_test_folder)
        remove_test_folder(test_folder)


def test_s3_storage_awscli():
    # Only run the test if AWS CLI is installed
    from shutil import which

    if which("aws") is not None:
        storage = get_s3_storage("awscli")
        run_test(storage)


def test_s3_storage_boto3():
    storage = get_s3_storage("boto3")
    run_test(storage)
