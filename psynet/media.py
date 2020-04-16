import os
import struct
import boto3

from dallinger.config import get_config

from .utils import log_time_taken

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

def make_batch_file(in_files, output_path):
    with open(output_path, "w") as output:
        for in_file in in_files:
            b = os.path.getsize(in_file)
            output.write(struct.pack('I', b))
            with open(in_file, 'r') as i:
                output.write(i.read())

def new_s3_client():
    config = get_config()

    return boto3.client(
        's3',
        aws_access_key_id = config.get("aws_access_key_id"),
        aws_secret_access_key = config.get("aws_secret_access_key"),
        region_name = config.get("aws_region")
    )

@log_time_taken
def upload_to_s3(local_path: str, bucket_name: str, key: str):
    logger.info("Uploading %s to bucket %s with key %s...", local_path, bucket_name, key)
    client = new_s3_client()
    client.upload_file(local_path, bucket_name, key)
    return {
        "key": key,
        "url": f"https://{bucket_name}.s3.amazonaws.com/{key}"
    }
