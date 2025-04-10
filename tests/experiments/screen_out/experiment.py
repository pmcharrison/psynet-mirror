from markupsafe import Markup

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, Prompt
from psynet.timeline import Timeline


class ScreenOutPage(ModularPage):
    def __init__(self, label: str, time_estimate: float):
        prompt = Markup(
            (
                """
                Thank you, you've done all you need to do, we will verify your submission and pay you soon.
                Your submission will be marked as 'screened out' but you will be paid as expected via bonus.
                <script>
                    $.get("/screen-out-pass/1");
                </script>
            """
            )
        )
        super().__init__(
            label,
            Prompt(prompt),
            show_next_button=False,
            time_estimate=time_estimate,
        )


class Exp(psynet.experiment.Experiment):
    label = "Screen out"

    timeline = Timeline(
        NoConsent(),
        ScreenOutPage("screen_out", time_estimate=0),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

    def test_experiment(self):
        super().test_experiment()
