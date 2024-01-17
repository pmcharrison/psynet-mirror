import requests

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.participant import Participant
from psynet.process import LocalAsyncProcess, WorkerAsyncProcess
from psynet.recruiters import DevLucidRecruiter, MTurkRecruiter, ProlificRecruiter
from psynet.timeline import CodeBlock, Timeline, switch
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


def worker_function(error_code):
    raise AssertionError(f"Error code {error_code}")


def worker_async_process_error(error_code):
    return CodeBlock(
        lambda participant: WorkerAsyncProcess(
            worker_function,
            arguments={"error_code": error_code},
            participant=participant,
        )
    )


def local_async_process_error(error_code):
    return CodeBlock(
        lambda participant: LocalAsyncProcess(
            worker_function,
            arguments={"error_code": error_code},
            participant=participant,
        )
    )


class Exp(psynet.experiment.Experiment):
    label = "Error handling demo"

    config = {
        "lucid_api_key": "secret",
        "lucid_sha1_hashing_key": "secret",
        "lucid_recruitment_config": "file:./lucid_recruitment_config.json",
        "show_abort_button": True,
        "show_reward": False,
    }

    def need_more_participants(self):
        return Participant.query.count() < 4

    timeline = Timeline(
        NoConsent(),
        InfoPage("Welcome to the experiment!", time_estimate=5),
        switch(
            "switch",
            # lambda participant: 3,
            lambda participant: (participant.id - 1) % 4,
            {
                0: ErrorOnSubmitResponse(38574, "Lorem ipsum", time_estimate=5),
                1: ErrorOnGetPage(82626, "Lorem ipsum", time_estimate=5),
                2: worker_async_process_error(48473),
                3: local_async_process_error(73722),
            },
        ),
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

    def take_pages_and_make_request(self, bot):
        for i in range(2):
            page = bot.get_current_page()
            bot.take_page(page)
        return requests.post(
            "http://localhost:5000/error-page", data={"participant_id": bot.id}
        )

    test_n_bots = 4

    def run_bot(self, bot):
        # Hotair
        if bot.id == 1:
            req = self.take_pages_and_make_request(bot)
            assert (
                "There has been an error and so you are unable to continue, sorry!"
                in str(req.content)
            )
            bot.run_to_completion()

        # Lucid
        if bot.id == 2:
            self.var.with_recruiter = "lucid"
            req = self.take_pages_and_make_request(bot)
            assert "Redirecting to Lucid Marketplace..." in str(req.content)
            bot.run_to_completion()

        # MTurk
        if bot.id == 3:
            self.var.with_recruiter = "mturk"
            req = self.take_pages_and_make_request(bot)
            assert (
                "There has been an error and so you are unable to continue, sorry!"
                in str(req.content)
            )
            assert (
                "You may be able to abort the experiment using the <strong>Abort experiment</strong> button below."
                in str(req.content)
            )
            assert (
                "Once aborted, there is no need to contact us to receive the compensation; this should be awarded to you automatically shortly."
                in str(req.content)
            )
            assert (
                'If this is not the case, please contact us at <a href="mailto:XXX@gmail.com">XXX@gmail.com</a> quoting the following information:'
                in str(req.content)
            )
            bot.run_to_completion()

        # Prolific
        if bot.id == 4:
            self.var.with_recruiter = "prolific"
            req = self.take_pages_and_make_request(bot)
            assert (
                "There has been an error and so you are unable to continue, sorry!"
                in str(req.content)
            )
            assert (
                "Don\\'t worry, your progress has been recorded. To enquire about compensation, please send the researcher a message via the Prolific website and describe what led to your error."
                in str(req.content)
            )
            bot.run_to_completion()
