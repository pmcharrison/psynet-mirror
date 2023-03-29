# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
# Imports
##########################################################################################


import psynet.experiment
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import ColorBlindnessTest
from psynet.timeline import Timeline

##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    label = "Colour blindness demo"

    timeline = Timeline(
        NoConsent(),
        ColorBlindnessTest(),
        InfoPage(
            "You passed the color blindness task! Congratulations.", time_estimate=3
        ),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        from psynet.prescreen import ColorBlindnessTrial

        trials = ColorBlindnessTrial.query.filter_by(participant_id=bot.id).all()
        assert len(trials) == 6
        n_correct = sum(trial.score for trial in trials)
        score = bot.module_states["color_blindness_test"][0].performance_check["score"]
        assert score == n_correct
