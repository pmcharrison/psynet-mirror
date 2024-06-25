import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import TextControl, ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.participant import Participant
from psynet.process import LocalAsyncProcess, WorkerAsyncProcess
from psynet.timeline import CodeBlock, Timeline, switch, join
from psynet.utils import get_logger

logger = get_logger()


class ErrorOnSubmitResponse(InfoPage):
    def __init__(self, error_code, *args, **kwargs):
        self.error_code = error_code
        super().__init__(*args, **kwargs)

    def format_answer(self, raw_answer, **kwargs):
        raise ValueError(f"Error code {self.error_code}")


class ErrorOnGetPage(InfoPage):
    def __init__(self, error_code, *args, **kwargs):
        self.error_code = error_code
        super().__init__(*args, **kwargs)

    def render(self, experiment, participant):
        raise RuntimeError(f"Error code {self.error_code}")


class Exp(psynet.experiment.Experiment):
    label = "Error handling demo"

    def logic_participant_error(self, participant):
        return join(
            ModularPage(
                "error_handler",
                """
                We're really sorry, it looks like an error occurred.
                We would appreciate it if you could leave a few words here
                to describe what happened.
                """,
                TextControl(),
            ),
            InfoPage(
                "Thank you very much, you can now close the window.",
            )
        )

    def need_more_participants(self):
        return Participant.query.count() < 2

    timeline = Timeline(
        NoConsent(),
        InfoPage("Welcome to the experiment!", time_estimate=5),
        switch(
            "switch",
            lambda: 0,
            # lambda participant: (participant.id - 1) % 4,
            {
                0: ErrorOnSubmitResponse(38574, "Lorem ipsum", time_estimate=5),
                1: ErrorOnGetPage(82626, "Lorem ipsum", time_estimate=5),
            },
        ),
        SuccessfulEndPage(),
    )

    def test_experiment(self):
        pass
