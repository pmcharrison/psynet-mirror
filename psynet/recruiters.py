import json
import os
from math import ceil

import dallinger.recruiters
import dominate
import flask
import requests
from dallinger import db
from dallinger.config import get_config
from dallinger.db import session
from dallinger.notifications import admin_notifier, get_mailer
from dallinger.recruiters import RedisStore
from dallinger.utils import get_base_url
from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from .data import SQLBase, SQLMixin, register_table
from .lucid import LucidService
from .utils import get_logger, pretty_format_seconds

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


# Lucid


@register_table
class LucidRID(SQLBase, SQLMixin):
    __tablename__ = "lucid_rid"

    # These fields are removed from the database table as they are not needed.
    failed = None
    failed_reason = None
    time_of_death = None

    rid = Column(String, index=True)
    terminated_at = Column(DateTime, index=True)
    termination_requested_at = Column(DateTime)


class LucidRecruiterException(Exception):
    """Custom exception for LucidRecruiter"""


class BaseLucidRecruiter(PsyNetRecruiter):
    """
    The LucidRecruiter base class


    Attributes
    ----------
    start_experiment_in_popup_window : bool
        Whether to start the experiment in a popup-window or not, Default: True
    """

    start_experiment_in_popup_window = True

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.config = get_config()
        self.mailer = get_mailer(self.config)
        self.notifies_admin = admin_notifier(self.config)
        self.lucidservice = LucidService(
            api_key=self.config.get("lucid_api_key"),
            sha1_hashing_key=self.config.get("lucid_sha1_hashing_key"),
            sandbox=self.config.get("mode") != "live",
            recruitment_config=json.loads(self.config.get("lucid_recruitment_config")),
        )
        self.store = kwargs.get("store") or RedisStore()

    @property
    def survey_number_storage_key(self):
        experiment_id = self.config.get("id")
        return "{}:{}".format(self.__class__.__name__, experiment_id)

    @property
    def in_progress(self):
        """Does a Lucid survey for the current experiment ID already exist?"""
        return self.current_survey_number() is not None

    def current_survey_number(self):
        """
        Return the survey number associated with the active experiment ID
        if any such survey exists.
        """
        return self.store.get(self.survey_number_storage_key)

    def open_recruitment(self, n=1):
        """Open a connection to Lucid and create a survey."""
        self.lucidservice.log(f"Opening initial recruitment for {n} participants.")
        if self.in_progress:
            raise LucidRecruiterException(
                "Tried to open_recruitment on already open recruiter."
            )

        experiment = dallinger.experiment.load().new(db.session)
        create_survey_request_params = {
            "bid_length_of_interview": ceil(
                experiment.estimated_completion_time(experiment.var.wage_per_hour) / 60
            ),
            "live_url": self.ad_url.replace("http://", "https://"),
            "name": self.config.get("title"),
            "quota": n,
            "quota_cpi": round(
                experiment.estimated_max_bonus(experiment.var.wage_per_hour),
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
        self.lucidservice.log("Done creating project and survey.")
        self.lucidservice.log("----------")
        self.lucidservice.log("---------> " + url.replace("https", "http"))
        self.lucidservice.log("----------")

        survey_id = self.current_survey_number()
        if survey_id is None:
            self.lucidservice.log("No survey in progress: recruitment aborted.")
            return

        return {
            "items": [url],
            "message": "Lucid survey created successfully.",
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
        participant and complete the survey if no more participants are needed.
        """
        if participant.failed:
            redirect_url = "https://samplicio.us/s/ClientCallBack.aspx?RIS=20&RID="
        else:
            redirect_url = (
                "https://www.samplicio.us/router/ClientCallBack.aspx?RIS=10&RID="
            )

        redirect_url += participant.assignment_id + "&"
        hash = self.lucidservice.sha1_hash(redirect_url)
        redirect_url += f"hash={hash}"
        self.lucidservice.log(f"Exit redirect: {redirect_url}")

        return flask.render_template(
            "exit_recruiter_lucid.html",
            external_submit_url=redirect_url,
        )

    def _record_current_survey_number(self, survey_number):
        self.store.set(self.survey_number_storage_key, survey_number)

    def run_checks(self):
        LucidService(
            api_key=self.config.get("lucid_api_key"),
            sha1_hashing_key=self.config.get("lucid_sha1_hashing_key"),
            sandbox=self.config.get("mode") != "live",
            recruitment_config=json.loads(self.config.get("lucid_recruitment_config")),
        ).terminate_invalid_respondents()

    @property
    def termination_time_in_min(self):
        lucid_recruitment_config = json.loads(
            self.config.get("lucid_recruitment_config")
        )
        return pretty_format_seconds(
            lucid_recruitment_config.get("termination_time_in_s")
        )


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
