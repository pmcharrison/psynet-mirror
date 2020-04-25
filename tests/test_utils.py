from psynet.utils import linspace

def test_linspace():
    assert linspace(0, 5, 6) == [0, 1, 2, 3, 4, 5]
    assert linspace(-1, 1, 5) == [-1, -0.5, 0, 0.5, 1]