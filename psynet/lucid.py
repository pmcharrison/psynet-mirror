import json
from datetime import datetime

import requests
from dallinger.db import session
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from psynet.participant import Participant

from . import deployment_info
from .utils import get_logger

logger = get_logger()


class LucidServiceException(Exception):
    """Custom exception type"""


class LucidService(object):
    """Facade for Lucid Marketplace services provided via its HTTP API."""

    def __init__(
        self,
        api_key,
        sha1_hashing_key,
        exp_config,
        recruitment_config,
        max_wait_secs=0,
    ):
        self.api_key = api_key
        self.sha1_hashing_key = sha1_hashing_key
        self.exp_config = exp_config
        self.recruitment_config = recruitment_config
        self.max_wait_secs = max_wait_secs
        self.headers = {
            "Content-type": "application/json",
            "Authorization": api_key,
            "Accept": "text/plain",
        }

    @property
    def request_base_url_v1(self):
        return "https://api.samplicio.us/Demand/v1"

    @classmethod
    def log(cls, text):
        logger.info(f"LUCID RECRUITER: {text}")

    def create_survey(
        self,
        bid_length_of_interview,
        live_url,
        name,
        quota,
        quota_cpi,
    ):
        """
        Create a survey and return a dict with its properties.
        """
        params = {
            "BidLengthOfInterview": bid_length_of_interview,
            "ClientSurveyLiveURL": live_url,
            "Quota": quota,
            "QuotaCPI": quota_cpi,
            "SurveyName": name,
            "TestRedirectURL": live_url,
        }

        # Apply survey configuration from 'lucid_recruitment_config.json' file.
        survey_data = self.recruitment_config["survey"]
        survey_status_code = "01"
        if (
            self.exp_config.activate_recruiter_on_start
            and deployment_info.read("mode") == "live"
        ):
            survey_status_code = "03"
        survey_data["SurveyStatusCode"] = survey_status_code

        request_data = json.dumps({**params, **survey_data})
        response = requests.post(
            f"{self.request_base_url_v1}/Surveys/Create",
            data=request_data,
            headers=self.headers,
        )
        response_data = response.json()

        if (
            "SurveySID" not in response_data["Survey"]
            or "SurveyNumber" not in response_data["Survey"]
        ):
            raise LucidServiceException(
                "LUCID: SurveySID/SurveyNumber was missing in response data from request to create survey."
            )
        self.log(
            f'Survey with number {response_data["Survey"]["SurveyNumber"]} created successfully.'
        )

        return response_data["Survey"]

    def remove_default_qualifications_from_survey(self, survey_number):
        """Remove default qualifications from a survey."""
        qualifications = [
            {
                "Name": "ZIP",
                "QuestionID": 45,
                "LogicalOperator": "OR",
                "NumberOfRequiredConditions": 0,
                "IsActive": False,
                "Order": 2,
                "PreCodes": [],
            },
            {
                "Name": "STANDARD_HHI_US",
                "QuestionID": 14785,
                "LogicalOperator": "OR",
                "NumberOfRequiredConditions": 0,
                "IsActive": False,
                "Order": 6,
                "PreCodes": [],
            },
            {
                "Name": "ETHNICITY",
                "QuestionID": 113,
                "LogicalOperator": "OR",
                "NumberOfRequiredConditions": 0,
                "IsActive": False,
                "Order": 5,
                "PreCodes": [],
            },
            {
                "Name": "GENDER",
                "QuestionID": 43,
                "LogicalOperator": "OR",
                "NumberOfRequiredConditions": 0,
                "IsActive": False,
                "Order": 3,
                "PreCodes": [],
            },
            {
                "Name": "HISPANIC",
                "QuestionID": 47,
                "LogicalOperator": "OR",
                "NumberOfRequiredConditions": 0,
                "IsActive": False,
                "Order": 4,
                "PreCodes": [],
            },
        ]

        for qualification in qualifications:
            request_data = json.dumps(qualification)
            response = requests.put(
                f"{self.request_base_url_v1}/SurveyQualifications/Update/{survey_number}",
                data=request_data,
                headers=self.headers,
            )

            if not response.ok:
                raise LucidServiceException(
                    "LUCID: Error removing default qualifications. Status returned: {response.status_code}, reason: {response.reason}"
                )

        self.log("Removed default qualifications from survey.")

    def add_qualifications_to_survey(self, survey_number):
        """Add platform and browser specific qualifications to a survey."""
        qualifications = []

        if not self.exp_config.allow_mobile_devices:
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

        if self.exp_config.force_google_chrome:
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

        if self.recruitment_config["qualifications"].get("headphones"):
            qualifications.append(
                {
                    "Name": "headphones",
                    "QuestionID": 149326,
                    "LogicalOperator": "OR",
                    "NumberOfRequiredConditions": 1,
                    "IsActive": True,
                    "Order": 3,
                    "PreCodes": ["1"],
                }
            )

        for qualification in qualifications:
            request_data = json.dumps(qualification)
            response = requests.post(
                f"{self.request_base_url_v1}/SurveyQualifications/Create/{survey_number}",
                data=request_data,
                headers=self.headers,
            )

            if not response.ok:
                raise LucidServiceException(
                    "LUCID: Error adding qualifications. Status returned: {response.status_code}, reason: {response.reason}"
                )

        if qualifications:
            self.log("Added qualifications to survey.")

    def can_be_terminated(self, lucid_rid):
        if (
            datetime.now() - lucid_rid.creation_time
        ).seconds <= self.recruitment_config["termination_time_in_s"]:
            return False

        n = Participant.query.filter_by(worker_id=lucid_rid.rid, progress=0).count()

        return n > 0

    def time_until_termination_in_s(self, rid):
        lucid_rid = get_lucid_rid(rid)

        if lucid_rid.terminated_at is not None:
            return 0

        termination_time_in_s = self.recruitment_config["termination_time_in_s"]

        if self.can_be_terminated(lucid_rid):
            return 0
        else:
            time_until_termination_in_s = (
                termination_time_in_s
                - (datetime.now() - lucid_rid.creation_time).seconds
            )
            return time_until_termination_in_s

    def send_complete_request(self, rid):
        return self.send_exit_request(rid, 10)

    def send_terminate_request(self, rid):
        return self.send_exit_request(rid, 20)

    def generate_submit_url(self, ris=None, rid=None):
        if ris is None or rid is None:
            raise RuntimeError(
                "Error generating 'submit_url': Both 'ris' and 'rid' need to be provided!"
            )
        submit_url = "https://samplicio.us/s/ClientCallBack.aspx"
        submit_url += f"?RIS={ris}"
        submit_url += f"&RID={rid}&"
        submit_url += f"hash={self.sha1_hash(submit_url)}"
        return submit_url

    def send_exit_request(self, rid, ris):
        redirect_url = self.generate_submit_url(ris=ris, rid=rid)
        self.log(
            f"Sending exit request for respondent with RID '{rid}' using redirect URL '{redirect_url}'."
        )
        return requests.get(redirect_url)

    def complete_respondent(self, rid):
        lucid_rid = get_lucid_rid(rid)

        if lucid_rid.completed_at is None and lucid_rid.terminated_at is None:
            response = self.send_complete_request(rid)
            if response.ok:
                lucid_rid.completed_at = datetime.now()
                session.commit()
                self.log("Respondent completed successfully.")
            else:
                self.log(
                    f"Error completing respondent. Status returned: {response.status_code}, reason: {response.reason}"
                )
        else:
            self.log(
                "Completion canceled. Respondent already completed or terminated survey."
            )

    def set_termination_details(self, rid, reason=None):
        lucid_rid = get_lucid_rid(rid)
        lucid_rid.terminated_at = datetime.now()
        lucid_rid.termination_reason = reason
        session.commit()

    def terminate_respondent(self, rid, reason):
        lucid_rid = get_lucid_rid(rid)

        if lucid_rid.completed_at is None and lucid_rid.terminated_at is None:
            response = self.send_terminate_request(rid)
            if response.ok:
                self.set_termination_details(rid, reason)
                session.commit()
                self.log("Respondent terminated successfully.")
            else:
                self.log(
                    f"Error terminating respondent. Status returned: {response.status_code}, reason: {response.reason}"
                )
        else:
            self.log(
                "Termination canceled. Respondent already completed or terminated survey."
            )

    def sha1_hash(self, url):
        """
        To allow for secure callbacks to Lucid Marketplace a hash needs to be appended to the URL
        which is used to e.g. terminate a participant or trigger a successful 'complete'.
        The algorithm for the generation of the SHA1 hash function makes use of a secret key
        which is provided by Lucid. The implementation below was taken from
        https://hash.lucidhq.engineering/submit/
        """
        import base64
        import hashlib
        import hmac

        encoded_key = self.sha1_hashing_key.encode("utf-8")
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


def get_lucid_rid(rid):
    from psynet.recruiters import LucidRID

    try:
        lucid_rid = LucidRID.query.filter_by(rid=rid).one()
    except NoResultFound:
        raise NoResultFound(
            f"No LucidRID for Lucid RID '{rid}' found. This should never happen."
        )
    except MultipleResultsFound:
        raise MultipleResultsFound(
            f"Multiple rows for Lucid RID '{rid}' found. This should never happen."
        )

    return lucid_rid
