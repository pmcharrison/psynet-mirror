import pytest

from psynet.translation.translation import check_locales


def test_check_languages():
    assert check_locales(["fr", "de"])

    with pytest.raises(ValueError, match="Unknown locale: asdas"):
        check_locales(["asdas"])
