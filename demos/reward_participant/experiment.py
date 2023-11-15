import requests
from dallinger import db

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "Reward participant demo"

    timeline = Timeline(
        NoConsent(),
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
        db.session.commit()
        req = requests.get(
            f"http://localhost:5000/reward_participant?unique_id={bot.unique_id}"
        )
        # total_reward == participant.base_payment
        assert (
            "When you press <b>Next</b>, your submission will be approved and you will receive the <b>full study payment of $0.34"
            in str(req.content)
        )

        bot.performance_reward += 1
        db.session.commit()

        req = requests.get(
            f"http://localhost:5000/reward_participant?unique_id={bot.unique_id}"
        )
        # total_reward > participant.base_payment
        assert (
            "When you press <b>Next</b>, your submission will be approved and <b>you will receive the full study payment of $0.34</b>. You will also receive an <b>additional bonus of $0.66</b>."
            in str(req.content)
        )

        # total_reward < min_accumulated_reward_for_abort
        # bot.performance_reward = -1
        # db.session.commit()

        bot.run_to_completion()
