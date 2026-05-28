Fixed incorrect `super().encode()` call in `NumpySerializer.default` for `np.bool_` types; should return `bool(obj)` like other numpy types (author: Cursor, reviewer: Peter Harrison)
