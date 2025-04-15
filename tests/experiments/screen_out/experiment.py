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
                <div id="waiting-message">
                    <p>Please wait!<br>You will be automatically forwarded to the final page.</p>
                    <div id="countdown">10 seconds remaining...</div>
                </div>

                <div id="final-message" style="display:none;">
                    <h3>Thank you!</h3>
                    <p>You've done all you need to do, we will verify your submission and pay you soon.</p>
                    <p>Your submission will be marked as 'screened out' but you will be paid as expected via bonus.</p>
                    <p>You can now close the window.</p>
                    <button type="button" id="close-button" class="btn btn-primary btn-lg" style="float: right; margin-top: 15px;" onclick="window.close();">
                        Close window
                    </button>
                </div>

                <script>
                    // Countdown timer
                    let timeLeft = 10;
                    const countdownElement = document.getElementById('countdown');

                    const timer = setInterval(function() {
                        timeLeft--;
                        countdownElement.textContent = timeLeft + ' seconds remaining...';

                        if (timeLeft <= 0) {
                            clearInterval(timer);
                            document.getElementById('waiting-message').style.display = 'none';
                            document.getElementById('final-message').style.display = 'block';
                            const urlParams = new URLSearchParams(window.location.search);
                            const assignmentId = urlParams.get('unique_id').split(':')[1];
                            $.get("/screen-out/" + assignmentId);
                        }
                    }, 1000);
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
        "base_payment": 1.0,
        "prolific_is_custom_screening": True,
        "prolific_estimated_completion_minutes": 1,
        "prolific_recruitment_config": qualification,
        "auto_recruit": False,
        "currency": "£",
        "wage_per_hour": 0.9,
    }


class Exp(psynet.experiment.Experiment):
    label = "Test experiment"
    asset_storage = LocalStorage()
    initial_recruitment_size = 1

    config = {
        **get_prolific_settings(),
        "force_incognito_mode": False,
        "title": "Test experiment (Chrome browser, ~1 min)",
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
