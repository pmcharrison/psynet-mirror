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
from .log import bold, red
from .lucid import get_lucid_service
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
            "lucid_fulcrum_status": self.lucid_fulcrum_status,
            "lucid_market_place_code": self.lucid_market_place_code,
            "lucid_entry_date": self.lucid_entry_date,
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
        recruitment_config = json.loads(self.config.get("lucid_recruitment_config"))

        self.lucidservice = get_lucid_service(self.config, recruitment_config)
        self.store = kwargs.get("store", RedisStore())

    @classmethod
    def get_recruiter_metrics(cls, entry_df):
        PRESCREENED_CODE = cls.PRESCREENED  # noqa: F841
        COMPLETED_CODE = cls.COMPLETED  # noqa: F841
        UNRETURNED_CODE = cls.UNRETURNED  # noqa: F841
        prescreens = entry_df.query("lucid_status != @PRESCREENED_CODE")
        completes = entry_df.query("lucid_status == @COMPLETED_CODE")
        drop_off = entry_df.query("lucid_status == @UNRETURNED_CODE")
        drop_off_rate = len(drop_off) / len(prescreens) if len(prescreens) > 0 else None
        conversion_rate = (
            len(completes) / len(prescreens) if len(prescreens) > 0 else None
        )

        pattern = (
            "Privacy Term|Quality Term|Financial Term|OFAC Term|Custom Qualification"
        )
        returned_because_of_qualifications = (
            entry_df.lucid_market_place_code.str.contains(pattern, regex=True).sum()
        )

        potential = len(completes) + returned_because_of_qualifications
        incidence_rate = len(completes) / potential if potential > 0 else None
        return {
            "drop_off_rate": drop_off_rate,
            "conversion_rate": conversion_rate,
            "incidence_rate": incidence_rate,
            "n_entrants": len(entry_df),
            "n_prescreens": len(prescreens),
            "n_completes": len(completes),
        }

    def run_checks(self):
        logger.info("Polling Lucid API to count entry_df")
        survey_number = self.current_survey_number()
        respondents = pd.DataFrame(self.lucidservice.get_respondents(survey_number))
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
            db.session.commit()

            entry_df = pd.DataFrame([entrant.to_dict() for entrant in lucid_entrants])
            metrics = self.get_recruiter_metrics(entry_df)
            logger.info(
                f"Found {metrics['n_entrants']} entrants, {metrics['n_prescreens']} prescreens, {metrics['n_completes']} completes"
            )

            logger.info(f"Drop off rate: {metrics['drop_off_rate']:.2%}")
            logger.info(f"Conversion rate: {metrics['conversion_rate']:.2%}")
            logger.info(f"Incidence rate: {metrics['incidence_rate']:.2%}")

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
                    .order_by(Response.creation_time)
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

        survey_info = self.lucidservice.create_survey(**create_survey_request_params)
        self._record_current_survey_number(survey_info["SurveyNumber"])

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
                reason = "Consent rejected"
            else:
                reason = (
                    "Termination in 'reward_bonus' as 'participant.progress' was < 1"
                )
            self.terminate_participant(participant.assignment_id, reason)

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

    # @property
    # def max_response_time_in_s(self):
    #     return self.get_config_entry("max_response_time_in_s")


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


CUSTOM_QUALIFICATIONS_LUCID = {
    "COUNTRY_OF_BIRTH": 190400,
    "NATIONALITY": 190399,
    "TIMEOUT": 191148,
    "MONOLINGUALISM": 190398,
    "FIRST_LANGUAGE": 190401,
    "HEADPHONE": 199614,
    "MICROPHONE": 199615,
}


def create_lucid_recruitment_config(
    language_tag,
    country_tag,
    question_answer_dict,
    use_headphones: bool,
    use_microphone: bool,
    config_path=None,
    allow_mobile_devices: bool = None,
    force_google_chrome: bool = None,
    unique_ip: bool = True,
    unique_pid: bool = True,
    industry_id: int = 30,
    study_type_id: int = 1,
    debug: bool = True,
):
    """
    Create a Lucid recruitment config.
    Parameters
    ----------
    language_tag: str, 3-letter lanugage name, NOT an ISO language tag, if you specify a wrong language tag, the Lucid
    API will tell you which ones are available.
    country_tag: str, 2-letter country code, NOT an ISO country code, if you specify a wrong country tag, the Lucid API
    will tell you which ones are available.
    question_answer_dict: dict, a dictionary with question names as keys and a list of allowed answers as values. The
    question names must occur in CUSTOM_QUALIFICATIONS_LUCID.
    use_headphones: bool, whether the participant must use headphones
    use_microphone: bool, whether the participant must use a microphone
    config_path: str, default None, if None, it will return the config as a dictionary, if a path is specified, it will
    allow_mobile_devices: bool, default None, if None, it will be taken from the config file
    force_google_chrome: bool, default None, if None, it will be taken from the config file
    unique_ip: bool, default True, whether the participant must have a unique IP
    unique_pid: bool, default True, whether the participant must have a unique PID
    industry_id: int, default 30, which is the default for "Other", pick from:
    {
     '1': 'Automotive',
     '2': 'Beauty/Cosmetics',
     '3': 'Beverages - Alcoholic',
     '4': 'Beverages - Non Alcoholic',
     '5': 'Education',
     '6': 'Electronics/Computer/Software',
     '7': 'Entertainment (Movies, Music, TV, etc)',
     '8': 'Fashion/Clothing',
     '9': 'Financial Services/Insurance',
     '10': 'Food/Snacks',
     '11': 'Gambling/Lottery',
     '12': 'Healthcare/Pharmaceuticals',
     '13': 'Home (Utilities, Appliances, ...)',
     '14': 'Home Entertainment (DVD, VHS)',
     '15': 'Home Improvement/Real Estate/Construction',
     '16': 'IT (Servers, Databases, etc)',
     '17': 'Personal Care/Toiletries',
     '18': 'Pets',
     '19': 'Politics',
     '20': 'Publishing (Newspaper, Magazines, Books)',
     '21': 'Restaurants',
     '22': 'Sports',
     '23': 'Telecommunications (phone, cell phone, cable)',
     '24': 'Tobacco (Smokers)',
     '25': 'Toys',
     '26': 'Transportation/Shipping',
     '27': 'Travel',
     '28': 'Video Games',
     '29': 'Websites/Internet/E-Commerce',
     '30': 'Other',
     '31': 'Sensitive Content',
     '32': 'Explicit Content'
    }
    study_type_id: int, default 1, which is the default for "Adhoc", pick from:
    {
     '1': 'Adhoc',
     '2': 'Diary',
     '5': 'IHUT',
     '8': 'Community Build',
     '9': 'Face to Face',
     '11': 'Recruit - Panel',
     '13': 'Tracking - Monthly',
     '14': 'Tracking - Quarterly',
     '15': 'Tracking - Weekly',
     '16': 'Wave Study',
     '17': 'Qualitative Screening',
     '18': 'Internal Use',
     '21': 'Incidence Check',
     '22': 'Recontact',
     '23': 'Ad Effectiveness Research',
     '24': 'Proof Exposed',
     '25': 'Proof Control'
     }
    debug: bool, default True, whether to print debug information, i.e. see the translations of the qualifications

    Returns
    -------

    """
    from .experiment import get_and_load_config

    logger = get_logger()
    config = get_and_load_config()
    service = get_lucid_service(config=config)
    country_language_id = get_lucid_country_language_id(
        country_tag, language_tag, service=service
    )

    qualifications = []

    if allow_mobile_devices is None:
        allow_mobile_devices = config.get("allow_mobile_devices")

    if allow_mobile_devices:
        qualifications.append(
            {
                "Name": "MS_is_mobile",
                "QuestionID": 8214,
                "LogicalOperator": "NOT",
                "NumberOfRequiredConditions": 0,
                "IsActive": True,
                "Order": 1,
                "PreCodes": ["true"],
            }
        )
        qualifications.append(
            {
                "Name": "MS_is_tablet",
                "QuestionID": 8213,
                "LogicalOperator": "NOT",
                "NumberOfRequiredConditions": 0,
                "IsActive": True,
                "Order": 1,
                "PreCodes": ["true"],
            }
        )

    if force_google_chrome is None:
        force_google_chrome = config.get("force_google_chrome")

    if force_google_chrome:
        qualifications.append(
            {
                "Name": "MS_browser_type_Non_Wurfl",
                "QuestionID": 1035,
                "LogicalOperator": "OR",
                "NumberOfRequiredConditions": 0,
                "IsActive": True,
                "Order": 2,
                "PreCodes": ["Chrome"],
            }
        )

    question_answer_dict["TIMEOUT"] = ["Agree"]
    if use_headphones:
        question_answer_dict["HEADPHONE"] = ["Yes, I can play audio"]
    if use_microphone:
        question_answer_dict["MICROPHONE"] = ["Yes, I can record audio"]

    for question_name, options in question_answer_dict.items():
        if question_name not in CUSTOM_QUALIFICATIONS_LUCID:
            raise ValueError(f"Unknown question {question_name}.")
        question_id = CUSTOM_QUALIFICATIONS_LUCID[question_name]
        english_option_df = service.get_answer_options(question_id)
        option_df = english_option_df.query("text in @options")
        assert (
            len(option_df) > 0
        ), f"Question {question_name} does not have specified options: {options}. Make sure to pick from: {english_option_df.text.tolist()}."
        precodes = option_df.precode.tolist()
        qualifications.append(
            {
                "Name": question_name,
                "QuestionID": question_id,
                "LogicalOperator": "OR",
                "NumberOfRequiredConditions": len(options),
                "IsActive": True,
                "PreCodes": precodes,
            }
        )

        foreign_locale = f"{language_tag}_{country_tag}"
        try:
            foreign_option_df = service.get_answer_options(question_id, foreign_locale)
        except AssertionError:
            raise AssertionError(
                bold(
                    red(f"Could not find question {question_name} in {foreign_locale}.")
                )
                + " "
                + "Make sure it exists: https://www.samplicio.us/fulcrum/Questions.aspx"
            )

        foreign_selected_option_df = foreign_option_df.query("precode in @precodes")
        english_selected_option_df = english_option_df.query("precode in @precodes")
        assert len(foreign_selected_option_df) == len(
            english_selected_option_df
        ), f"Foreign options for question {question_name} do not match English options. English: {english_selected_option_df.text.tolist()} -> Foreign: {foreign_selected_option_df.text.tolist()}"
        foreign_question = service.get_question_name(question_id, foreign_locale)

        english_question = service.get_question_name(question_id)
        if debug:
            logger.info(
                bold(
                    f"Question {question_name} ({question_id}): {service.default_locale.upper()} -> {foreign_locale.upper()}"
                )
            )
            print(
                bold("English")
                + f": '{english_question}' => {english_selected_option_df.text.tolist()}"
            )
            print(
                bold("Foreign")
                + f": '{foreign_question}' => {foreign_selected_option_df.text.tolist()}"
            )
    lucid_recruitment_config = {
        "survey": {
            "CountryLanguageID": country_language_id,
            # Following API documentation: To ensure Suppliers have access to the Survey when it is set live,
            # set the following parameters:
            # FulcrumExchangeAllocation: 0
            # FulcrumExchangeHedgeAccess: true
            "FulcrumExchangeAllocation": 0,
            "FulcrumExchangeHedgeAccess": True,
            "IndustryID": industry_id,
            "StudyTypeID": study_type_id,
            "UniqueIPAddress": unique_ip,
            "UniquePID": unique_pid,
        },
        "qualifications": qualifications,
        "country": country_tag,
        "language": language_tag,
    }
    if config_path is not None:
        with open(config_path, "w") as f:
            json.dump(lucid_recruitment_config, f, indent=4)
    else:
        return lucid_recruitment_config


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
    lucid_recruitment_config[
        "aggressive_no_focus_timeout_in_s"
    ] = aggressive_no_focus_timeout_in_s
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
