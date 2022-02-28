import json

import requests

from .utils import get_logger

logger = get_logger()


class LucidServiceException(Exception):
    """Custom exception type"""


class LucidService(object):
    """
    Facade for Lucid Marketplace services provided via its HTTP API.
    """

    def __init__(
        self,
        api_key,
        sandbox=True,
        recruitment_config=None,
        max_wait_secs=0,
    ):
        self.api_key = api_key
        self.is_sandbox = sandbox
        self.recruitment_config = recruitment_config
        self.max_wait_secs = max_wait_secs
        self.headers = {
            "Content-type": "application/json",
            "Authorization": api_key,
            "Accept": "text/plain",
        }

    @property
    def request_base_url(self):
        url = "https://live.techops.engineering/demand/v2-beta"
        if self.is_sandbox:
            # url = "https://api.samplicio.us/demand/v2-beta"
            url = "https://sandbox.techops.engineering/demand/v2-beta"
        return url

    @property
    def request_base_url_v1(self):
        url = "https://live.techops.engineering/Demand/v1"
        if self.is_sandbox:
            url = "https://sandbox.techops.engineering/Demand/v1"
        return url

    @property
    def survey_update_url(self):
        return f"{self.request_base_url}/surveys"

    def create_survey(
        self,
        id,
        name,
        quota,
        live_url,
    ):
        """
        Create a survey and return a dict with its properties.
        """

        # Create the survey
        # "owner_id": 38490             # TODO: Is this correct? Got from dictionary lookup for users
        # "business_unit_id": 2404,     # TODO: Get business unit id dynamically
        # "project_manager_id": 38490,  # TODO: Is this correct? Got from dictionary lookup for users
        params = {
            # "project_id": response_data["id"],
            "ClientSurveyLiveURL": live_url,
            "TestRedirectURL": live_url,
            "Quota": quota,
            "name": name,
        }
        request_data = json.dumps({**params, **self.recruitment_config["survey"]})
        # request_data = json.dumps({})
        response = requests.post(
            f"{self.request_base_url_v1}/Surveys/Create",
            data=request_data,
            headers=self.headers,
        )
        response_data = response.json()
        logger.info("+++++ response_data +++++")
        logger.info(response_data)
        logger.info("+++++ response_data +++++")
        if (
            "SurveySID" not in response_data["Survey"]
            or "SurveyNumber" not in response_data["Survey"]
        ):
            raise LucidServiceException(
                ">>>>>>>>>> LUCID: 'Create survey' request was invalid for unknown reason."
            )
        logger.info(
            f'>>>>>>>>>> LUCID: Survey with number {response_data["Survey"]["SurveyNumber"]} created successfully.'
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

    def get_qualifications(self, survey_number):
        response = requests.get(
            f"{self.request_base_url_v1}/SurveyQualifications/BySurveyNumber/{survey_number}",
            headers=self.headers,
        )
        return response.json()

    def update_quota(self, survey_number, quota_id, number):
        request_data = self.recruitment_config["sub_quota"]
        request_data.update({"SurveyQuotaID": quota_id, "Quota": number})
        request_data = json.dumps(request_data)
        response = requests.put(
            f"{self.request_base_url_v1}/SurveyQuotas/Update/{survey_number}",
            data=request_data,
            headers=self.headers,
        )

        if not response.ok:
            raise LucidServiceException(
                f"Error updating quota ({survey_number}): {response.text}"
            )

        response_data = response.json()
        logger.info(
            f'>>>>>>>>>> LUCID: Quota for {response_data["Quotas"][1]["Name"]} to {response_data["Quotas"][1]["Quota"]} updated successfully.'
        )

        return response_data

    def complete_survey(self, survey_number):
        params = {
            "status": "complete",
        }
        request_data = json.dumps(params)
        response = requests.patch(
            f"{self.request_base_url}/surveys/{survey_number}",
            data=request_data,
            headers=self.headers,
        )

        if not response.ok:
            raise LucidServiceException(
                f"Error completing survey ({survey_number}): {response.text}"
            )

        logger.info(f">>>>>>>>>> LUCID: Survey with id {survey_number} completed.")
        return response.json()

    def get_quotas(self, survey_number):
        response = requests.get(
            f"{self.request_base_url_v1}/SurveyQuotas/BySurveyNumber/{survey_number}",
            headers=self.headers,
        )

        if not response.ok:
            raise LucidServiceException(
                f"Error getting quota for survey ({survey_number}): {response.text}"
            )
        logger.info(
            f">>>>>>>>>> LUCID: Quotas for survey with id '{survey_number}') successfully retrieved."
        )

        return response.json()

    def sha1_hash(self, url):
        import base64
        import hashlib
        import hmac

        encoded_key = self.api_key.encode("utf-8")
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
