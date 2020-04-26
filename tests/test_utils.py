import pytest
from psynet.utils import linspace, merge_dicts, DuplicateKeyError

def test_linspace():
    assert linspace(0, 5, 6) == [0, 1, 2, 3, 4, 5]
    assert linspace(-1, 1, 5) == [-1, -0.5, 0, 0.5, 1]

def test_merge_dicts():
    x = {"a": 1, "b": 2, "c": 3}
    y = {"b": 5, "c": 4, "d": 11}
    z = {"c": 10, "d": -5, "e": 5}

    assert merge_dicts(x, y, z, overwrite=True) == {"a": 1, "b": 5, "c": 10, "d": -5, "e": 5}

    with pytest.raises(DuplicateKeyError) as e:
        merge_dicts(x, y, z, overwrite=False)
