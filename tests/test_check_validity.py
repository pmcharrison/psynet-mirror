import pytest

from psynet.asset import ExternalAsset
from psynet.data import InvalidDefinitionError


def test_define_in_function():
    with pytest.raises(InvalidDefinitionError):

        def f():
            class CustomExternalAsset(ExternalAsset):
                pass

            return CustomExternalAsset

        f()


def test_define_in_class():
    with pytest.raises(InvalidDefinitionError):
        try:
            from .examples import example_invalid_class_definition  # noqa
        except ImportError:
            from examples import example_invalid_class_definition  # noqa


def test_define_in_module():
    try:
        from .examples import example_valid_class_definition  # noqa
    except ImportError:
        from examples import example_invalid_class_definition  # noqa
