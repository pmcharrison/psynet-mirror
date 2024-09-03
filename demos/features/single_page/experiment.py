# pylint: disable=unused-import,abstract-method

# This demo illustrates single-page functionality in PsyNet.
#
# Ordinarily in PsyNet, each time we navigate to a new timeline page, the web browser
# loads a new page. However, if we take the single-page approach illustrated below,
# then we can advance to a new page without the browser needing to reload the whole page.
# This can be useful for creating a more seamless user experience.

import logging

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import SuccessfulEndPage
from psynet.timeline import Page, Timeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


class MyPage(Page):
    def __init__(self, question, time_estimate, session_id="default", **kwargs):
        """

        Parameters
        ----------
        question
            The question to ask the participant.

        time_estimate
            The estimated time to complete the page (seconds).

        session_id
            If session_id is not None, then it must be a string. If two consecutive pages occur with the same session_id,
            then when it’s time to move to the second page, the browser will not navigate to a new page, but will instead
            update the Javascript variable psynet.page with metadata for the new page, and will trigger an event called
            pageUpdated. This event can be listened for with Javascript code like
            psynet.trial.onEvent("pageUpdated", function() { ... }).
        """
        super().__init__(
            time_estimate=time_estimate,
            template_path="templates/my-page.html",
            contents={"question": question},
            session_id=session_id,
            **kwargs,
        )

    def get_bot_response(self, experiment, bot):
        return "I am a bot"


class Exp(psynet.experiment.Experiment):
    label = "Single page demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        MyPage("What is your favorite color?", 5),
        MyPage("What is your favorite animal?", 5),
        MyPage("What is your favorite fruit?", 5),
        MyPage("What is your favorite movie?", 5),
        SuccessfulEndPage(),
    )
