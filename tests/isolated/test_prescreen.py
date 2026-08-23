import json

import numpy as np
import pytest

from psynet.prescreen import NumpySerializer


class TestNumpySerializer:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (np.bool_(True), '{"value": true}'),
            (np.bool_(False), '{"value": false}'),
            (np.int64(42), '{"value": 42}'),
            (np.float64(3.14), '{"value": 3.14}'),
            (np.array([1, 2, 3]), '{"value": [1, 2, 3]}'),
        ],
    )
    def test_serialize_numpy_types(self, value, expected):
        result = json.dumps({"value": value}, cls=NumpySerializer)
        assert result == expected
