"""Tests for psynet.field module."""

from psynet.field import _PythonDict, _PythonList


class TestSerialize:
    """Test that serialize methods work correctly."""

    def test_python_list_serialize(self):
        """Test that _PythonList.serialize works correctly as a classmethod."""
        result = _PythonList.serialize([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_python_dict_serialize(self):
        """Test that _PythonDict.serialize works correctly as a classmethod."""
        result = _PythonDict.serialize({"a": 1, "b": 2})
        assert result == '{"a": 1, "b": 2}'
