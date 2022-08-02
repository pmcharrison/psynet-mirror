import pytest

from psynet.asset import S3Storage


@pytest.fixture
def s3_storage():
    return S3Storage("psynet", "tests")
