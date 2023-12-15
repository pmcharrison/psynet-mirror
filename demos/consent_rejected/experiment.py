from typing import List

import requests

import psynet.experiment
from psynet.bot import Bot
from psynet.consent import MainConsent
from psynet.page import SuccessfulEndPage
from psynet.recruiters import DevLucidRecruiter, MTurkRecruiter, ProlificRecruiter
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "Consent rejected demo"
    initial_recruitment_size = 1

    config = {
        "lucid_api_key": "secret",
        "lucid_sha1_hashing_key": "secret",
        "lucid_recruitment_config": "file:./lucid_recruitment_config.json",
        "min_accumulated_reward_for_abort": 0.15,
        "show_abort_button": True,
        "show_reward": False,
    }

    timeline = Timeline(
        MainConsent(),
        SuccessfulEndPage(),
    )

    def with_recruiter(self, nickname):
        # We use this for patching the recruiter while testing the recruiter UI
        if self.var.has("with_recruiter"):
            patched_recruiter = self.var.with_recruiter
            if nickname == "mturk":
                self.recruiter = MTurkRecruiter(skip_config_validation=True)
            elif nickname == "prolific":
                self.recruiter = ProlificRecruiter()
            elif nickname == "lucid":
                self.recruiter = DevLucidRecruiter()
            return nickname == patched_recruiter
        return super().with_recruiter(nickname)

    def take_page_and_make_request(self, bot):
        bot.take_page(bot.get_current_page(), response={"main_consent": False})
        return requests.get(f"http://localhost:5000/timeline?unique_id={bot.unique_id}")

    test_n_bots = 4

    def run_bot(self, bot):
        # Hotair
        if bot.id == 1:
            req = self.take_page_and_make_request(bot)
            assert "Consent was rejected." in str(req.content)
            assert "End of experiment." in str(req.content)
            assert 'Please click "Finish" to complete the experiment.' in str(
                req.content
            )
            bot.run_to_completion()

        # Lucid
        if bot.id == 2:
            self.var.with_recruiter = "lucid"
            req = self.take_page_and_make_request(bot)
            assert "Consent was rejected." not in str(req.content)
            assert "End of experiment." not in str(req.content)
            bot.run_to_completion()

        # MTurk
        if bot.id == 3:
            self.var.with_recruiter = "mturk"
            req = self.take_page_and_make_request(bot)
            assert "Consent was rejected." in str(req.content)
            assert "End of experiment." in str(req.content)
            assert 'Please click "Finish" to complete the HIT.' in str(req.content)
            bot.run_to_completion()

        # Prolific
        if bot.id == 4:
            self.var.with_recruiter = "prolific"
            req = self.take_page_and_make_request(bot)
            assert "Consent was rejected." in str(req.content)
            assert "End of experiment." in str(req.content)
            assert 'Please click "Finish" to complete the study.' in str(req.content)
            bot.run_to_completion()

    def test_check_bots(self, bots: List[Bot]):
        super().test_check_bots(bots, failed=True)
