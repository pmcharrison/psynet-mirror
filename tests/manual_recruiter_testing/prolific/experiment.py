"""
Prolific Recruiter Test Experiment
==================================

This experiment is designed to test the integration between PsyNet and the Prolific recruiter.
It simulates different participant flows to ensure that screen-out and reward mechanisms work as expected
when using Prolific.

Participants are assigned to one of three experiment flows based on their participant ID:
    1. **Normal**: Participant completes a simple flow. They are compensated for 3 minutes of participation, so get the full £0.45 base payment.
    2. **Failed prescreening**: Participant fails a prescreen. They are only compensated for 2 minutes of participation, so get no base payment, but £0.33 bonus.
    3. **Increment performance reward**: Participant completes the full experiment and also receives a performance reward increment. They get base payment plus £0.10 bonus.


The experimenter should check the following in the Prolific dashboard:
1. Recruitment: Verify that participants are correctly recruited and appear in the Prolific dashboard for the study.
2. Completion Status: Check that participants (ID % 3 == 0 and ID % 3 == 2) who complete the experiment are marked
    as complete in both Prolific and PsyNet.
3. Prescreening Failures: Confirm that participants (ID % 3 == 1) who fail the prescreening are handled appropriately
    (e.g., marked as returned/screened-out in both Prolific and PsyNet).
4. Bonus/Reward Payments: For participants (ID % 3 == 2) in the increment performance reward flow, ensure that
    the bonus payment is correctly set in both Prolific and PsyNet.

This test is intended to be deployed and run with real participants.
"""

# pylint: disable=unused-import,abstract-method,unused-argument

import json

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, UnsuccessfulEndPage
from psynet.timeline import CodeBlock, Timeline, join, switch
from psynet.utils import get_logger

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


def normal_plus_performance_reward():
    return join(
        normal(),
        InfoPage(
            "In this simulation you additionally received a small performance reward of £0.10.",
            time_estimate=0,
        ),
        CodeBlock(lambda participant: participant.inc_performance_reward(0.10)),
    )


def get_prolific_settings():
    with open("qualification_prolific_en.json", "r") as f:
        qualification = json.dumps(json.load(f))

    return {
        "recruiter": "prolific",
        "base_payment": 0.45,
        "prolific_is_custom_screening": True,
        "prolific_estimated_completion_minutes": 1,
        "prolific_recruitment_config": qualification,
        "auto_recruit": False,
        "currency": "£",
        "wage_per_hour": 9,
    }


class Exp(psynet.experiment.Experiment):
    label = "Simple test experiment"

    config = {
        **get_prolific_settings(),
        "force_incognito_mode": False,
        "title": "Test experiment (Chrome browser, ~1-2 min)",
        "description": "This is a short technical test of our experimental software. While this is not a real experiment, you will be compensated for your time at the regular rate. We appreciate your help in testing our system.",
        "contact_email_on_error": "computational.audition@gmail.com",
        "organization_name": "Max Planck Institute for Empirical Aesthetics",
        "show_reward": False,
        # The experiment should be tested with three configurations (three deployments):
        # 1. prolific_enable_screen_out = True, prolific_enable_return_for_bonus = True
        # 2. prolific_enable_screen_out = False, prolific_enable_return_for_bonus = True
        # 3. prolific_enable_screen_out = False, prolific_enable_return_for_bonus = False
        "prolific_enable_screen_out": True,
        "prolific_enable_return_for_bonus": True,
    }

    timeline = Timeline(
        NoConsent(),
        InfoPage(
            "What happens next will depend on chance. Either way, you will receive some payment for your time. However, we will be trialling different methods of payment to make sure they are all working properly.",
            time_estimate=(
                2 * 60
            ),  # If the wage_per_hour = 10, then this will mean a payment of 0.33
        ),
        switch(
            "participant_flow",
            lambda participant: participant.id % 3,
            {
                0: normal_plus_performance_reward(),
                1: normal(),
                2: failed_prescreening(),
            },
        ),
    )
