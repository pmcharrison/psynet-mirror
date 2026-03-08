"""
Minimal mock S3 support for PsyNet's artifact-storage tests.

This helper intentionally implements only the subset of S3 behavior exercised by
`S3ArtifactStorage` and `S3Boto3TransferBackend`, including bucket creation,
object upload/download/copy/delete, object metadata lookups, paginator-based
listing, and the resource helpers used by recursive operations.
"""

import io
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cache
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import botocore.exceptions


def _client_error(code: str, operation_name: str):
    return botocore.exceptions.ClientError(
        {
            "Error": {
                "Code": code,
                "Message": code,
            }
        },
        operation_name,
    )


class _BucketExceptions:
    class BucketAlreadyOwnedByYou(Exception):
        pass


class MockS3Store:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def bucket_path(self, bucket_name: str) -> Path:
        return self.root / bucket_name

    def ensure_bucket(self, bucket_name: str):
        self.bucket_path(bucket_name).mkdir(parents=True, exist_ok=True)

    def has_bucket(self, bucket_name: str) -> bool:
        return self.bucket_path(bucket_name).is_dir()

    def object_path(self, bucket_name: str, key: str) -> Path:
        return self.bucket_path(bucket_name).joinpath(*PurePosixPath(key).parts)

    def put_file(self, bucket_name: str, key: str, source_path: str):
        if not self.has_bucket(bucket_name):
            raise _client_error("NoSuchBucket", "PutObject")
        target_path = self.object_path(bucket_name, key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)

    def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        target_bucket: str,
        target_key: str,
    ):
        source_path = self.object_path(source_bucket, source_key)
        if not source_path.is_file():
            raise _client_error("NoSuchKey", "CopyObject")
        if not self.has_bucket(target_bucket):
            raise _client_error("NoSuchBucket", "CopyObject")
        target_path = self.object_path(target_bucket, target_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)

    def download_file(self, bucket_name: str, key: str, target_path: str):
        source_path = self.object_path(bucket_name, key)
        if not source_path.is_file():
            raise _client_error("NoSuchKey", "GetObject")
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)

    def delete_object(self, bucket_name: str, key: str):
        path = self.object_path(bucket_name, key)
        if path.exists():
            path.unlink()
            self._remove_empty_parents(path.parent, self.bucket_path(bucket_name))

    def get_object(self, bucket_name: str, key: str):
        source_path = self.object_path(bucket_name, key)
        if not source_path.is_file():
            raise _client_error("NoSuchKey", "GetObject")
        return {"Body": io.BytesIO(source_path.read_bytes())}

    def head_object(self, bucket_name: str, key: str):
        source_path = self.object_path(bucket_name, key)
        if not source_path.is_file():
            raise _client_error("NoSuchKey", "HeadObject")
        return {
            "LastModified": datetime.fromtimestamp(
                source_path.stat().st_mtime, tz=timezone.utc
            )
        }

    def list_objects(
        self,
        bucket_name: str,
        prefix: str = "",
        delimiter: str | None = None,
    ):
        if not self.has_bucket(bucket_name):
            return []

        bucket_path = self.bucket_path(bucket_name)
        contents = []
        for path in bucket_path.rglob("*"):
            if not path.is_file():
                continue

            key = path.relative_to(bucket_path).as_posix()
            if not key.startswith(prefix):
                continue

            if delimiter == "/":
                suffix = key[len(prefix) :]
                if suffix.startswith("/"):
                    suffix = suffix[1:]
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

    def _remove_empty_parents(self, path: Path, stop_at: Path):
        while path != stop_at and path.is_dir():
            try:
                path.rmdir()
            except OSError:
                break
            path = path.parent


class MockS3Paginator:
    def __init__(self, store: MockS3Store):
        self.store = store

    def paginate(
        self,
        Bucket: str,
        Prefix: str = "",
        Delimiter: str | None = None,
        **_kwargs,
    ):
        yield {
            "Contents": self.store.list_objects(
                bucket_name=Bucket,
                prefix=Prefix,
                delimiter=Delimiter,
            )
        }


@dataclass
class MockS3ObjectSummary:
    store: MockS3Store
    bucket_name: str
    key: str
    last_modified: datetime

    def delete(self):
        self.store.delete_object(self.bucket_name, self.key)


class MockS3FilteredObjects:
    def __init__(self, store: MockS3Store, bucket_name: str, prefix: str):
        self.store = store
        self.bucket_name = bucket_name
        self.prefix = prefix

    def __iter__(self):
        for content in self.store.list_objects(self.bucket_name, prefix=self.prefix):
            yield MockS3ObjectSummary(
                store=self.store,
                bucket_name=self.bucket_name,
                key=content["Key"],
                last_modified=content["LastModified"],
            )

    def delete(self):
        for obj in list(self):
            obj.delete()


class MockS3ObjectCollection:
    def __init__(self, store: MockS3Store, bucket_name: str):
        self.store = store
        self.bucket_name = bucket_name

    def filter(self, Prefix: str):
        return MockS3FilteredObjects(self.store, self.bucket_name, Prefix)


class MockS3ObjectRef:
    def __init__(self, store: MockS3Store, bucket_name: str, key: str):
        self.store = store
        self.bucket_name = bucket_name
        self.key = key

    def delete(self):
        self.store.delete_object(self.bucket_name, self.key)


class MockS3Bucket:
    def __init__(self, store: MockS3Store, bucket_name: str):
        self.store = store
        self.name = bucket_name
        self.objects = MockS3ObjectCollection(store, bucket_name)

    def Object(self, key: str):
        return MockS3ObjectRef(self.store, self.name, key)

    def Cors(self):
        return SimpleNamespace(delete=lambda: None, put=lambda **_kwargs: None)

    def Acl(self):
        return SimpleNamespace(put=lambda **_kwargs: None)


class MockS3Client:
    exceptions = _BucketExceptions

    def __init__(self, root: str):
        self.store = MockS3Store(root)

    def create_bucket(self, Bucket: str):
        self.store.ensure_bucket(Bucket)

    def upload_file(self, Filename: str, Bucket: str, Key: str):
        self.store.put_file(Bucket, Key, Filename)

    def download_file(self, Bucket: str, Key: str, Filename: str):
        self.store.download_file(Bucket, Key, Filename)

    def copy(self, CopySource: dict, Bucket: str, Key: str):
        self.store.copy_object(
            source_bucket=CopySource["Bucket"],
            source_key=CopySource["Key"],
            target_bucket=Bucket,
            target_key=Key,
        )

    def delete_object(self, Bucket: str, Key: str):
        self.store.delete_object(Bucket, Key)

    def get_paginator(self, name: str):
        if name != "list_objects":
            raise NotImplementedError(f"Unsupported paginator: {name}")
        return MockS3Paginator(self.store)

    def head_object(self, Bucket: str, Key: str):
        return self.store.head_object(Bucket, Key)

    def get_object(self, Bucket: str, Key: str):
        return self.store.get_object(Bucket, Key)

    def head_bucket(self, Bucket: str):
        if not self.store.has_bucket(Bucket):
            raise _client_error("404", "HeadBucket")


class MockS3Resource:
    def __init__(self, root: str):
        self._client = get_mock_s3_client(root)
        self.store = self._client.store
        self.meta = SimpleNamespace(client=self._client)

    def Bucket(self, bucket_name: str):
        return MockS3Bucket(self.store, bucket_name)

    def BucketPolicy(self, _bucket_name: str):
        return SimpleNamespace(put=lambda **_kwargs: None)


@cache
def get_mock_s3_client(root: str):
    return MockS3Client(root)


@cache
def get_mock_s3_resource(root: str):
    return MockS3Resource(root)


def setup_mock_s3(root: str):
    import psynet.artifact as artifact
    import psynet.asset as asset
    import psynet.media as media

    client = get_mock_s3_client(root)
    resource = get_mock_s3_resource(root)

    media.get_s3_client = lambda: client
    media.get_s3_resource = lambda: resource
    asset.get_s3_client = lambda: client
    asset.get_s3_bucket = lambda bucket_name: resource.Bucket(bucket_name)
    artifact.get_s3_client = lambda: client
    asset.list_files_in_s3_bucket__cached.cache_clear()
