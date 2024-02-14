import json
import os
import random
import re
import time
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
from dallinger.recruiters import RedisStore
from dallinger.utils import get_base_url
from dominate import tags
from dominate.util import raw
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.sql import func

from .consent import AudiovisualConsent, LucidConsent, OpenScienceConsent
from .data import SQLBase, SQLMixin, register_table
from .lucid import LucidService
from .participant import Participant
from .timeline import Response
from .utils import get_logger, render_template_with_translations

logger = get_logger()


class PsyNetRecruiter(dallinger.recruiters.CLIRecruiter):
    """
    The PsyNetRecruiter base class
    """

    def compensate_worker(self, *args, **kwargs):
        """A recruiter may provide a means to directly compensate a worker."""
        raise RuntimeError("Compensation is not implemented.")

    def notify_duration_exceeded(self, participants, reference_time):
        """
        The participant has been working longer than the time defined in
        the "duration" config value.
        """
        for participant in participants:
            participant.status = "abandoned"
            session.commit()

    def recruit(self, n=1):
        """Incremental recruitment isn't implemented for now, so we return an empty list."""
        return []


# CAP Recruiter
class BaseCapRecruiter(PsyNetRecruiter):
    """
    The CapRecruiter base class
    """

    def open_recruitment(self, n=1):
        """
        Return an empty list which otherwise would be a list of recruitment URLs.
        """
        return {"items": [], "message": ""}

    def close_recruitment(self):
        logger.info("No more participants required. Recruitment stopped.")

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


class DevCapRecruiter(BaseCapRecruiter):
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
            "lucid_entry_date": self.lucid_entry_date,
            "lucid_fulcrum_status": self.lucid_fulcrum_status,
            "lucid_last_date": self.lucid_last_date,
            "lucid_panelist_id": self.lucid_panelist_id,
            "lucid_respondent_id": self.lucid_respondent_id,
            "lucid_supplier_id": self.lucid_supplier_id,
        }


class LucidRecruiterException(Exception):
    """Custom exception for LucidRecruiter"""


class BaseLucidRecruiter(PsyNetRecruiter):
    PRESCREENED = "Marketplace codes"
    COMPLETED = "Returned as Complete"
    TERMINATED = "Returned as Terminate"
    UNRETURNED = "Currently in Client Survey or Drop"
    client_codes = {
        1: UNRETURNED,
        20: TERMINATED,
        10: COMPLETED,
        -1: PRESCREENED,
    }

    marketplace_codes = {
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
        50: "Financial Term: CPI Below Supplier’s Rate Card",
        98: "Exit: End of Router",
    }

    """
    The LucidRecruiter base class
    """

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
        self.lucidservice = LucidService(
            api_key=self.config.get("lucid_api_key"),
            sha1_hashing_key=self.config.get("lucid_sha1_hashing_key"),
            exp_config=self.config,
            recruitment_config=json.loads(self.config.get("lucid_recruitment_config")),
        )
        self.store = kwargs.get("store", RedisStore())

    @classmethod
    def get_recruiter_metrics(cls, respondents):
        PRESCREENED_CODE = cls.PRESCREENED  # noqa: F841
        COMPLETED_CODE = cls.COMPLETED  # noqa: F841
        UNRETURNED_CODE = cls.UNRETURNED  # noqa: F841
        prescreens = respondents.query("status != @PRESCREENED_CODE")
        completes = respondents.query("status == @COMPLETED_CODE")
        drop_off = respondents.query("status == @UNRETURNED_CODE")
        drop_off_rate = len(drop_off) / len(prescreens)
        conversion_rate = len(completes) / len(prescreens)

        pattern = (
            "Privacy Term|Quality Term|Financial Term|OFAC Term|Custom Qualification"
        )
        returned_because_of_qualifications = respondents.market_place_code.str.contains(
            pattern, regex=True
        ).sum()

        incidence_rate = len(completes) / (
            len(completes) + returned_because_of_qualifications
        )
        return {
            "drop_off_rate": drop_off_rate,
            "conversion_rate": conversion_rate,
            "incidence_rate": incidence_rate,
            "n_entrants": len(respondents),
            "n_prescreens": len(prescreens),
            "n_completes": len(completes),
        }

    def run_checks(self):
        logger.info("Polling Lucid API to count respondents")
        survey_number = self.current_survey_number()
        respondents = pd.DataFrame(self.lucidservice.get_respondents(survey_number))

        respondents["status"] = respondents.client_status.apply(
            lambda x: self.client_codes.get(x, "Unknown")
        )
        respondents["market_place_code"] = respondents.fulcrum_status.apply(
            lambda x: self.marketplace_codes.get(x, "Unknown")
        )

        all_entrants = LucidRID.query.all()
        entrants_dict = {entrant.rid: entrant for entrant in all_entrants}

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
        db.session.commit()

        metrics = self.get_recruiter_metrics(respondents)
        logger.info(
            f"Found {metrics['n_entrants']} entrants, {metrics['n_prescreens']} prescreens, {metrics['n_completes']} completes"
        )

        logger.info(f"Drop off rate: {metrics['drop_off_rate']:.2%}")
        logger.info(f"Conversion rate: {metrics['conversion_rate']:.2%}")

        unfailed_entrants = LucidRID.query.filter_by(
            terminated_at=None, completed_at=None
        ).all()
        logger.info(f"Found {len(unfailed_entrants)} of which are not failed")
        now = datetime.now()

        for entrant in unfailed_entrants:
            if (
                entrant.registered_at
                + timedelta(minutes=self.initial_response_within_s)
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

            reason = None
            details = None
            try:
                participant = Participant.query.filter_by(worker_id=entrant.rid).one()
                responses = (
                    Response.query.filter_by(participant_id=participant.id)
                    .sort_by(Response.creation_time)
                    .all()
                )
                if len(responses) == 0:
                    reason = f"Did not receive first response within {self.initial_response_within_s // 60} minutes"
                    details = f"Participant {participant.id} did not accept the consent"
                # else:
                #     last_response = responses[-1]
                #     if now > last_response.creation_time + timedelta(
                #         minutes=self.max_response_time_in_s
                #     ):
                #         reason = (
                #             f"No response {self.max_response_time_in_s//60} minutes"
                #         )
                #         details = f"Participant {participant.id} had {len(responses)} responses"

            except sqlalchemy.orm.exc.NoResultFound:
                reason = "Never entered the experiment"

            if reason:
                self.terminate_participant(entrant.rid, reason, details)
                logger.info(f"RID {entrant.rid} terminated")
                # sleep to avoid hitting the Lucid API rate limit, min 1 second, max 30 seconds
                wait = random.randint(1, 15)
                logger.info(f"Wait for {wait} seconds")
                time.sleep(wait)

    @property
    def survey_number_storage_key(self):
        experiment_id = self.config.get("id")
        return "{}:{}".format(self.__class__.__name__, experiment_id)

    @property
    def in_progress(self):
        """Does a Lucid survey for the current experiment ID already exist?"""
        return self.current_survey_number() is not None

    def verify_consents(self, consents):
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
        return self.store.get(self.survey_number_storage_key)

    def open_recruitment(self, n=1):
        """Open a connection to Lucid and create a survey."""
        from .experiment import get_and_load_config, get_experiment

        self.lucidservice.log(f"Opening initial recruitment for {n} participants.")
        if self.in_progress:
            raise LucidRecruiterException(
                "Tried to open_recruitment on already open recruiter."
            )

        experiment = get_experiment()
        wage_per_hour = get_and_load_config().get("wage_per_hour")
        create_survey_request_params = {
            "bid_length_of_interview": ceil(
                experiment.estimated_completion_time(wage_per_hour) / 60
            ),
            "live_url": self.ad_url.replace("http://", "https://"),
            "name": self.config.get("title"),
            "quota": n,
            "quota_cpi": round(
                experiment.estimated_max_reward(wage_per_hour),
                2,
            ),
        }

        survey_info = self.lucidservice.create_survey(**create_survey_request_params)
        self._record_current_survey_number(survey_info["SurveyNumber"])

        # Lucid Marketplace automatically adds 6 qualifications to US studies
        # when a survey is created (Age, Gender, Zip, Ethnicity, Hispanic, Standard HHI US).
        # We update the qualifications in this case to remove these constraints on the participants.
        # See https://developer.lucidhq.com/#post-create-a-survey
        if self.lucidservice.recruitment_config["survey"]["CountryLanguageID"] == 9:
            self.lucidservice.remove_default_qualifications_from_survey(
                self.current_survey_number()
            )

        self.lucidservice.add_qualifications_to_survey(self.current_survey_number())

        url = survey_info["ClientSurveyLiveURL"]
        self.lucidservice.log("Done creating Lucid project and survey.")
        self.lucidservice.log("----------")
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
            self.terminate_participant(
                participant.assignment_id,
                "Termination in 'reward_bonus' as 'participant.progress' was < 1",
            )

    def _record_current_survey_number(self, survey_number):
        self.store.set(self.survey_number_storage_key, survey_number)

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
        return {"ris": ris, "rid": assignment_id}

    def error_page_content(self, _, _p, assignment_id, external_submit_url):
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

    def terminate_participant(self, rid, reason, details=None):
        return self.lucidservice.terminate_respondent(rid, reason, details)

    def set_termination_details(self, rid, reason):
        self.lucidservice.set_termination_details(rid, reason)

    def get_config_entry(self, key):
        lucid_recruitment_config = json.loads(
            self.config.get("lucid_recruitment_config")
        )

        return lucid_recruitment_config.get(key)

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

    @property
    def max_response_time_in_s(self):
        return self.get_config_entry("max_response_time_in_s")


class DevLucidRecruiter(BaseLucidRecruiter):
    """
    Development recruiter for the Lucid Marketplace.
    """

    nickname = "dev-lucid-recruiter"

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.ad_url = (
            f"http://localhost.cap:5000/ad?recruiter={self.nickname}&RID=[%RID%]"
        )


class LucidRecruiter(BaseLucidRecruiter):
    """
    The production Lucid recruiter.
    Recruit participants from the Lucid Marketplace.
    """

    nickname = "lucid-recruiter"

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.ad_url = f"{get_base_url()}/ad?recruiter={self.nickname}&RID=[%RID%]"


class GenericRecruiter(PsyNetRecruiter):
    """
    An improved version of Dallinger's Hot-Air Recruiter.
    """

    nickname = "generic"

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
