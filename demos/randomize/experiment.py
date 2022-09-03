import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline, randomize
from psynet.utils import get_logger

logger = get_logger()


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    label = "Randomize demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        randomize(
            label="Numbers from 0-99",
            logic=[InfoPage(f"{i}", time_estimate=5) for i in range(100)],
        ),
        SuccessfulEndPage(),
    )

    def test_run_bot(self, bot):
        observed = []
        for i in range(100):
            observed.append(str(bot.get_current_page().prompt))
            bot.take_page()
        assert sorted(observed) == [str(i) for i in range(100)]
        bot.run_to_completion()
