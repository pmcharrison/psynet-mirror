import pytest

from psynet.translation.translation import check_languages


def test_check_languages():
    assert check_languages(["fr", "de"])

    with pytest.raises(ValueError, match="Unknown language: asdas"):
        check_languages(["asdas"])
