import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil

import dallinger.recruiters
import dominate
import flask
import pandas as pd
import requests
import sqlalchemy
from dallinger import db
from dallinger.config import get_config
from dallinger.db import session
from dallinger.notifications import admin_notifier, get_mailer
from dallinger.recruiters import (
    DevRecruiter,
    MockRecruiter,
    RecruitmentStatus,
    RedisStore,
)
from dallinger.utils import get_base_url
from dominate import tags
from dominate.util import raw
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.sql import func

from .consent import AudiovisualConsent, LucidConsent, OpenScienceConsent
from .data import SQLBase, SQLMixin, register_table
from .lucid import LucidService, get_lucid_service
from .page import InfoPage
from .participant import Participant
from .timeline import (
    AsyncCodeBlock,
    CodeBlock,
    PageMaker,
    Response,
    TimelineLogic,
    conditional,
    join,
    while_loop,
)
from .utils import get_logger, get_translator, render_template_with_translations

logger = get_logger()


def screen_out_participant(participant):
    """
    Standalone function for AsyncCodeBlock to use (can be serialized properly)
    """
    from psynet.experiment import get_experiment

    experiment = get_experiment()
    recruiter = experiment.recruiter

    return recruiter.screen_out(participant, participant.calculate_reward())


class PsyNetRecruiterMixin:
    show_termination_button = False

    def terminate_participant(
        self, participant=None, assignment_id=None, reason=None, details=None
    ):
        raise NotImplementedError

    def release_participant(self, experiment, participant) -> TimelineLogic:
        return self.approve_assignment()

    def approve_assignment(self) -> TimelineLogic:
        # This calls dallinger.submitAssignment,
        # and this will tell Dallinger to approve the assignment and pay the base payment,
        # AND it also pays the participant a bonus, calculated from participant.bonus()
        from .page import ExecuteFrontEndJS

        _p = get_translator(context=True)

        return ExecuteFrontEndJS(
            "dallinger.submitAssignment()",
            message=_p(
                "recruiter_communication",
                "Communicating with the recruiter...",
            ),
        )

    def check_consents(self, consents):
        """
        Check that the consent elements are suitable for the recruiter.
        By default this check is skipped in ``psynet debug local``.

        Parameters
        ----------
        consents : list
            List of consent objects from the timeline
        """
        if len(consents) == 0:
            raise RuntimeError(
                "It looks like your experiment is missing a consent page. "
                "Is that right? You can resolve this check by adding a pre-prepared consent page from psynet.consent "
                "to your timeline, or a custom subclass of psynet.consent.Consent, "
                "or psynet.consent.NoConsent to skip this check entirely."
            )


class HotAirRecruiter(PsyNetRecruiterMixin, dallinger.recruiters.HotAirRecruiter):
    def get_status(self) -> RecruitmentStatus:
        from .experiment import get_experiment

        status = super().get_status()
        exp = get_experiment()
        status.study_status = (
            "Recruiting" if exp.need_more_participants else "Not recruiting"
        )
        return status


class PsyNetProlificRecruiterMixin(PsyNetRecruiterMixin):
    def screen_out(self, participant, bonus):
        response = super().screen_out(participant, bonus)
        message = response.get("message")
        success = (
            message == "The request to bulk screen out has been made successfully."
        )
        if success:
            logger.info(message)
        else:
            logger.warning(f"Screen out failed: {response}")

        participant.var.prolific_screen_out_successful = success

        return success

    def release_participant(
        self, experiment, participant: Participant
    ) -> TimelineLogic:
        if participant.failed:
            return self.reject_assignment(participant)
        return self.approve_assignment()

    def reject_assignment(self, participant) -> TimelineLogic:
        return PageMaker(self._reject_assignment, time_estimate=0.0)

    def successful_screenout_logic(self) -> TimelineLogic:
        """Create the TimelineLogic for successful screen out."""
        _p = get_translator(context=True)

        return InfoPage(
            _p(
                "screen_out_successful",
                "You have been credited for the time spent on the experiment. "
                "Because you could not progress to the main experiment "
                "your submission will appear as 'screened out' in Prolific. "
                "You can now close this browser window.",
            ),
            show_next_button=False,
            time_estimate=0.0,
        )

    def assignment_returned_logic(self) -> TimelineLogic:
        """Create the TimelineLogic for checking assignment return status."""
        _p = get_translator(context=True)

        return join(
            CodeBlock(
                lambda participant: participant.var.set("assignment_returned", False)
            ),
            InfoPage(
                _p(
                    "return_assignment_instructions",
                    "Please return your submission via the Prolific interface and click Next. "
                    "We will then automatically pay you a bonus for your time.",
                ),
                time_estimate=0.5,
            ),
            while_loop(
                "wait_for_assignment_return",
                condition=lambda participant: not participant.var.assignment_returned,
                logic=join(
                    AsyncCodeBlock(
                        self.check_assignment_return_status,
                        wait=True,
                        expected_wait=5.0,
                        check_interval=1.0,
                    ),
                    conditional(
                        label="assignment_return_result",
                        condition=lambda participant: participant.var.assignment_returned,
                        logic_if_true=join(
                            CodeBlock(self.reward_and_set_bonus),
                            InfoPage(
                                _p(
                                    "return_for_bonus_completed",
                                    "That worked! You have been credited for the time spent on the experiment. "
                                    "Thank you for participating. You can now close this browser window.",
                                ),
                                show_next_button=False,
                                time_estimate=0.0,
                            ),
                        ),
                        logic_if_false=InfoPage(
                            _p(
                                "assignment_return_retry",
                                "That didn't work. Are you sure you returned the submission for this study? "
                                "Please go to the Prolific interface, make sure you have returned the submission, "
                                "then click the 'Next' button.",
                            ),
                            time_estimate=0.5,
                        ),
                    ),
                ),
                expected_repetitions=1,
            ),
        )

    def return_for_bonus_logic(self, enable_return_for_bonus) -> TimelineLogic:
        """Create the TimelineLogic for returning the assignment in order to receive the bonus."""
        if not enable_return_for_bonus:
            return None

        _p = get_translator(context=True)

        return conditional(
            "return_for_bonus_enabled",
            lambda participant: enable_return_for_bonus,
            join(
                InfoPage(
                    _p(
                        "return_for_bonus_enabled",
                        "We are sorry that you could not proceed to the main experiment, "
                        "but we will still pay you for your time spent so far. "
                        "To receive this payment, we need you to return this assignment "
                        "via the Prolific interface, then click the 'Next' button below.",
                    ),
                    time_estimate=0.5,
                ),
                self.assignment_returned_logic(),
            ),
            None,
        )

    def return_and_message_experimenter_logic(self) -> TimelineLogic:
        """Create the TimelineLogic for returning the assignment and messaging the experimenter."""
        _p = get_translator(context=True)

        return InfoPage(
            _p(
                "screen_out_return_and_message_experimenter",
                "We are sorry that you could not proceed to the main experiment. "
                "To receive this payment for your time, please return your assignment in Prolific "
                "and send a message to the experimenter via the Prolific messaging system. "
                "The experimenter will review your case and arrange payment if appropriate. "
                "Thank you for your understanding. "
                "You can now close this browser window.",
            ),
            show_next_button=False,
            time_estimate=0.5,
        )

    def screen_out_logic(self, enable_screen_out) -> TimelineLogic:
        """Create the TimelineLogic for screen out."""
        if not enable_screen_out:
            return None

        return conditional(
            "screen_out_enabled",
            lambda participant: enable_screen_out,
            join(
                AsyncCodeBlock(
                    screen_out_participant,
                    wait=True,
                    expected_wait=5.0,
                    check_interval=0.5,
                ),
                conditional(
                    label="screen_out_successful",
                    condition=self.check_screen_out_successful,
                    logic_if_true=self.successful_screenout_logic(),
                ),
            ),
            None,
        )

    def _reject_assignment(self, participant) -> TimelineLogic:
        enable_return_for_bonus = get_config().get("prolific_enable_return_for_bonus")
        enable_screen_out = get_config().get("prolific_enable_screen_out")

        logic_screen_out = self.screen_out_logic(enable_screen_out)
        logic_return_for_bonus = self.return_for_bonus_logic(enable_return_for_bonus)
        logic_return_and_message_experimenter = (
            self.return_and_message_experimenter_logic()
        )

        return join(
            logic_screen_out,
            logic_return_for_bonus,
            logic_return_and_message_experimenter,
        )

    def check_screen_out_successful(self, participant) -> bool:
        """Check if the participant has been successfully screened out."""
        try:
            return participant.var.prolific_screen_out_successful
        except KeyError:
            return False

    @staticmethod
    def check_assignment_return_status(participant) -> bool:
        """Check and update the participant's assignment return status via API call.

        Returns:
            bool: True if assignment is returned, False otherwise
        """
        from psynet.experiment import get_experiment

        experiment = get_experiment()
        recruiter = experiment.recruiter
        logger.info(
            f"Checking Prolific submission status for assignment {participant.assignment_id}"
        )
        submission = recruiter.prolificservice.get_participant_submission(
            participant.assignment_id
        )
        logger.info(
            f"Received Prolific submission response for assignment {participant.assignment_id}: {submission}"
        )
        is_returned = submission and submission.get("status") == "RETURNED"
        participant.var.assignment_returned = is_returned
        return is_returned

    @staticmethod
    def reward_and_set_bonus(participant):
        from psynet.experiment import get_experiment

        experiment = get_experiment()
        recruiter = experiment.recruiter

        bonus = participant.calculate_reward()
        recruiter.reward_bonus(
            participant,
            bonus,
            "Partial payment for incomplete participation",
        )
        participant.bonus = bonus

    def check_for_returned_assignment(self, participant) -> bool:
        """Check if the participant has returned the assignment."""
        try:
            return participant.var.assignment_returned
        except KeyError:
            return False


class ProlificRecruiter(
    PsyNetProlificRecruiterMixin, dallinger.recruiters.ProlificRecruiter
):
    def open_recruitment(self, n: int = 1) -> dict:
        response = super().open_recruitment(n)

        from .experiment import get_experiment

        exp = get_experiment()
        study_details = exp.notifier.url(
            exp.notifier.bold("Study details"),
            f"https://app.prolific.com/researcher/workspaces/studies/{self.current_study_id}",
        )
        submissions = exp.notifier.url(
            exp.notifier.bold("Submissions"),
            f"https://app.prolific.com/researcher/workspaces/studies/{self.current_study_id}/submissions",
        )
        msg = f"Prolific:\n- {study_details}\n- {submissions}"
        exp.notifier.notify(msg)
        return response

    def run_checks(self):
        logger.info("Polling Prolific API to check for unread messages")
        unread_messages = self.prolificservice.get_unread_messages()
        relevant_messages = []
        for message in unread_messages:
            study_id = message["data"].get("study_id")
            if study_id and study_id == self.current_study_id:
                message_concat = " ".join(
                    [message[key] for key in ["sender_id", "body", "sent_at"]]
                )
                message_hash = hashlib.md5(message_concat.encode()).hexdigest()
                from psynet.redis import redis_vars

                if redis_vars.get(message_hash, None) is None:
                    redis_vars.set(message_hash, "seen")
                    relevant_messages.append(message)

        if len(relevant_messages) > 0:
            from .experiment import get_experiment

            exp = get_experiment()
            messages = [f"Found {len(relevant_messages)} unread messages"]
            for message in relevant_messages:
                sender_id = message.get("sender_id")
                body = message.get("body")
                sent_at = message.get("sent_at")
                msg = exp.notifier.bold("Message from Prolific") + ":\n"
                msg += f"Sender: `{sender_id}` at {sent_at}\n"
                msg += f"> {body}"
                messages.append(msg)
            exp.notifier.notify(exp.notifier.combine(messages))


class DevProlificRecruiter(
    PsyNetProlificRecruiterMixin, dallinger.recruiters.DevProlificRecruiter
):
    pass


class MockProlificRecruiter(
    PsyNetRecruiterMixin, dallinger.recruiters.MockProlificRecruiter
):
    pass


class MTurkRecruiter(PsyNetRecruiterMixin, dallinger.recruiters.MTurkRecruiter):
    pass


# CAP Recruiter
@dataclass
class CapRecruitmentStatus(RecruitmentStatus):
    pass


class BaseCapRecruiter(PsyNetRecruiterMixin, dallinger.recruiters.CLIRecruiter):
    """
    The CapRecruiter base class
    """

    def recruit(self, n=1):
        """Incremental recruitment isn't implemented for now, so we return an empty list."""
        return []

    def open_recruitment(self, n=1):
        """
        Return an empty list which otherwise would be a list of recruitment URLs.
        """
        return {"items": [], "message": ""}

    def close_recruitment(self):
        logger.info("No more participants required. Recruitment stopped.")

    def notify_duration_exceeded(self, participants, reference_time):
        """
        The participant has been working longer than the time defined in
        the "duration" config value.
        """
        for participant in participants:
            participant.status = "abandoned"
            # We preserve this commit just in case Dallinger removes the external commit in the future
            session.commit()

    def reward_bonus(self, participant, amount, reason):
        """
        Return values for `basePay` and `bonus` to cap-recruiter application.
        """
        data = {
            "assignmentId": participant.assignment_id,
            "basePayment": self.config.get("base_payment"),
            "bonus": amount,
            "failed_reason": participant.failure_tags,
        }
        url = self.external_submission_url
        url += "/fail" if participant.failed else "/complete"

        requests.post(
            url,
            json=data,
            headers={"Authorization": os.environ.get("CAP_RECRUITER_AUTH_TOKEN")},
            verify=False,  # Temporary fix because of SSLCertVerificationError
        )

    def get_status(self) -> CapRecruitmentStatus:
        """Return the status of the recruiter as a RecruitmentStatus."""
        from psynet.experiment import get_experiment

        all_participants = Participant.query.all()
        statuses = []
        for participant in all_participants:
            if participant.failed:
                statuses.append("FAILED")
            else:
                if participant.status == "working":
                    statuses.append("WORKING")
                else:
                    statuses.append("COMPLETED")
        status = super().get_status()
        status_counts = dict(Counter(statuses))
        exp = get_experiment()
        study_status = "Recruiting" if exp.need_more_participants else "Not recruiting"

        return CapRecruitmentStatus(
            recruiter_name=self.nickname,
            participant_status_counts=status_counts,
            study_id=status.study_id,
            study_status=study_status,
            study_cost=status.study_cost,
            currency="€",  # Default currency
        )


class CapRecruiter(BaseCapRecruiter):
    """
    The production cap-recruiter.

    """

    nickname = "cap-recruiter"
    external_submission_url = "https://cap-recruiter.ae.mpg.de/tasks"


class StagingCapRecruiter(BaseCapRecruiter):
    """
    The staging cap-recruiter.

    """

    nickname = "staging-cap-recruiter"
    external_submission_url = "https://staging-cap-recruiter.ae.mpg.de/tasks"


class DevCapRecruiter(DevRecruiter, BaseCapRecruiter):
    """
    The development cap-recruiter.

    """

    nickname = "dev-cap-recruiter"
    external_submission_url = "http://localhost:8000/tasks"


# Lucid Recruiter
@register_table
class LucidRID(SQLBase, SQLMixin):
    __tablename__ = "lucid_rid"

    # These fields are removed from the database table as they are not needed.
    failed = None
    failed_reason = None
    time_of_death = None
    vars = None
    creation_time = None

    rid = Column(String, ForeignKey("participant.worker_id"), index=True)
    registered_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    completed_at = Column(DateTime)
    terminated_at = Column(DateTime)
    termination_reason = Column(String)
    termination_details = Column(String)

    # Lucid fields
    lucid_status = Column(String)
    lucid_status_code = Column(Integer)
    lucid_fulcrum_status = Column(Integer)
    lucid_market_place_code = Column(String)
    lucid_entry_date = Column(DateTime)
    lucid_last_date = Column(DateTime)
    lucid_panelist_id = Column(String)
    lucid_respondent_id = Column(String)
    lucid_supplier_id = Column(Integer)

    # to dict
    def to_dict(self):
        return {
            "rid": self.rid,
            "registered_at": self.registered_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "terminated_at": self.terminated_at,
            "termination_reason": self.termination_reason,
            "termination_details": self.termination_details,
            "lucid_status": self.lucid_status,
            "lucid_status_code": self.lucid_status_code,
            "lucid_fulcrum_status": self.lucid_fulcrum_status,
            "lucid_market_place_code": self.lucid_market_place_code,
            "lucid_entry_date": self.lucid_entry_date,
            "lucid_last_date": self.lucid_last_date,
            "lucid_panelist_id": self.lucid_panelist_id,
            "lucid_respondent_id": self.lucid_respondent_id,
            "lucid_supplier_id": self.lucid_supplier_id,
        }


@register_table
class LucidStatus(SQLBase, SQLMixin):
    __tablename__ = "lucid_status"

    # These fields are removed from the database table as they are not needed.
    failed = None
    failed_reason = None
    time_of_death = None
    vars = None

    status = Column(String)
    cost = Column(Float)
    currency = Column(String)
    exchange_rate = Column(Float)
    cost_per_survey = Column(Float)
    payment_per_hour = Column(Float)
    earnings_per_click = Column(Float)
    system_conversion = Column(Integer)
    completion_loi = Column(Integer)
    termination_loi = Column(Integer)
    last_complete_date = Column(DateTime)

    total_entrants = Column(Integer)
    total_completes = Column(Integer)
    total_screens = Column(Integer)
    drop_off_rate = Column(Float)
    conversion_rate = Column(Float)
    incidence_rate = Column(Float)

    def to_dict(self):
        return {
            "timestamp": self.creation_time,
            "status": self.status,
            "cost": self.cost,
            "currency": self.currency,
            "exchange_rate": self.exchange_rate,
            "cost_per_survey": self.cost_per_survey,
            "payment_per_hour": self.payment_per_hour,
            "earnings_per_click": self.earnings_per_click,
            "system_conversion": self.system_conversion,
            "completion_loi": self.completion_loi,
            "termination_loi": self.termination_loi,
            "last_complete_date": self.last_complete_date,
            "total_entrants": self.total_entrants,
            "total_screens": self.total_screens,
            "total_completes": self.total_completes,
            "drop_off_rate": self.drop_off_rate,
            "conversion_rate": self.conversion_rate,
            "incidence_rate": self.incidence_rate,
        }


class LucidRecruiterException(Exception):
    """Custom exception for LucidRecruiter"""


@dataclass
class LucidRecruitmentStatus(RecruitmentStatus):
    survey_sid: str
    survey_number: int
    total_completes: int
    total_entrants: int
    total_screens: int
    completion_loi: int
    drop_off_rate: float
    conversion_rate: float
    incidence_rate: float
    payment_per_hour: float
    exchange_rate: float
    cost_per_survey: float
    earnings_per_click: float
    system_conversion: int
    termination_loi: int
    last_complete_date: datetime
    config: dict


class BaseLucidRecruiter(PsyNetRecruiterMixin, dallinger.recruiters.CLIRecruiter):
    supports_delayed_publishing = True
    MARKETPLACE_CODE = "Marketplace codes"
    IN_SURVEY = "Currently in Client Survey or Drop"
    COMPLETED = "Returned as Complete"
    TERMINATED = "Returned as Terminate"
    SURVEY_CLOSED = "Survey Closed"
    survey_codes = ["awarded", "pending", "paused", "live", "complete", "archived"]
    client_codes = {
        # See https://support.lucidhq.com/s/article/Client-Response-Codes
        -1: MARKETPLACE_CODE,
        1: IN_SURVEY,
        10: COMPLETED,  # Returned as Complete from PsyNet
        11: COMPLETED,  # Adjusted Complete
        20: TERMINATED,  # Terminated from PsyNet
        26: TERMINATED,  # Adjusted Terminate
        28: TERMINATED,  # Adjusted Terminate
        30: TERMINATED,  # Quality termination
        33: TERMINATED,  # Speeder
        34: TERMINATED,  # Open End Terminate
        35: TERMINATED,  # Encryption Failure
        38: TERMINATED,  # Adjusted to Terminate
        134: TERMINATED,  # Encryption Failure at Client Survey
        135: TERMINATED,  # Encryption Failure at Marketplace Return
        136: TERMINATED,  # Survey Closed
        137: TERMINATED,  # Verify Callback Failure
        233: TERMINATED,  # Invalid Client Response Status
        235: TERMINATED,  # Secure Client Callback Failure
        40: TERMINATED,  # Client Survey Quota Full
        60: TERMINATED,  # Quality Terminate on Pre-Client Intermediary Page
        62: TERMINATED,  # Declined Routing on Pre-Client Intermediary Page
        66: TERMINATED,  # Declined Routing on Pre-Client Intermediary Page
        91: TERMINATED,  # Incorrectly Formatted Redirect
        110: TERMINATED,  # Used for specific opt-in studies
        70: COMPLETED,  # Audience: Returned as Complete
        80: TERMINATED,  # Audience: Returned as Terminate
    }

    market_place_codes = {
        -6: "Sent to Marketplace Intermediate",
        -5: "Sent to External Intermediate",
        -1: "Error",
        1: "In Screener",
        3: "In Client Survey",
        21: "Industry Lockout",
        23: "Standard Qualification",
        24: "Custom Qualification",
        120: "Pre-Client Survey Opt Out",
        122: "Return to Marketplace Opt Out",
        123: "Max Client Survey Entries",
        124: "Max Time in Router",
        125: "Max Time in Router Warning Opt Out",
        126: "Max Answer Limit",
        30: "Quality Term: Unique IP",
        31: "Quality Term: RelevantID Duplicate",
        32: "Quality Term: Invalid Traffic",
        35: "Quality Term: Supplier PID Duplicate",
        36: "Quality Term: Cookie Duplicate",
        37: "Quality Term: GEO IP Mismatch",
        38: "Quality Term: RelevantID** Fraud Profile",
        131: "Quality Term: Supplier Encryption Failure",
        132: "Quality Term: Blocked PID",
        133: "Quality Term: Blocked IP",
        134: "Quality Term: Max Completes per Day Terminate",
        138: "Quality Term: Survey Group Cookie Duplicate",
        139: "Quality Term: Survey Group Supplier PID Duplicate",
        230: "Quality Term: Survey Group Unique IP",
        234: "OFAC Term: Blocked Country IP",
        236: "Privacy Term: No Privacy Consent",
        237: "Privacy Term: Minimum Age",
        238: "Quality Term: Found on Deny List",
        240: "Quality Term: Invalid Browser",
        241: "Quality Term: Respondent Threshold Limit",
        242: "Quality Term: Respondent Quality Score",
        243: "Quality Term: Marketplace Signature Check",
        40: "Overquota: Quota Full",
        41: "Overquota: Supplier Allocation",
        42: "Overquota: Survey Closed for Entry",
        50: "Financial Term: CPI Below Supplier's Rate Card",
        98: "Exit: End of Router",
    }

    """
    The LucidRecruiter base class
    """

    show_termination_button = True

    required_consent_page = LucidConsent.LucidConsentPage
    optional_consent_pages = (
        AudiovisualConsent.AudiovisualConsentPage,
        OpenScienceConsent.OpenScienceConsentPage,
    )

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.config = get_config()
        if self.config.get("show_reward"):
            raise RuntimeError(
                "Lucid recruitment requires `show_reward` to be set to `False`."
            )
        self.mailer = get_mailer(self.config)
        self.notifies_admin = admin_notifier(self.config)
        recruitment_config = json.loads(self.config.get("lucid_recruitment_config"))

        self.lucidservice = get_lucid_service(self.config, recruitment_config)
        self.store = kwargs.get("store", RedisStore())

    def recruit(self, n=1):
        """Incremental recruitment isn't implemented for now, so we return an empty list."""
        return []

    def get_status(self, submissions=None) -> LucidRecruitmentStatus:
        recruitment_config = json.loads(self.config.get("lucid_recruitment_config"))
        survey_number = self.current_survey_number()
        summary = self.lucidservice.get_summary(survey_number)
        cost = summary["cost"]
        total_completes = summary["total_completes"]
        completion_loi = summary["completion_loi"]

        drop_off_rate = 0
        conversion_rate = 0
        incidence_rate = 0
        submission_status_counts = {}

        if submissions is None:
            submissions = self.lucidservice.get_submissions(survey_number)
        if submissions is not None:
            respondents = pd.DataFrame(submissions)
            respondents["status"] = respondents.client_status.apply(
                lambda x: self.client_codes.get(x, "Unknown")
            )

            submission_status_counts = respondents["status"].value_counts().to_dict()
            if len(respondents) > 0:
                respondents["status"] = respondents.client_status.apply(
                    lambda x: self.client_codes.get(x, "Unknown")
                )
                respondents["market_place_code"] = respondents.fulcrum_status.apply(
                    lambda x: self.market_place_codes.get(x, "Unknown")
                )

                MARKETPLACE_CODE = self.MARKETPLACE_CODE  # noqa: F841
                COMPLETED_CODE = self.COMPLETED  # noqa: F841
                IN_SURVEY_CODE = self.IN_SURVEY  # noqa: F841
                after_screener = respondents.query("status != @MARKETPLACE_CODE")
                completes = respondents.query("status == @COMPLETED_CODE")
                in_survey = respondents.query("status == @IN_SURVEY_CODE")
                drop_off_rate = (
                    len(in_survey) / len(after_screener)
                    if len(after_screener) > 0
                    else 0
                )
                conversion_rate = (
                    len(completes) / len(after_screener)
                    if len(after_screener) > 0
                    else 0
                )

                pattern = "Privacy Term|Quality Term|Financial Term|OFAC Term|Custom Qualification|Standard Qualification"
                n_returned_because_of_qualifications = (
                    respondents.market_place_code.str.contains(
                        pattern, regex=True
                    ).sum()
                )

                n_potential_completes = (
                    len(completes) + n_returned_because_of_qualifications
                )
                incidence_rate = float(
                    len(completes) / n_potential_completes
                    if n_potential_completes > 0
                    else 0.0
                )

        cost_per_survey = (cost / total_completes) if total_completes > 0 else 0
        payment_per_hour = completion_loi / 60 * cost_per_survey

        return LucidRecruitmentStatus(
            recruiter_name=self.nickname,
            participant_status_counts=submission_status_counts,
            study_id=self.current_survey_number(),
            study_status=summary["status"],
            study_cost=summary["cost"],
            survey_sid=self.current_survey_sid(),
            survey_number=self.current_survey_number(),
            total_completes=summary["total_completes"],
            total_entrants=summary["total_entrants"],
            total_screens=summary["total_screens"],
            currency=summary["currency"],
            completion_loi=summary["completion_loi"],
            drop_off_rate=drop_off_rate,
            conversion_rate=conversion_rate,
            incidence_rate=incidence_rate,
            cost_per_survey=cost_per_survey,
            payment_per_hour=payment_per_hour,
            earnings_per_click=summary["epc"],
            system_conversion=summary["system_conversion"],
            termination_loi=summary["termination_loi"],
            last_complete_date=summary["last_complete_date"],
            exchange_rate=summary["exchange_rate"],
            config=recruitment_config,
        )

    def notify_duration_exceeded(self, participants, reference_time):
        """
        The participant has been working longer than the time defined in
        the "duration" config value.
        """
        for participant in participants:
            participant.status = "abandoned"
            # We preserve this commit just in case Dallinger removes the external commit in the future
            session.commit()

    def run_checks(self):
        logger.info("Polling Lucid API to count entry_df")

        survey_number = self.current_survey_number()
        submissions = self.lucidservice.get_submissions(survey_number)
        if submissions is None or len(submissions) == 0:
            return
        respondents = pd.DataFrame(submissions)
        status = self.get_status(submissions)

        if len(respondents) > 0:
            respondents["status"] = respondents.client_status.apply(
                lambda x: self.client_codes.get(x, "Unknown")
            )
            respondents["market_place_code"] = respondents.fulcrum_status.apply(
                lambda x: self.market_place_codes.get(x, "Unknown")
            )

            all_entrants = LucidRID.query.all()
            entrants_dict = {entrant.rid: entrant for entrant in all_entrants}

            lucid_entrants = []

            for _, row in respondents.iterrows():
                if row.respondent_id in entrants_dict:
                    entrant = entrants_dict[row.respondent_id]
                    changed = False
                    fields_to_update = {
                        "lucid_status": "status",
                        "lucid_status_code": "client_status",
                        "lucid_fulcrum_status": "fulcrum_status",
                        "lucid_market_place_code": "market_place_code",
                        "lucid_last_date": "last_date",
                    }
                    for field, api_field in fields_to_update.items():
                        if getattr(entrant, field) != row[api_field]:
                            setattr(entrant, field, row[api_field])
                            changed = True
                    if changed:
                        db.session.add(entrant)
                else:
                    entrant = LucidRID(
                        rid=row.respondent_id,
                        lucid_status=row.status,
                        lucid_status_code=row.client_status,
                        lucid_fulcrum_status=row.fulcrum_status,
                        lucid_market_place_code=row.market_place_code,
                        lucid_entry_date=row.entry_date,
                        lucid_last_date=row.last_date,
                        lucid_panelist_id=row.panelist_id,
                        lucid_respondent_id=row.respondent_id,
                        lucid_supplier_id=row.supplier_id,
                    )
                    db.session.add(entrant)
                lucid_entrants.append(entrant)

        logger.info(
            f"Payment per hour: {status.payment_per_hour:.2f} {status.currency}"
        )
        logger.info(f"Drop off rate: {status.drop_off_rate:.2%}")
        logger.info(f"Conversion rate: {status.conversion_rate:.2%}")
        logger.info(f"Incidence rate: {status.incidence_rate:.2%}")
        blocked_fields = [
            "recruiter_name",
            "participant_status_counts",
            "study_id",
            "study_status",
            "study_cost",
            "survey_sid",
            "survey_number",
            "config",
        ]
        status_entry = LucidStatus(
            # From the summary
            status=status.study_status,
            cost=status.study_cost,
            **{
                k: v
                for k, v in status.__dict__.items()
                if not k in blocked_fields  # noqa: E713
            },
        )
        db.session.add(status_entry)
        db.session.commit()

        unfailed_entrants = LucidRID.query.filter_by(
            terminated_at=None, completed_at=None
        ).all()
        logger.info(f"Found {len(unfailed_entrants)} of which are not failed")
        now = datetime.now()

        for entrant in unfailed_entrants:
            if (
                entrant.registered_at
                + timedelta(seconds=self.initial_response_within_s)
                > now
            ):
                # skip entrants that have not been registered long enough
                continue
            if entrant.completed_at is not None:
                # skip completed entrants
                continue
            if entrant.terminated_at is not None:
                # skip terminated entrants
                continue

            details = None
            participant = None
            reason = None
            try:
                participant = Participant.query.filter_by(worker_id=entrant.rid).one()
                responses = (
                    Response.query.filter_by(participant_id=participant.id)
                    .order_by(Response.creation_time)
                    .all()
                )
                if len(responses) == 0:
                    reason = "first-response-timeout"

            except sqlalchemy.orm.exc.NoResultFound:
                # Do not terminate participants who did not pass the qualifications
                if entrant.lucid_status != self.MARKETPLACE_CODE:
                    reason = "never-entered-experiment"

            if reason:
                try:
                    participant_info = (
                        {"participant": participant}
                        if participant
                        else {"assignment_id": entrant.rid}
                    )
                    self.terminate_participant(
                        reason=reason, details=details, **participant_info
                    )

                    logger.info(
                        f"Successfully terminated participant with RID '{entrant.rid}'."
                    )
                except Exception as e:
                    logger.error(
                        f"Error terminating participant with RID '{entrant.rid}': {e}"
                    )

    def get_survey_storage_key(self, name):
        experiment_id = self.config.get("id")
        return f"{self.__class__.__name__}:{experiment_id}:{name}"

    @property
    def in_progress(self):
        """Does a Lucid survey for the current experiment ID already exist?"""
        return self.current_survey_number() is not None

    def check_consents(self, consents):
        super().check_consents(consents)
        error_msg = "Lucid recruitment requires consent 'LucidConsent' and optionally one of `AudiovisualConsent` or `OpenScienceConsent` (in this order)."
        if isinstance(consents[0], self.required_consent_page):
            if len(consents) == 1:
                pass
            elif len(consents) == 2 and isinstance(
                consents[1], self.optional_consent_pages
            ):
                pass
            else:
                raise RuntimeError(error_msg)
        else:
            raise RuntimeError(error_msg)

    def current_survey_number(self):
        """
        Return the survey number associated with the active experiment ID
        if any such survey exists.
        """
        return self.store.get(self.get_survey_storage_key("survey_number"))

    def current_survey_sid(self):
        """
        Return the survey SID associated with the active experiment ID
        if any such survey exists.
        """
        return self.store.get(self.get_survey_storage_key("survey_sid"))

    def open_recruitment(self, n=1):
        """Open a connection to Lucid and create a survey."""
        from .experiment import get_experiment
        from .utils import get_config

        self.lucidservice.log(f"Opening initial recruitment for {n} participants.")
        if self.in_progress:
            raise LucidRecruiterException(
                "Tried to open recruitment on already open recruiter."
            )

        experiment = get_experiment()
        wage_per_hour = get_config().get("wage_per_hour")
        estimated_duration = experiment.estimated_completion_time(wage_per_hour)
        create_survey_request_params = {
            "bid_length_of_interview": ceil(estimated_duration / 60),
            "live_url": self.ad_url.replace("http://", "https://"),
            "name": self.config.get("title"),
            "quota": n,
            "quota_cpi": round(
                experiment.estimated_max_reward(wage_per_hour),
                2,
            ),
        }

        survey_info = self.lucidservice.create_survey(
            self.config.get("publish_experiment"), **create_survey_request_params
        )
        self._record_current_survey_number(survey_info["SurveyNumber"])
        self._record_survey_sid(survey_info["SurveySID"])

        # Lucid Marketplace automatically adds 6 qualifications to US studies
        # when a survey is created (Age, Gender, Zip, Ethnicity, Hispanic, Standard HHI US).
        # We update the qualifications in this case to remove these constraints on the participants.
        # See https://developer.lucidhq.com/#post-create-a-survey
        survey_number = self.current_survey_number()
        if self.lucidservice.recruitment_config["survey"]["CountryLanguageID"] == 9:
            self.lucidservice.remove_default_qualifications_from_survey(survey_number)

        self.lucidservice.add_qualifications_to_survey(survey_number)

        url = survey_info["ClientSurveyLiveURL"]
        self.lucidservice.log(
            f"Done creating Lucid project and survey: {survey_number}."
        )
        self.lucidservice.log(
            f"Lucid reports: https://marketplace.samplicio.us/fulcrum/next/surveys/{survey_number}/reports"
        )
        self.lucidservice.log("---------> " + url)
        self.lucidservice.log("----------")

        survey_id = self.current_survey_number()
        if survey_id is None:
            self.lucidservice.log("No survey in progress: Recruitment aborted.")
            return

        lucid_url = (
            f"https://marketplace.samplicio.us/fulcrum/next/surveys/{survey_id}/quotas"
        )
        message = f"Lucid survey {survey_id} created successfully. " f"URL: {lucid_url}"

        return {
            "items": [url],
            "message": message,
        }

    def close_recruitment(self):
        """
        Lucid automatically ends recruitment when the number of completes has reached the
        target.
        """
        self.lucidservice.log("Recruitment is automatically handled by Lucid.")

    def normalize_entry_information(self, entry_information):
        """Accepts data from the recruited user and returns data needed to validate,
        create or load a Dallinger Participant.

        See :func:`~dallinger.experiment.Experiment.create_participant` for
        details.

        The default implementation extracts ``hit_id``, ``assignment_id``, and
        ``worker_id`` values directly from ``entry_information``.

        This implementation extracts the ``RID`` from ``entry_information``
        and assigns the value to ``hit_id``, ``assignment_id``, and ``worker_id``.
        """

        rid = entry_information.get("RID")
        hit_id = entry_information.get("hit_id")
        if hit_id is None:
            hit_id = entry_information.get("hitId")

        if rid is None and hit_id is None:
            raise LucidRecruiterException(
                "Either `RID` or `hit_id` has to be present in `entry_information`."
            )

        if rid is None:
            rid = hit_id

        # Save RID info into the database
        try:
            LucidRID.query.filter_by(rid=rid).one()
        except NoResultFound:
            self.lucidservice.log(f"Saving RID '{rid}' into the database.")
            db.session.add(LucidRID(rid=rid))
            db.session.commit()
        except MultipleResultsFound:
            raise MultipleResultsFound(
                f"Multiple rows for Lucid RID '{rid}' found. This should never happen."
            )

        participant_data = {
            "hit_id": rid,
            "assignment_id": rid,
            "worker_id": rid,
        }

        if entry_information:
            participant_data["entry_information"] = entry_information

        return participant_data

    def exit_response(self, experiment, participant):
        """
        Delegate to the experiment for possible values to show to the
        participant and complete the survey.
        """
        external_submit_url = self.external_submit_url(participant=participant)
        self.lucidservice.log(f"Exit redirect: {external_submit_url}")

        return render_template_with_translations(
            "exit_recruiter_lucid.html",
            external_submit_url=external_submit_url,
        )

    def reward_bonus(self, participant, amount, reason):
        """
        Set `completed_at` timestamp on participant's LucidRID entry
        """
        if participant is not None and participant.progress == 1:
            self.complete_participant(participant.assignment_id)
        else:
            responses = (
                Response.query.filter_by(participant_id=participant.id)
                .order_by(Response.creation_time)
                .all()
            )
            if responses[-1].answer == {"lucid_consent": False}:
                reason = "consent-rejected"
            else:
                reason = "participant-did-not-complete"
            self.terminate_participant(participant=participant, reason=reason)

    def _record_current_survey_number(self, survey_number):
        self.store.set(self.get_survey_storage_key("survey_number"), survey_number)

    def _record_survey_sid(self, survey_sid):
        self.store.set(self.get_survey_storage_key("survey_sid"), survey_sid)

    def external_submit_url(self, participant=None, assignment_id=None):
        if participant is None and assignment_id is None:
            raise RuntimeError(
                "Error generating 'external_submit_url': One of 'participant' or 'assignment_id' needs to be provided."
            )
        data = self.data_for_submit_url(participant, assignment_id)
        return self.lucidservice.generate_submit_url(ris=data["ris"], rid=data["rid"])

    def data_for_submit_url(self, participant, assignment_id):
        # Standard terminate
        ris = 20
        if participant is not None:
            assignment_id = participant.assignment_id
            if "performance_check" in participant.failure_tags:
                # Security terminate
                ris = 30
            elif participant.progress == 1:
                # Complete
                ris = 10
        if assignment_id is None:
            assignment_id = assignment_id
        return {"rid": assignment_id, "ris": ris}

    def error_page_content(self, assignment_id, external_submit_url):
        _p = get_translator(context=True)

        if external_submit_url is None:
            external_submit_url = self.external_submit_url(assignment_id=assignment_id)

        html = tags.div()
        with html:
            tags.p(
                " ".join(
                    [
                        _p(
                            "lucid_error",
                            "Redirecting to Lucid Marketplace...",
                        ),
                    ]
                )
            )
            tags.script(
                raw(
                    'setTimeout(() => { window.location = "'
                    + external_submit_url
                    + '"; }, 2000)'
                )
            )
        return html

    def time_until_termination_in_s(self, rid):
        return self.lucidservice.time_until_termination_in_s(rid)

    def complete_participant(self, rid):
        return self.lucidservice.complete_respondent(rid)

    def terminate_participant(
        self, participant=None, assignment_id=None, reason=None, details=None
    ):
        assert participant or assignment_id
        assert not (participant and assignment_id)

        if participant:
            assignment_id = participant.assignment_id

            participant.failed = True
            participant.failed_reason = reason
            participant.status = "returned"
            db.session.commit()
        try:
            self.lucidservice.terminate_respondent(assignment_id, reason, details)
            logger.info(
                f"Terminating respondent with RID '{assignment_id}'. Reason: '{reason}'"
            )
        except Exception as e:
            logger.error(
                f"Error terminating respondent with RID '{assignment_id}': {e}"
            )

        return self.external_submit_url(assignment_id=assignment_id)

    def set_termination_details(self, rid, reason):
        self.lucidservice.set_termination_details(rid, reason)

    def get_config_entry(self, key):
        lucid_recruitment_config = json.loads(
            self.config.get("lucid_recruitment_config")
        )

        return lucid_recruitment_config.get(key)

    def get_participant(self, request):
        assignment_id = request.values.get("assignmentId")
        unique_id = request.values.get("unique_id")
        participant_id = request.values.get("participant_id")
        rid = request.values.get("RID")
        participant = None

        if assignment_id is None:
            if unique_id is not None:
                assignment_id = unique_id.split(":")[1]
            elif rid is not None:
                assignment_id = rid
            elif participant_id is not None:
                participant = (
                    Participant.query.with_for_update(of=Participant)
                    .populate_existing()
                    .get(int(participant_id))
                )
                assignment_id = participant.assignment_id

        assert assignment_id is not None, "Could not determine assignment_id."

        if participant is None:
            try:
                participant = Participant.query.filter_by(
                    assignment_id=assignment_id
                ).one()
            except NoResultFound:
                logger.error(
                    f"No LucidRID for Lucid RID '{assignment_id}' found. This should never happen."
                )
            except MultipleResultsFound:
                logger.error(
                    f"Multiple rows for Lucid RID '{assignment_id}' found. This should never happen."
                )

        return participant

    @property
    def termination_time_in_s(self):
        return self.get_config_entry("termination_time_in_s")

    @property
    def inactivity_timeout_in_s(self):
        return self.get_config_entry("inactivity_timeout_in_s")

    @property
    def no_focus_timeout_in_s(self):
        return self.get_config_entry("no_focus_timeout_in_s")

    @property
    def aggressive_no_focus_timeout_in_s(self):
        return self.get_config_entry("aggressive_no_focus_timeout_in_s")

    @property
    def initial_response_within_s(self):
        return self.get_config_entry("initial_response_within_s")

    def change_lucid_status(self, status):
        survey_number = self.current_survey_number()
        service = get_lucid_service()
        service.change_status(survey_number, status)
        LucidStatus.query.order_by(LucidStatus.id.desc()).first().status = status
        db.session.commit()


class DevLucidRecruiter(DevRecruiter, BaseLucidRecruiter):
    """
    Development recruiter for the Lucid Marketplace.
    """

    nickname = "dev-lucid-recruiter"

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.ad_url = (
            f"http://localhost.cap:5000/ad?recruiter={self.nickname}&RID=[%RID%]"
        )

    def get_status(self, submissions=None) -> LucidRecruitmentStatus:
        survey_number = 123456789
        return LucidRecruitmentStatus(
            recruiter_name=self.nickname,
            participant_status_counts={},
            study_id=survey_number,
            study_status="DEV-LUCID",
            study_cost=0,
            survey_sid="DEV-LUCID-SID",
            survey_number=survey_number,
            total_completes=0,
            total_entrants=0,
            total_screens=0,
            currency="€",
            completion_loi=0,
            drop_off_rate=0,
            conversion_rate=0,
            incidence_rate=0,
            cost_per_survey=0,
            payment_per_hour=0,
            earnings_per_click=0,
            system_conversion=0,
            termination_loi=0,
            last_complete_date=datetime.now(),
            exchange_rate=0,
            config={},
        )


class MockLucidRecruiter(MockRecruiter, BaseLucidRecruiter):
    nickname = "mocklucid"

    def __init__(self, *args, **kwargs):
        if len(kwargs) == 0:
            recruitment_config = json.loads(
                get_config().get("lucid_recruitment_config")
            )
        else:
            recruitment_config = kwargs.get("config")
        self.survey_number = recruitment_config.get("survey_number")
        self.survey_sid = recruitment_config.get("survey_sid")

        if len(kwargs) == 0:
            BaseLucidRecruiter.__init__(self, *args, **kwargs)
        else:
            if "id" not in recruitment_config:
                recruitment_config["id"] = f"{self.survey_sid}-{self.survey_number}"
            self.config = {
                "lucid_recruitment_config": json.dumps(recruitment_config),
            }
            config = get_config()

            self.lucidservice = LucidService(
                api_key=config.get("lucid_api_key"),
                sha1_hashing_key=config.get("lucid_sha1_hashing_key"),
                exp_config=config,
                recruitment_config=recruitment_config,
            )
            self.store = RedisStore()

    def register_study(self, **kwargs):
        self._record_current_survey_number(self.survey_number)
        self._record_survey_sid(self.survey_sid)


class LucidRecruiter(BaseLucidRecruiter):
    """
    The production Lucid recruiter.
    Recruit participants from the Lucid Marketplace.
    """

    nickname = "lucid-recruiter"

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.ad_url = f"{get_base_url()}/ad?recruiter={self.nickname}&RID=[%RID%]"


def get_lucid_country_language_id(country_tag, language_tag, service=None):
    assert len(country_tag) == 2, "Country tag must be 2 characters long."
    assert country_tag.isupper(), "Country tag must be uppercase."
    assert len(language_tag) == 3, "Language tag must be 3 characters long."
    assert language_tag.isupper(), "Language tag must be uppercase."

    if service is None:
        service = get_lucid_service()
    lookup = service.get_lucid_country_language_lookup()
    selection = lookup.query(
        "country_tag == @country_tag and language_tag == @language_tag"
    )
    if len(selection) == 0:
        pd.set_option("display.max_rows", None)
        raise ValueError(
            f"Could not find country language ID for {country_tag} and {language_tag}. Pick from these:\n{lookup}"
        )
    return selection.iloc[0]["Id"]


def get_lucid_settings(
    lucid_recruitment_config_path,
    termination_time_in_s: int,
    bid_incidence=66,
    collects_pii=False,
    inactivity_timeout_in_s=120,
    no_focus_timeout_in_s=60,
    aggressive_no_focus_timeout_in_s=3,
    initial_response_within_s=180,
    debug_recruiter=False,
):
    """
    Parameters
    ----------
    lucid_recruitment_config_path: str, path to the Lucid recruitment config.

    termination_time_in_s: int, maximal time a participant can spend on the experiment. If this time is exceeded,
        the participant is terminated via the front-end.

    bid_incidence: int, default 66, the bid incidence. Bid incidence is the number of completes/(number of completes +
        participants who did not pass the qualifications). It is a percentage, so if you expect 66% of the participants
        to pass the qualifications, set it to 66. Set it to a realistic value, but as high as possible.

    collects_pii: bool, default False, whether the survey collects personally identifiable information.

    inactivity_timeout_in_s: int, default 120, the inactivity timeout in seconds. If the participant is inactive for
        this amount of time, the participant is terminated via the front-end. Inactive means that the participant does
        not interact with the page (i.e., no ["click", "keypress", "load", "mousedown", "mousemove", "touchstart"]).

    no_focus_timeout_in_s: int, default 60, the no focus timeout in seconds. If the participant moves the mouse outside
        the window or opens another tab, the participant is terminated via the front-end after this amount of time.

    aggressive_termination_on_no_focus: int, default 3, this the same setting as `no_focus_timeout_in_s`, but it is
        only used for aggressive in the consent page, since many participants are lost there.

    initial_response_within_s: int, default 180 seconds (3 minutes). If the participant does not proceed to the consent
        within this time, the participant is terminated via the backend-end.

    debug_recruiter: bool, default False, whether to use the development recruiter. This is useful for local testing.

    """

    with open(lucid_recruitment_config_path, "r") as f:
        lucid_recruitment_config = json.load(f)

    if termination_time_in_s is not None:
        lucid_recruitment_config["termination_time_in_s"] = termination_time_in_s

    lucid_recruitment_config["survey"]["BidIncidence"] = bid_incidence
    lucid_recruitment_config["survey"]["CollectsPII"] = collects_pii
    lucid_recruitment_config["inactivity_timeout_in_s"] = inactivity_timeout_in_s
    lucid_recruitment_config["no_focus_timeout_in_s"] = no_focus_timeout_in_s
    lucid_recruitment_config["aggressive_no_focus_timeout_in_s"] = (
        aggressive_no_focus_timeout_in_s
    )
    lucid_recruitment_config["initial_response_within_s"] = initial_response_within_s

    lucid_recruitment_config = json.dumps(lucid_recruitment_config)

    settings = {
        "recruiter": "LucidRecruiter",
        "lucid_recruitment_config": lucid_recruitment_config,
        "currency": "EUR",
        "show_reward": False,
        "show_abort_button": False,
    }
    if debug_recruiter:
        settings["debug_recruiter"] = "DevLucidRecruiter"
    return settings


class GenericRecruiter(PsyNetRecruiterMixin, dallinger.recruiters.CLIRecruiter):
    """
    An improved version of Dallinger's Hot-Air Recruiter.
    """

    nickname = "generic"

    def recruit(self, n=1):
        return []

    def exit_response(self, experiment, participant):
        from psynet.timeline import Page

        message = experiment.render_exit_message(participant)

        if message is None:
            raise ValueError(
                "experiment.render_exit_message returned None. Did you forget to use 'return'?"
            )

        elif isinstance(message, Page):
            raise ValueError(
                "Sorry, you can't return a Page from experiment.render_exit_message."
            )

        elif message == "default_exit_message":
            return super().exit_response(experiment, participant)

        elif isinstance(message, str):
            html = dominate.tags.p(message).render()

        elif isinstance(message, dominate.dom_tag.dom_tag):
            html = message.render()

        else:
            raise ValueError(
                f"Invalid value of experiment.render_exit_message: {message}. "
                "You should return either a string or an HTML specification created using dominate tags "
                "(see https://pypi.org/project/dominate/)."
            )

        return flask.render_template("custom_html.html", html=html)

    def open_recruitment(self, n=1):
        res = super().open_recruitment(n=n)

        # Hide the Dallinger logs advice, because the advice doesn't work for SSH deployment
        res["message"] = re.sub(
            "Open the logs for this experiment.*", "", res["message"]
        )
        res["message"] = re.sub(
            ".*in the logs for subsequent recruitment URLs\\.", "", res["message"]
        )

        return res

    def notify_duration_exceeded(self, participants, reference_time):
        """
        The participant has been working longer than the time defined in
        the "duration" config value.
        """
        for participant in participants:
            participant.status = "abandoned"
            # We preserve this commit just in case Dallinger removes the external commit in the future
            session.commit()
