import pytest

from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Module, Timeline


def test_repeated_modules():
    with pytest.raises(
        ValueError,
        match="The following module ID\\(s\\) were duplicated in your timeline: my-module, my-module-2",
    ):
        Timeline(
            NoConsent(),
            Module("my-module", [InfoPage("My page", time_estimate=5)]),
            Module("my-module", [InfoPage("My page", time_estimate=5)]),
            Module("my-module-2", [InfoPage("My page", time_estimate=5)]),
            Module("my-module-2", [InfoPage("My page", time_estimate=5)]),
            Module("my-module-3", [InfoPage("My page", time_estimate=5)]),
            SuccessfulEndPage(),
        )
