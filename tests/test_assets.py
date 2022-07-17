import pytest

import psynet.experiment  # noqa -- Need to import this for SQLAlchemy registrations to work properly
from psynet.asset import CachedFunctionAsset


def test_lambda_function():
    with pytest.raises(ValueError) as e:
        CachedFunctionAsset(function=lambda path, x: x + 1)
    assert (
        str(e.value)
        == "'function' cannot be a lambda function, please provide a named function instead"
    )


def test_key():
    def f(path):
        pass

    asset_1 = CachedFunctionAsset(function=f)
    asset_2 = CachedFunctionAsset(function=f, key="asset_2")

    assert not asset_1.has_key
    assert asset_2.has_key
