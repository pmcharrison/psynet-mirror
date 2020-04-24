from psynet.utils import merge_dicts

def test_merge_dicts():
    x = {"a": 1, "b": 2, "c": 3}
    y = {"b": 5, "c": 4, "d": 11}
    z = {"c": 10, "d": -5, "e": 5}

    assert merge_dicts(x, y, z) == {"a": 1, "b": 5, "c": 10, "d": -5, "e": 5}
    assert merge_dicts() == {}
