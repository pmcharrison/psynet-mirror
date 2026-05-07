from psynet.serialize import serialize, unserialize


class SerializeRoundtrip:
    timeout = 120

    def setup(self):
        self.obj = _make_payload()
        self.encoded = serialize(self.obj)

    def time_serialize(self):
        serialize(self.obj)

    def time_unserialize(self):
        unserialize(self.encoded)


def _make_payload():
    return {
        "participants": [
            {
                "id": i,
                "name": f"participant_{i}",
                "score": i * 1.5,
                "answers": [
                    {"q": f"q{j}", "a": (i + j) % 7, "ok": (i + j) % 2 == 0}
                    for j in range(20)
                ],
                "metadata": {"group": ["A", "B", "C"][i % 3], "active": i % 2 == 0},
            }
            for i in range(50)
        ],
        "config": {"version": "1.0", "tags": ["alpha", "beta", "gamma"]},
    }
