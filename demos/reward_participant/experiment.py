import requests
from dallinger import db

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "Reward participant demo"

    timeline = Timeline(
        NoConsent(),
        InfoPage("Reward participant demo", time_estimate=101),
        SuccessfulEndPage(),
    )

    def with_recruiter(self, nickname):
        # We use this for patching the recruiter while testing the recruiter UI
        if self.var.has("with_recruiter"):
            patched_recruiter = self.var.with_recruiter
            return nickname == patched_recruiter

        return super().with_recruiter(nickname)

    def run_bot(self, bot):
        # Prolific
        self.var.with_recruiter = "prolific"

        # reward == base_payment (0.34 == 0.34)
        page = bot.get_current_page()
        bot.take_page(page)
        assert round(bot.time_reward(), 2) == 0.34
        db.session.commit()
        req = requests.get(
            f"http://localhost:5000/reward_participant?unique_id={bot.unique_id}"
        )
        assert (
            "When you press <b>Next</b>, your submission will be approved and you will receive the full study payment of <b>$0.34</b>."
            in str(req.content)
        )

        # reward > participant.base_payment (0.5 > 0.34)
        assert round(bot.time_reward(), 2) == 0.34
        bot.performance_reward = 0.16
        db.session.commit()

        req = requests.get(
            f"http://localhost:5000/reward_participant?unique_id={bot.unique_id}"
        )
        assert (
            "When you press <b>Next</b>, your submission will be approved and you will receive the full study payment of <b>$0.34</b>. "
            + "You will also receive an additional bonus of <b>$0.16</b>."
            in str(req.content)
        )

        # reward < min_accumulated_reward_for_abort (0.19 < 0.2)
        assert round(bot.time_reward(), 2) == 0.34
        bot.performance_reward -= 0.31
        db.session.commit()

        req = requests.get(
            f"http://localhost:5000/reward_participant?unique_id={bot.unique_id}"
        )
        assert (
            "You did not complete enough of the experiment to receive a payment, sorry. Please return the study."
            in str(req.content)
        )

        # min_accumulated_reward_for_abort = reward < base_payment (0.2 == 0.2 < 0.34)
        assert round(bot.time_reward(), 2) == 0.34
        bot.performance_reward += 0.01
        db.session.commit()

        req = requests.get(
            f"http://localhost:5000/reward_participant?unique_id={bot.unique_id}"
        )
        assert (
            "You were unable to complete the experiment, but you will still be paid <b>$0.34</b> for the time you put in so far. "
            + "When you press <b>Next</b>, we will pay you via the bonus mechanism. Please then return the study."
            in str(req.content)
        )

        # min_accumulated_reward_for_abort < reward < base_payment (0.2 < 0.21 < 0.34)
        assert round(bot.time_reward(), 2) == 0.34
        bot.performance_reward += 0.01
        db.session.commit()

        req = requests.get(
            f"http://localhost:5000/reward_participant?unique_id={bot.unique_id}"
        )
        assert (
            "You were unable to complete the experiment, but you will still be paid <b>$0.34</b> for the time you put in so far. "
            + "When you press <b>Next</b>, we will pay you via the bonus mechanism. Please then return the study."
            in str(req.content)
        )

        bot.run_to_completion()
