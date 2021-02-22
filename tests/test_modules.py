import pytest

from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Module, Timeline


def test_repeated_modules():
    with pytest.raises(
        ValueError, match="duplicated module ID\\(s\\): my-module, my-module-2"
    ):
        Timeline(
            Module("my-module", [InfoPage("My page", time_estimate=5)]),
            Module("my-module", [InfoPage("My page", time_estimate=5)]),
            Module("my-module-2", [InfoPage("My page", time_estimate=5)]),
            Module("my-module-2", [InfoPage("My page", time_estimate=5)]),
            Module("my-module-3", [InfoPage("My page", time_estimate=5)]),
            SuccessfulEndPage(),
        )
