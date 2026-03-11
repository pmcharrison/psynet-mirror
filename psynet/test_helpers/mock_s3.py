"""
Minimal S3 client mock for PsyNet's artifact-storage tests.

This helper intentionally implements only the boto client surface exercised by
the lightweight S3 artifact-storage tests: bucket creation, file
upload/download/copy/delete, and paginator-based object listings.
"""

import shutil
from datetime import datetime, timezone
from functools import cache
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import botocore.exceptions


def _client_error(code: str, operation_name: str):
    return botocore.exceptions.ClientError(
        {"Error": {"Code": code, "Message": code}},
        operation_name,
    )


class ArtifactStorageS3TestClient:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _bucket_path(self, bucket_name: str) -> Path:
        return self.root / bucket_name

    def _object_path(self, bucket_name: str, key: str) -> Path:
        return self._bucket_path(bucket_name).joinpath(*PurePosixPath(key).parts)

    def create_bucket(self, Bucket: str):
        self._bucket_path(Bucket).mkdir(parents=True, exist_ok=True)

    def _has_bucket(self, bucket_name: str) -> bool:
        return self._bucket_path(bucket_name).is_dir()

    def _list_objects(
        self, bucket_name: str, prefix: str = "", delimiter: str | None = None
    ):
        if not self._has_bucket(bucket_name):
            return []

        contents = []
        for path in self._bucket_path(bucket_name).rglob("*"):
            if not path.is_file():
                continue

            key = path.relative_to(self._bucket_path(bucket_name)).as_posix()
            if not key.startswith(prefix):
                continue

            if delimiter == "/":
                suffix = key[len(prefix) :].lstrip("/")
                if "/" in suffix:
                    continue

            contents.append(
                {
                    "Key": key,
                    "LastModified": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ),
                }
            )

        return contents

    def _upload_file(self, filename: str, bucket_name: str, key: str):
        if not self._has_bucket(bucket_name):
            raise _client_error("NoSuchBucket", "PutObject")
        target = self._object_path(bucket_name, key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(filename, target)

    def _download_file(self, bucket_name: str, key: str, filename: str):
        source = self._object_path(bucket_name, key)
        if not source.is_file():
            raise _client_error("NoSuchKey", "GetObject")
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, filename)

    def _copy(self, copy_source: dict, bucket_name: str, key: str):
        source = self._object_path(copy_source["Bucket"], copy_source["Key"])
        if not source.is_file():
            raise _client_error("NoSuchKey", "CopyObject")
        if not self._has_bucket(bucket_name):
            raise _client_error("NoSuchBucket", "CopyObject")
        target = self._object_path(bucket_name, key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    def _delete_object(self, bucket_name: str, key: str):
        path = self._object_path(bucket_name, key)
        if path.exists():
            path.unlink()

    def upload_file(self, Filename: str, Bucket: str, Key: str):
        self._upload_file(Filename, Bucket, Key)

    def download_file(self, Bucket: str, Key: str, Filename: str):
        self._download_file(Bucket, Key, Filename)

    def copy(self, CopySource: dict, Bucket: str, Key: str):
        self._copy(CopySource, Bucket, Key)

    def delete_object(self, Bucket: str, Key: str):
        self._delete_object(Bucket, Key)

    def get_paginator(self, name: str):
        def paginate(
            Bucket: str, Prefix: str = "", Delimiter: str | None = None, **_kwargs
        ):
            yield {
                "Contents": self._list_objects(
                    bucket_name=Bucket,
                    prefix=Prefix,
                    delimiter=Delimiter,
                )
            }

        return SimpleNamespace(paginate=paginate)


@cache
def get_artifact_storage_s3_test_client(root: str):
    return ArtifactStorageS3TestClient(root)


def setup_artifact_storage_s3_test_client(root: str):
    import psynet.asset as asset

    client = get_artifact_storage_s3_test_client(root)
    asset.get_s3_client = lambda: client
    asset.list_files_in_s3_bucket__cached.cache_clear()
