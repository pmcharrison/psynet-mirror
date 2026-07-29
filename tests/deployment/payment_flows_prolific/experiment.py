"""
Prolific Recruiter Test Experiment
==================================

This experiment is designed to test the integration between PsyNet and the Prolific recruiter.
It simulates different participant flows to ensure that screen-out and reward mechanisms work as expected
when using Prolific.

Participants are assigned to one of four experiment flows based on their participant ID (ID % 4):
    0. **Normal plus performance reward**: Participant completes the full experiment and also receives
        a performance reward increment. They get base payment plus £0.10 bonus.
    1. **Normal**: Participant completes a simple flow (consent, info pages, and debrief; ~4.5 minutes
        estimated). They get the full £0.50 base payment.
    2. **Failed prescreening**: Participant fails a prescreen after accruing 3 minutes (1-minute consent
        plus 2-minute info page), i.e. £0.50 at wage_per_hour = 10.
    3. **Errored**: Participant hits a deliberate error after accruing the same 3 minutes and lands on
        the error page (skipped for bots so that automated tests pass).

See ``experiment.py.prolific`` for how unsuccessful participants (flows 2 and 3) are paid under the
different Prolific deployment configurations, and for the checks the experimenter should perform in
the Prolific dashboard.

This default file uses the HotAir recruiter so running the directory
directly cannot accidentally start paid recruitment. The deployable paid
variant lives in ``experiment.py.prolific`` (with ``config.txt.prolific``)
and is intended to be deployed and run with real participants.
"""

# pylint: disable=unused-import,abstract-method,unused-argument

import os
import sys

import psynet.experiment
from psynet.page import InfoPage, UnsuccessfulEndPage
from psynet.timeline import CodeBlock, Timeline, join, switch
from psynet.utils import get_logger

# The vendored consents_cococo package (copied from
# https://gitlab.com/computational-audition-lab/cococo-shared) uses absolute
# imports, so the experiment directory must be on sys.path: Dallinger imports
# the experiment as the dallinger_experiment package from a temp copy.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from consents_cococo.consent_cultural_foundation import (  # noqa: E402
    consent_irb_cultural_foundation,
    debrief_page,
)

logger = get_logger()


def normal():
    return join(
        InfoPage(
            "In this simulation, you are a participant who completed the full experiment as expected.",
            time_estimate=1 * 60,
        ),
    )


def failed_prescreening():
    return join(
        InfoPage(
            "In this simulation, you are a participant whose device proved to be incompatible with the experiment requirements.",
            time_estimate=0,
        ),
        UnsuccessfulEndPage(),
    )


class SimulatedExperimentError(Exception):
    """Deliberate error used to test error-page payment handling."""


def _raise_simulated_error(participant):
    from psynet.bot import Bot

    if isinstance(participant, Bot):
        # Automated (bot) test runs should not crash on the simulated error;
        # only real participants exercise the error-page payment flow.
        logger.info("Skipping simulated error for bot participant.")
        return
    raise SimulatedExperimentError(
        "This is a deliberate error raised to test the error page payment flow."
    )


def errored():
    return join(
        InfoPage(
            "In this simulation, you are a participant who is about to experience a technical error. "
            "Please follow the instructions on the next page.",
            time_estimate=0,
        ),
        CodeBlock(_raise_simulated_error),
    )


def normal_plus_performance_reward():
    return join(
        normal(),
        InfoPage(
            "In this simulation you additionally received a small performance reward of £0.10.",
            time_estimate=0,
        ),
        CodeBlock(lambda participant: participant.inc_performance_reward(0.10)),
    )


def get_hotair_settings():
    """Return recruiter settings safe for local runs."""
    return {
        "recruiter": "hotair",
        "base_payment": 0.50,
        "initial_recruitment_size": 12,
        "currency": "£",
        "wage_per_hour": 10,
    }


class Exp(psynet.experiment.Experiment):
    label = "Simple test experiment"

    config = {
        **get_hotair_settings(),
        "force_incognito_mode": False,
        "title": "Test experiment (Chrome browser, ~1-2 min)",
        "description": "This is a short technical test of our experimental software. While this is not a real experiment, you will be compensated for your time at the regular rate. We appreciate your help in testing our system.",
        "contact_email_on_error": "computational.audition@gmail.com",
        "organization_name": "Max Planck Institute for Empirical Aesthetics",
        "show_reward": False,
    }

    timeline = Timeline(
        # DURATION/PAYMENT are passed explicitly because this experiment sets
        # its payment settings in Exp.config rather than config.txt, where the
        # consent module would read them.
        consent_irb_cultural_foundation(consent="MAIN", DURATION=2, PAYMENT=0.50),
        InfoPage(
            "What happens next will depend on chance. Either way, you will receive some payment for your time. However, we will be trialling different methods of payment to make sure they are all working properly.",
            # Together with the 1-minute consent page, a participant screened
            # out after this page has accrued 3 minutes, i.e. £0.50 at
            # wage_per_hour = 10.
            time_estimate=2 * 60,
        ),
        switch(
            "participant_flow",
            lambda participant: participant.id % 4,
            {
                0: normal_plus_performance_reward(),
                1: normal(),
                2: failed_prescreening(),
                3: errored(),
            },
        ),
        debrief_page(),
    )
