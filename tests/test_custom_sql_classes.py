import pytest

from psynet.utils import get_custom_sql_classes


@pytest.mark.usefixtures("demo_mcmcp")
def test_custom_sql_classes():
    classes = get_custom_sql_classes()

    desired = [
        "CustomCls",
        "CustomNetwork",
        "CustomNode",
        "CustomSource",
        "CustomTrial",
    ]

    for _actual, _desired in zip(classes.items(), desired):
        assert _actual[0] == _desired
        assert _actual[1].__name__ == _desired
