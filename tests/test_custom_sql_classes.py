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

    assert desired == list(classes.keys())
    assert desired == list([c.__name__ for c in classes.values()])
