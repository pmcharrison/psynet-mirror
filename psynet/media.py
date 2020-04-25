import os
import struct
import boto3
import botocore.errorfactory

from dallinger.config import get_config

from .utils import log_time_taken

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

def make_batch_file(in_files, output_path):
    with open(output_path, "wb") as output:
        for in_file in in_files:
            b = os.path.getsize(in_file)
            output.write(struct.pack('I', b))
            with open(in_file, 'rb') as i:
                output.write(i.read())

def get_aws_credentials():
    config = get_config()
    if not config.ready:
        config.load()
    return {
        "aws_access_key_id": config.get("aws_access_key_id"),
        "aws_secret_access_key": config.get("aws_secret_access_key"),
        "region_name": config.get("aws_region")
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
        "Successfully emptied S3 bucket %s (%i objects).",
        bucket_name, old_num_objects
    )

@log_time_taken
def upload_to_s3(local_path: str, bucket_name: str, key: str, public_read: bool):
    logger.info("Uploading %s to bucket %s with key %s...", local_path, bucket_name, key)

    # client = new_s3_client()
    # client.upload_file(local_path, bucket_name, key)

    args = {}
    if public_read:
        args["ACL"] = "public-read"

    bucket = get_s3_bucket(bucket_name)
    bucket.upload_file(local_path, key, ExtraArgs=args)

    return {
        "key": key,
        "url": f"https://{bucket_name}.s3.amazonaws.com/{key}"
    }

def create_bucket(bucket_name: str, client=None):
    logger.info("Creating bucket '%s'.", bucket_name)
    if client is None:
        client = new_s3_client()
    client.create_bucket(bucket_name)
