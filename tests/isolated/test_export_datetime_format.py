from datetime import datetime

from psynet.data import _db_instance_to_dict


class _DummyExportObject:
    def to_dict(self):
        return {"creation_time": datetime(2026, 2, 7, 12, 34, 56)}


def test_db_instance_to_dict_formats_datetime():
    data = _db_instance_to_dict(_DummyExportObject(), scrub_pii=False)

    assert data["creation_time"] == "2026-02-07 12:34:56"
    assert "py/object" not in data["creation_time"]
