# pylint: disable=unused-import,abstract-method

import logging

import psynet.experiment
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.page import SuccessfulEndPage, ModularPage
from psynet.modular_page import PushButtonControl
from psynet.pytest_psynet import AnimalTrial, ColorTrial, trial_maker_1, trial_maker_2
from psynet.timeline import Timeline, for_loop, join

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


class Exp(psynet.experiment.Experiment):
    label = "Translation test"

    timeline = Timeline(
        NoConsent(),
        InfoPage(
            _("Hello, welcome to my experiment!"),
        ),
        ModularPage(

        )
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert len(bot.alive_trials) == 6
        trials = sorted(bot.alive_trials, key=lambda t: t.id)
        for i in [0, 2, 4]:
            assert isinstance(trials[i], AnimalTrial)
        for i in [1, 3, 5]:
            assert isinstance(trials[i], ColorTrial)
