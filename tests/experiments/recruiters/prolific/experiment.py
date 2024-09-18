# pylint: disable=unused-import,abstract-method

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.utils import as_plain_text


class Exp(psynet.experiment.Experiment):
    label = "Prolific demo"

    timeline = Timeline(
        NoConsent(),
        InfoPage("Welcome to the experiment!", time_estimate=5),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 5

    def run_bot(self, bot):
        import pydevd_pycharm

        pydevd_pycharm.settrace(
            "localhost", port=12345, stdoutToServer=True, stderrToServer=True
        )

        page = bot.get_current_page()
        assert page.prompt.text == "Welcome to the experiment!"

        bot.take_page(page)

        # Add tests to check that the right messages are displayed to the participant
        # We want to check that the numbers for payment are right
        assert (
            as_plain_text(bot.get_current_page().prompt.text)
            == 'That\'s the end of the experiment! You will receive a reward of **$0.02** for the time you spent on the experiment. You have also been awarded a performance reward of **$0.00**! Thank you for taking part. Please click "Finish" to complete the HIT.'
        )

        bot.run_to_completion()

        # We also add tests to check that the expected calls to the Prolific API have been made,
        # and that they have the right numbers too
        # See pexpect documentation - https://pexpect.readthedocs.io/en/stable/api/pexpect.html?highlight=expect#pexpect.spawn.expect
        # Might have to use regex to match the log call properly
        self.debug_server_process.expect("Simulated Prolific API call: ....")
