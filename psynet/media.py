import json
import os
import shutil
import struct
import tempfile

import boto3
import parselmouth
from dallinger.config import get_config

from .utils import cache, get_logger

logger = get_logger()


def make_batch_file(in_files, output_path):
    with open(output_path, "wb") as output:
        for in_file in in_files:
            b = os.path.getsize(in_file)
            output.write(struct.pack("I", b))
            with open(in_file, "rb") as i:
                output.write(i.read())


@cache
def get_aws_credentials(capitalize=False):
    config = get_config()
    if not config.ready:
        config.load()
    cred = {
        "aws_access_key_id": config.get("aws_access_key_id"),
        "aws_secret_access_key": config.get("aws_secret_access_key"),
        "region_name": config.get("aws_region"),
    }
    if capitalize:
        cred = {key.upper(): value for key, value in cred.items()}
    return cred


def new_s3_client():
    return boto3.client("s3", **get_aws_credentials())


def new_s3_resource():
    return boto3.resource("s3", **get_aws_credentials())


def get_s3_bucket(bucket_name: str):
    # pylint: disable=no-member
    resource = new_s3_resource()
    return resource.Bucket(bucket_name)


def setup_bucket_for_presigned_urls(bucket_name, public_read=False):
    logger.info("Setting bucket CORSRules and policies...")

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
    logger.info(
        "Verifying that the S3 bucket '%s' is correctly configured for public access...",
        bucket_name,
    )

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
