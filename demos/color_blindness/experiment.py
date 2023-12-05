# pylint: disable=unused-import,abstract-method,unused-argument,no-member

import psynet.experiment
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import ColorBlindnessTest
from psynet.timeline import Timeline
from psynet.modular_page import ModularPage, PushButtonControl, Prompt, Control, TextControl, NumberControl

class ValidationPage(ModularPage):
    pass
def get_calibration_page():
    time_estimate = 60
    lable = "validation"
    prompt = index.html
    return ValidationPage(
        "validation",
        (prompt),
        TextControl(one_line=False),
        save_answer=lable,
        time_estimate=time_estimate,
    )

class Exp(psynet.experiment.Experiment):
    label = "Colour blindness demo"

    timeline = Timeline(
        NoConsent(),
        get_calibration_page(),
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
