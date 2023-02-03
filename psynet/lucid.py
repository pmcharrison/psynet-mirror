import json
from datetime import datetime

import requests
from dallinger.db import session
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from psynet.participant import Participant

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
        sandbox=True,
        recruitment_config=None,
        max_wait_secs=0,
    ):
        self.api_key = api_key
        self.sha1_hashing_key = sha1_hashing_key
        self.sandbox = False  # sandbox
        self.recruitment_config = recruitment_config
        self.max_wait_secs = max_wait_secs
        self.headers = {
            "Content-type": "application/json",
            "Authorization": api_key,
            "Accept": "text/plain",
        }

    @property
    def request_base_url_v1(self):
        url = "https://api.samplicio.us/Demand/v1"
        if self.sandbox:
            url = "https://sandbox.techops.engineering/Demand/v1"
        return url

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
        request_data = json.dumps({**params, **self.recruitment_config["survey"]})
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
                "LUCID: 'Create survey' request was invalid for unknown reason."
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
            response_data = response.json()

        return response_data

    def add_qualifications_to_survey(self, survey_number):
        """Add platform and browser specific qualifications to a survey."""
        qualifications = [
            {
                "Name": "MS_is_mobile",
                "QuestionID": 8214,
                "LogicalOperator": "NOT",
                "NumberOfRequiredConditions": 0,
                "IsActive": True,
                "Order": 1,
                "PreCodes": ["true"],
            },
            {
                "Name": "MS_browser_type_Non_Wurfl",
                "QuestionID": 1035,
                "LogicalOperator": "OR",
                "NumberOfRequiredConditions": 0,
                "IsActive": True,
                "Order": 2,
                "PreCodes": ["Chrome"],
            },
        ]

        for qualification in qualifications:
            request_data = json.dumps(qualification)
            response = requests.post(
                f"{self.request_base_url_v1}/SurveyQualifications/Create/{survey_number}",
                data=request_data,
                headers=self.headers,
            )
            response_data = response.json()

        return response_data

    def can_be_terminated(self, rid):
        participant_rids = [
            participant.entry_information.get("worker_id")
            for participant in Participant.query.all()
        ]

        if (datetime.now() - rid.creation_time).seconds <= self.recruitment_config[
            "termination_time_in_s"
        ]:
            return False

        if rid.rid not in participant_rids:
            return True

        try:
            participant = Participant.query.filter_by(worker_id=rid.rid).one()
        except NoResultFound:
            raise NoResultFound(
                f"No participant for Lucid RID '{rid}' found. This should never happen."
            )
        except MultipleResultsFound:
            raise MultipleResultsFound(
                f"Multiple participants for Lucid RID '{rid}' found. This should never happen."
            )
        if participant.progress == 0:
            return True

        return False

    def terminate_invalid_respondents(self):
        from psynet.recruiters import LucidRID

        for rid in LucidRID.query.filter_by(terminated_at=None).all():
            if self.can_be_terminated(rid):
                redirect_url = (
                    f"https://samplicio.us/s/ClientCallBack.aspx?RIS=20&RID={rid.rid}&"
                )
                redirect_url += f"hash={self.sha1_hash(redirect_url)}"
                self.log(
                    f"Terminating respondent with RID '{rid.rid}' using redirect URL '{redirect_url}'."
                )
                rid.termination_requested_at = datetime.now()
                session.commit()
                try:
                    response = requests.get(redirect_url)
                    if response.status_code == 200:
                        rid.terminated_at = datetime.now()
                        session.commit()
                        self.log(
                            f"Respondent terminated using redirect URL '{redirect_url}'."
                        )
                    else:
                        self.log(
                            f"Error terminating respondent using redirect URL '{redirect_url}'."
                        )
                        self.log(response.text)
                        self.log(response.__dict__)
                except Exception as e:
                    self.log(
                        f"Error terminating respondent using redirect URL '{redirect_url}':\n{e}"
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
