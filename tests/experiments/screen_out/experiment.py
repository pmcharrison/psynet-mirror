import json

from markupsafe import Markup

import psynet.experiment
from psynet.asset import LocalStorage
from psynet.consent import MainConsent
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


def get_prolific_settings():
    with open("qualification_prolific_en.json", "r") as f:
        qualification = json.dumps(json.load(f))

    return {
        "recruiter": "prolific",
        "base_payment": 0.50,
        "prolific_estimated_completion_minutes": 1,
        "prolific_recruitment_config": qualification,
        "auto_recruit": False,
        "currency": "£",
        "wage_per_hour": 0.9,
    }


class Exp(psynet.experiment.Experiment):
    label = "Audio game - play with sounds."
    asset_storage = LocalStorage()
    initial_recruitment_size = 1
    config = {
        **get_prolific_settings(),
        "initial_recruitment_size": 1,
        "force_incognito_mode": False,
        "title": "Software Testing Session (Chrome browser, ~1 min)",
        "description": "This is a short technical test of our experimental software. While this is not a real experiment, you will be compensated for your time at the regular rate. We appreciate your help in testing our system.",
        "contact_email_on_error": "computational.audition@gmail.com",
        "organization_name": "Max Planck Institute for Empirical Aesthetics",
        "show_reward": False,
    }

    timeline = Timeline(
        MainConsent(),
        ScreenOutPage("screen_out", time_estimate=30),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

    def test_experiment(self):
        super().test_experiment()
