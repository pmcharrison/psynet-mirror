import json
import os
import shutil
import struct
import tempfile
import uuid
from pathlib import Path

import boto3
import botocore.errorfactory
import botocore.exceptions
import parselmouth
from dallinger.config import get_config

from .utils import get_logger, log_time_taken

logger = get_logger()

# For debugging, currently only partly implemented
LOCAL_S3 = False
LOCAL_S3_CLONE = "local-s3-clone"


def make_batch_file(in_files, output_path):
    with open(output_path, "wb") as output:
        for in_file in in_files:
            b = os.path.getsize(in_file)
            output.write(struct.pack("I", b))
            with open(in_file, "rb") as i:
                output.write(i.read())


def get_aws_credentials():
    config = get_config()
    if not config.ready:
        config.load()
    return {
        "aws_access_key_id": config.get("aws_access_key_id"),
        "aws_secret_access_key": config.get("aws_secret_access_key"),
        "region_name": config.get("aws_region"),
    }


def new_s3_client():
    return boto3.client("s3", **get_aws_credentials())


def new_s3_resource():
    return boto3.resource("s3", **get_aws_credentials())


def get_s3_bucket(bucket_name: str):
    # pylint: disable=no-member
    resource = new_s3_resource()
    return resource.Bucket(bucket_name)


def count_objects_in_s3_bucket(bucket_name: str):
    bucket = get_s3_bucket(bucket_name)
    return sum(1 for _ in bucket.objects.all())


@log_time_taken
def empty_s3_bucket(bucket_name: str):
    old_num_objects = count_objects_in_s3_bucket(bucket_name)

    bucket = get_s3_bucket(bucket_name)
    bucket.objects.delete()

    new_num_objects = count_objects_in_s3_bucket(bucket_name)
    if new_num_objects != 0:
        raise RuntimeError(
            f"Failed to empty S3 bucket {bucket_name} "
            f"({new_num_objects} object(s) still remaining)."
        )

    logger.info(
        "Successfully emptied S3 bucket %s (%i objects).", bucket_name, old_num_objects
    )


@log_time_taken
def prepare_s3_bucket_for_presigned_urls(
    bucket_name: str, public_read: bool, create_new_bucket: bool = False
):
    logger.info("Preparing S3 bucket for presigned urls...")
    if create_new_bucket and not bucket_exists(bucket_name):
        create_bucket(bucket_name)
    setup_bucket_for_presigned_urls(bucket_name, public_read)


@log_time_taken
def generate_presigned_url(bucket_name: str, file_extension: str):
    return new_s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket_name, "Key": f"{str(uuid.uuid4())}.{file_extension}"},
    )


@log_time_taken
def upload_to_s3(
    local_path: str,
    bucket_name: str,
    key: str,
    public_read: bool,
    create_new_bucket: bool = False,
):
    "If ``create_new_bucket`` is ``True``, then a new bucket is created if the bucket doesn't exist."
    if LOCAL_S3:
        return upload_to_local_s3(
            local_path, bucket_name, key, public_read, create_new_bucket
        )

    logger.info(
        "Uploading %s to bucket %s with key %s...", local_path, bucket_name, key
    )

    args = {}
    if public_read:
        args["ACL"] = "public-read"

    bucket = get_s3_bucket(bucket_name)

    def upload():
        if os.path.isfile(local_path):
            bucket.upload_file(local_path, key, ExtraArgs=args)
        else:
            for _dir_path, _dir_names, _file_names in os.walk(local_path):
                _rel_dir_path = os.path.relpath(_dir_path, local_path)
                for _file_name in _file_names:
                    _local_path = os.path.join(_dir_path, _file_name)
                    if _rel_dir_path == ".":
                        _file_key = os.path.join(key, _file_name)
                    else:
                        _file_key = os.path.join(key, _rel_dir_path, _file_name)
                    bucket.upload_file(_local_path, _file_key, ExtraArgs=args)

    try:
        upload()
    except boto3.exceptions.S3UploadFailedError as e:
        if ("NoSuchBucket" in str(e)) and create_new_bucket:
            create_bucket(bucket_name)
            upload()
        else:
            raise

    return {"key": key, "url": f"https://{bucket_name}.s3.amazonaws.com/{key}"}


def upload_to_local_s3(local_path, bucket_name, key, public_read, create_new_bucket):
    logger.info(
        "Simulating uploading %s to bucket %s with key %s...",
        local_path,
        bucket_name,
        key,
    )

    output_dirs = ["static/s3"]
    if LOCAL_S3_CLONE is not None:
        output_dirs.append(LOCAL_S3_CLONE)

    for output_dir in output_dirs:
        destination = os.path.join(output_dir, bucket_name, key)
        Path(os.path.dirname(destination)).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, destination)

    return {"key": key, "url": os.path.join("/static/s3", bucket_name, key)}


def download_from_local_s3(local_path: str, bucket_name: str, key: str):
    logger.info(
        "Simulating downloading %s from bucket %s to local path %s...",
        key,
        bucket_name,
        local_path,
    )
    source_path = os.path.join("static/s3", bucket_name, key)
    shutil.copyfile(source_path, local_path)


@log_time_taken
def download_from_s3(local_path: str, bucket_name: str, key: str):
    # Returns False if the file doesn't exist, otherwise True.

    if LOCAL_S3:
        return download_from_local_s3(local_path, bucket_name, key)

    bucket = get_s3_bucket(bucket_name)
    try:
        bucket.download_file(key, local_path)
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return False
        raise
    return True


def read_string_from_s3(bucket_name: str, key: str):
    # Returns None if the file doesn't exist, otherwise returns the string.
    if LOCAL_S3:
        return read_string_from_local_s3(bucket_name, key)
    resource = new_s3_resource()
    obj = resource.Object(bucket_name, key)
    try:
        return obj.get()["Body"].read().decode("utf-8")
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise


def read_string_from_local_s3(bucket_name: str, key: str):
    path = os.path.join(LOCAL_S3_CLONE, bucket_name, key)
    if os.path.exists(path) and os.path.isfile(path):
        with open(path, "r") as f:
            return f.read()
    else:
        return None


def write_string_to_s3(string: str, bucket_name: str, key: str):
    if LOCAL_S3:
        write_string_to_local_s3(string, bucket_name, key)
    else:
        new_s3_client().put_object(Bucket=bucket_name, Body=string, Key=key)


def write_string_to_local_s3(string: str, bucket_name: str, key: str):
    path = os.path.join(LOCAL_S3_CLONE, bucket_name, key)
    with open(path, "w") as f:
        f.write(string)


def create_bucket(bucket_name: str, client=None):
    logger.info("Creating bucket '%s'.", bucket_name)
    if LOCAL_S3:
        Path(os.path.join(LOCAL_S3_CLONE, bucket_name)).mkdir(
            parents=True, exist_ok=True
        )
    else:
        if client is None:
            client = new_s3_client()
        client.create_bucket(Bucket=bucket_name)


def delete_bucket_dir(bucket_name, bucket_dir):
    logger.info(
        "Deleting directory '%s' in bucket '%s' (if it exists).",
        bucket_dir,
        bucket_name,
    )
    if LOCAL_S3:
        path = os.path.join(LOCAL_S3_CLONE, bucket_name, bucket_dir)
        if os.path.exists(path) and os.path.isdir(path):
            shutil.rmtree(path)
    else:
        bucket = get_s3_bucket(bucket_name)
        bucket.objects.filter(Prefix=bucket_dir).delete()


def bucket_exists(bucket_name):
    if LOCAL_S3:
        path = os.path.join(LOCAL_S3_CLONE, bucket_name)
        return os.path.exists(path) and os.path.isdir(path)
    resource = new_s3_resource()
    try:
        resource.meta.client.head_bucket(Bucket=bucket_name)
    except botocore.exceptions.ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        if error_code == 404:
            return False
    return True


def setup_bucket_for_presigned_urls(bucket_name, public_read=False):
    logger.info("Setting bucket CORSRules and policies...")

    if LOCAL_S3:
        return

    s3_resource = new_s3_resource()
    bucket = s3_resource.Bucket(bucket_name)

    cors = bucket.Cors()

    config = {
        "CORSRules": [
            {
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["GET", "PUT"],
                "AllowedOrigins": ["*"],
            }
        ]
    }

    cors.delete()
    cors.put(CORSConfiguration=config)

    if public_read:
        bucket_policy = s3_resource.BucketPolicy(bucket_name)

        new_policy = json.dumps(
            {
                "Version": "2008-10-17",
                "Statement": [
                    {
                        "Sid": "AllowPublicRead",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{bucket_name}/*",
                    }
                ],
            }
        )
        bucket_policy.put(Policy=new_policy)


def make_bucket_public(bucket_name):
    logger.info("Ensuring bucket is publicly accessible...")

    if LOCAL_S3:
        return

    s3_resource = new_s3_resource()
    bucket = s3_resource.Bucket(bucket_name)
    bucket.Acl().put(ACL="public-read")

    cors = bucket.Cors()

    config = {"CORSRules": [{"AllowedMethods": ["GET"], "AllowedOrigins": ["*"]}]}

    cors.delete()
    cors.put(CORSConfiguration=config)

    bucket_policy = s3_resource.BucketPolicy(bucket_name)
    new_policy = json.dumps(
        {
            "Version": "2008-10-17",
            "Statement": [
                {
                    "Sid": "AllowPublicRead",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/*",
                }
            ],
        }
    )
    bucket_policy.put(Policy=new_policy)


def recode_wav(file_path):
    with tempfile.NamedTemporaryFile() as temp_file:
        shutil.copyfile(file_path, temp_file.name)
        s = parselmouth.Sound(temp_file.name)
        s.save(file_path, "WAV")


def get_s3_url(bucket, key):
    if LOCAL_S3:
        destination = os.path.join("static", "s3", bucket, key)
        Path(os.path.dirname(destination)).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(os.path.join(LOCAL_S3_CLONE, bucket, key), destination)
        return os.path.join("/static/s3", bucket, key)
    else:
        return os.path.join("https://s3.amazonaws.com", bucket, key)
