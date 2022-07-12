import pytest

import psynet.experiment  # noqa -- Need to import this for SQLAlchemy registrations to work properly
from psynet.assets import CachedFunctionAsset


def test_lambda_function():
    with pytest.raises(ValueError) as e:
        CachedFunctionAsset(function=lambda path, x: x + 1)
    assert (
        str(e.value)
        == "'function' cannot be a lambda function, please provide a named function instead"
    )
