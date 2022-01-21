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
        live_url,
    ):
        """
        Create the survey and return a dict with its useful properties.
        """

        # Create the survey
        # "owner_id": 38490             # TODO: Is this correct? Got from dictionary lookup for users
        # "business_unit_id": 2404,     # TODO: Get business unit id dynamically
        # "project_manager_id": 38490,  # TODO: Is this correct? Got from dictionary lookup for users
        params = {
            # "project_id": response_data["id"],
            "ClientSurveyLiveURL": live_url,
            "TestRedirectURL": live_url,  # TODO: Different one?
            "name": name,
        }
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
                ">>>>>>>>>> LUCID: 'Create survey' request was invalid for unknown reason."
            )
        logger.info(
            f'>>>>>>>>>> LUCID: Survey with number {response_data["Survey"]["SurveyNumber"]} created successfully.'
        )

        return response_data["Survey"]

    def create_qualifications_and_quota(self, survey_id, number, duration_hours=None):
        """
        Create qualifications and quota
        """

        # Create qualifications
        request_data = json.dumps(self.recruitment_config["qualifications"])
        response = requests.post(
            f"{self.request_base_url_v1}/SurveyQualifications/Create/{survey_id}",
            data=request_data,
            headers=self.headers,
        )
        response_data = response.json()

        if "ResultCount" not in response_data:
            raise LucidServiceException(
                ">>>>>>>>>> LUCID: 'Create qualifications' request was invalid for unknown reason."
            )
        logger.info(
            f">>>>>>>>>> LUCID: Qualifications ({response_data}) created successfully."
        )

        # Create Quota
        request_data = json.dumps(self.recruitment_config["sub_quota"])
        response = requests.post(
            f"{self.request_base_url_v1}/SurveyQuotas/Create/{survey_id}",
            data=request_data,
            headers=self.headers,
        )
        response_data = response.json()

        if "ResultCount" not in response_data:
            raise LucidServiceException(
                ">>>>>>>>>> LUCID: 'Create subquota' request was invalid for unknown reason."
            )
        logger.info(f">>>>>>>>>> LUCID: Quota ({response_data}) created successfully.")

        return response_data

    def update_quota(self, survey_id, quota_id, number):
        request_data = self.recruitment_config["sub_quota"]
        request_data.update({"SurveyQuotaID": quota_id, "Quota": number})
        request_data = json.dumps(request_data)
        response = requests.put(
            f"{self.request_base_url_v1}/SurveyQuotas/Update/{survey_id}",
            data=request_data,
            headers=self.headers,
        )
        response_data = response.json()

        if "ResultCount" not in response_data:
            raise LucidServiceException(
                ">>>>>>>>>> LUCID: 'Update quota' request was invalid for unknown reason."
            )
        logger.info(
            f'>>>>>>>>>> LUCID: Updated quota for {response_data["Quotas"][1]["Name"]} to {response_data["Quotas"][1]["Quota"]}.'
        )

        return response_data

    def complete_survey(self, survey_id):
        params = {
            "status": "complete",
        }
        request_data = json.dumps(params)
        response = requests.patch(
            f"{self.request_base_url}/surveys/{survey_id}",
            data=request_data,
            headers=self.headers,
        )
        response_data = response.json()

        if response.status_code != 200:
            raise LucidServiceException(
                ">>>>>>>>>> LUCID: 'Update survey' request was invalid for unknown reason."
            )
        logger.info(f">>>>>>>>>> LUCID: Survey with id {survey_id} completed.")

        return response_data

    def get_quotas(self, survey_id):
        response = requests.get(
            f"{self.request_base_url_v1}/SurveyQuotas/BySurveyNumber/{survey_id}",
            headers=self.headers,
        )
        response_data = response.json()

        if "ResultCount" not in response_data:
            raise LucidServiceException(
                f">>>>>>>>>> LUCID: 'Update quota' request for survey id '{survey_id}' was invalid for unknown reason."
            )
        logger.info(
            f">>>>>>>>>> LUCID: Quotas for survey with id '{survey_id}') successfully retrieved."
        )

        return response_data
