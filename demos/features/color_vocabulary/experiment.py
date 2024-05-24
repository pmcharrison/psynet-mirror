import psynet.experiment
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import ColorVocabularyTest
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Colour vocabulary demo"

    timeline = Timeline(
        NoConsent(),
        ColorVocabularyTest(),
        InfoPage(
            "You passed the color vocabulary task! Congratulations.", time_estimate=3
        ),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        from psynet.prescreen import ColorVocabularyTrial

        trials = ColorVocabularyTrial.query.filter_by(participant_id=bot.id).all()
        assert len(trials) == 6
        n_correct = sum(trial.score for trial in trials)
        score = bot.module_states["color_vocabulary_test"][0].performance_check["score"]
        assert score == n_correct
