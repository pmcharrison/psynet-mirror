"""
Prolific Recruiter Test Experiment
==================================

This experiment is designed to test the integration between PsyNet and the Prolific recruiter.
It simulates different participant flows to ensure that screen-out and reward mechanisms work as expected
when using Prolific.

Participants are assigned to one of three experiment flows based on their participant ID:
    1. **Normal**: Participant completes a simple flow.
    2. **Failed prescreening**: Participant is subjected to the Antiphase Headphone Test which they fail.
    3. **Increment performance reward**: Participant receives a performance reward increment.

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
from psynet.asset import LocalStorage
from psynet.consent import MainConsent
from psynet.page import InfoPage
from psynet.prescreen import AntiphaseHeadphoneTest
from psynet.timeline import CodeBlock, Timeline, conditional, join
from psynet.utils import get_logger

logger = get_logger()


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
        "wage_per_hour": 9,
    }


def normal():
    return join(
        InfoPage("Click the button below.", time_estimate=5),
        InfoPage("You finished the experiment!", time_estimate=5),
    )


def failed_prescreening():
    return join(
        AntiphaseHeadphoneTest(performance_threshold=7),
        InfoPage(
            "You failed the prescreening test.",
            time_estimate=5,
        ),
        InfoPage("You finished the experiment!", time_estimate=5),
    )


def increment_performance_reward():
    return join(
        CodeBlock(lambda participant: participant.inc_performance_reward(0.50)),
        InfoPage("You have been awarded a performance reward.", time_estimate=5),
        InfoPage("You finished the experiment!", time_estimate=5),
    )


##########################################################################################
# Experiment
##########################################################################################
class Exp(psynet.experiment.Experiment):
    label = "Simple test experiment"
    asset_storage = LocalStorage()
    initial_recruitment_size = 1

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
        MainConsent(),
        conditional(
            "is_normal",
            lambda participant: participant.id % 3 == 1,
            normal(),
            conditional(
                "is_failed_prescreening",
                lambda participant: participant.id % 3 == 2,
                failed_prescreening(),
                increment_performance_reward(),
            ),
        ),
    )
