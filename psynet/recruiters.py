import json
import os

import dallinger.recruiters
import flask
import requests
from dallinger.config import get_config
from dallinger.db import session
from dallinger.heroku import tools as heroku_tools
from dallinger.notifications import admin_notifier, get_mailer
from dallinger.recruiters import RedisStore
from dallinger.utils import get_base_url

from .lucid import LucidService
from .utils import get_logger

logger = get_logger()


class BaseCapRecruiter(dallinger.recruiters.CLIRecruiter):

    """
    The CapRecruiter base class
    """

    def open_recruitment(self, n=1):
        """
        Return an empty list which otherwise would be a list of recruitment URLs.
        """
        return {"items": [], "message": ""}

    def recruit(self, n=1):
        return []

    def close_recruitment(self):
        logger.info("No more participants required. Recruitment stopped.")

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

    def reward_bonus(self, assignment_id, amount, reason):
        """
        Return values for `basePay` and `bonus` to cap-recruiter application.
        """
        data = {
            "assignmentId": assignment_id,
            "basePayment": self.config.get("base_payment"),
            "bonus": amount,
        }
        requests.post(
            self.external_submission_url,
            json=data,
            headers={"Authorization": os.environ.get("CAP_RECRUITER_AUTH_TOKEN")},
            verify=False,  # Temporary fix because of SSLCertVerificationError
        )


class CapRecruiter(BaseCapRecruiter):

    """
    The production cap-recruiter.

    """

    nickname = "cap-recruiter"
    external_submission_url = "https://cap-recruiter.ae.mpg.de/hits/complete"


class StagingCapRecruiter(BaseCapRecruiter):

    """
    The staging cap-recruiter.

    """

    nickname = "staging-cap-recruiter"
    external_submission_url = "https://staging-cap-recruiter.ae.mpg.de/hits/complete"


class DevCapRecruiter(BaseCapRecruiter):

    """
    The development cap-recruiter.

    """

    nickname = "dev-cap-recruiter"
    external_submission_url = "http://localhost:8000/hits/complete"


# Lucid


class LucidRecruiterException(Exception):
    """Custom exception for LucidRecruiter"""


class BaseLucidRecruiter(dallinger.recruiters.CLIRecruiter):
    """
    The LucidRecruiter base class
    """

    external_submission_url = (
        "https://www.samplicio.us/router/ClientCallBack.aspx?RIS=10&RID="
    )
    # extra_routes = mturk_routes

    def __init__(self, *args, **kwargs):
        super(BaseLucidRecruiter, self).__init__()
        self.config = get_config()
        # self.ad_url = f"{get_base_url()}/ad?recruiter={self.nickname}&hitId=[%RID%]&assignmentId=[%RID%]&workerId=[%RID%]"
        self.ad_url = f"{get_base_url()}/ad?recruiter={self.nickname}&RID=12345"
        self.notifies_admin = admin_notifier(self.config)
        self.mailer = get_mailer(self.config)
        self.store = kwargs.get("store") or RedisStore()
        self.lucidservice = LucidService(
            api_key=self.config.get("lucid_api_key"),
            sandbox=self.config.get("mode") != "live",
            recruitment_config=json.loads(self.config.get("lucid_recruitment_config")),
        )

    @property
    def survey_update_url(self):
        """
        On experiment completion, participants are returned to
        the Lucid Marketplace site to submit their survey.
        """
        return self.lucidservice.survey_update_url

    @property
    def is_in_progress(self):
        """Does an Lucid survey for the current experiment ID already exist?"""
        return self.current_survey_number() is not None

    @property
    def survey_number_storage_key(self):
        experiment_id = self.config.get("id")
        return "{}:{}".format(self.__class__.__name__, experiment_id)

    @property
    def quota_id_storage_key(self):
        experiment_id = self.config.get("id")
        return "{}:{}:QUOTA".format(self.__class__.__name__, experiment_id)

    def current_survey_number(self):
        """
        Return the ID of the survey associated with the active experiment ID
        if any such survey exists.
        """
        return self.store.get(self.survey_number_storage_key)

    def _record_current_survey_number(self, survey_number):
        self.store.set(self.survey_number_storage_key, survey_number)

    def current_quota_id(self):
        """
        Return the ID of the quota associated with the active experiment ID
        if any such quota exists.
        """
        return self.store.get(self.quota_id_storage_key)

    def _record_current_quota_id(self, quota_id):
        self.store.set(self.quota_id_storage_key, quota_id)

    def open_recruitment(self, n=1):
        """Open a connection to Lucid and create a survey."""
        logger.info(
            f">>>>>>>>>> LUCID RECRUITER: Opening initial recruitment for {n} participants."
        )
        if self.is_in_progress:
            raise LucidRecruiterException(
                "Tried to open_recruitment on already open recruiter."
            )

        create_survey_request_params = {
            "id": heroku_tools.app_name(self.config.get("id")),
            "name": self.config.get("title"),
            "quota": n,
            "live_url": self.ad_url.replace("http", "https"),
        }

        survey_info = self.lucidservice.create_survey(**create_survey_request_params)
        self._record_current_survey_number(survey_info["SurveyNumber"])
        url = survey_info["ClientSurveyLiveURL"]
        logger.info(">>>>>>>>>> LUCID RECRUITER: Done creating project and survey.")

        logger.info(">>>>>>>>>> LUCID RECRUITER: Live URL updated successfully.")
        logger.info("----------")
        logger.info("---------->" + url.replace("https", "http"))
        logger.info("----------")

        survey_id = self.current_survey_number()
        if survey_id is None:
            logger.info(
                ">>>>>>>>>> LUCID RECRUITER: No survey in progress: recruitment aborted."
            )
            return

        return {
            "items": [url],
            "message": "Survey live_url updated.",
        }

    def recruit(self, n=1):
        return []

    def close_recruitment(self):
        logger.info(
            ">>>>>>>>>> LUCID RECRUITER: No more participants required. Recruitment stopped."
        )

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

    def normalize_entry_information(self, entry_information):
        """Accepts data from recruited user and returns data needed to validate,
        create or load a Dallinger Participant.

        See :func:`~dallinger.experiment.Experiment.create_participant` for
        details.

        The default implementation extracts ``hit_id``, ``assignment_id``, and
        ``worker_id`` values directly from the ``entry_information``.

        Returning a dictionary without valid ``hit_id``, ``assignment_id``, or
        ``worker_id`` will generally result in an exception.
        """

        rid = entry_information.get("RID", entry_information.get("rid", None))

        participant_data = {
            "hit_id": rid,
            "assignment_id": rid,
            "worker_id": rid,
        }
        data = {
            "hitId": rid,
            "assignmentId": rid,
            "workerId": rid,
        }

        logger.info("entry_information")
        logger.info(entry_information)
        if entry_information:
            participant_data["entry_information"] = {
                **participant_data,
                **entry_information,
                **data,
            }
        logger.info("participant_data")
        logger.info(participant_data)
        return participant_data

    def exit_response(self, experiment, participant):
        """
        Delegate to the experiment for possible values to show to the
        participant and complete the survey if no more participants are needed.
        """
        response_data = self.lucidservice.complete_survey(self.current_survey_number())
        logger.info(
            f">>>>>>>>>> LUCID RECRUITER: 'Complete survey' request returned: {response_data}\n"
            + f">>>>>>>>>> LUCID RECRUITER: Calling exit route: {self.external_submission_url + participant.assignment_id}"
        )

        complete_redirect_url = (
            self.external_submission_url + participant.assignment_id + "&"
        )
        hash = self.sha1_hash(complete_redirect_url)
        url = f"{complete_redirect_url}hash={hash}"
        logger.info(f"SHA1 -----> URL with HASH: {url}")

        return flask.render_template(
            "exit_recruiter_lucid.html",
            external_submit_url=complete_redirect_url,
        )

    def sha1_hash(self, url):
        import base64
        import hashlib
        import hmac

        key = "secret_key"  # TODO

        encoded_key = key.encode("utf-8")
        encoded_URL = url.encode("utf-8")
        hashed = hmac.new(encoded_key, msg=encoded_URL, digestmod=hashlib.sha1)
        digested_hash = hashed.digest()
        base64_encoded_result = base64.b64encode(digested_hash)
        return (
            base64_encoded_result.decode("utf-8")
            .replace("+", "-")
            .replace("/", "_")
            .replace("=", "")
        )


class DevLucidRecruiter(BaseLucidRecruiter):
    """
    The development Lucid recruiter.
    Recruit sandbox participants from Lucid Marketplace
    """

    nickname = "dev-lucid-recruiter"

    def __init__(self, *args, **kwargs):
        super(DevLucidRecruiter, self).__init__()


class StagingLucidRecruiter(BaseLucidRecruiter):
    """
    The staging Lucid recruiter.
    Recruit sandbox participants from Lucid Marketplace
    """

    nickname = "staging-lucid-recruiter"

    def __init__(self, *args, **kwargs):
        super(StagingLucidRecruiter, self).__init__()


class LucidRecruiter(BaseLucidRecruiter):
    """
    The production Lucid recruiter.
    Recruit participants from Lucid Marketplace
    """

    nickname = "lucid-recruiter"

    def __init__(self, *args, **kwargs):
        super(LucidRecruiter, self).__init__()
