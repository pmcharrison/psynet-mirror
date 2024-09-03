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
        super().__init__(
            time_estimate=time_estimate,
            template_path="templates/my-page.html",
            contents={"question": question},
            session_id=session_id,
            **kwargs,
        )


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
