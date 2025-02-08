import json
import os.path
from datetime import datetime, timedelta
from typing import List

import pandas as pd
import requests
from dallinger.db import session
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from psynet import deployment_info
from psynet.participant import Participant
from psynet.utils import get_logger

__module__ = "psynet.lucid"
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
        default_locale="eng_gb",
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
        self.default_locale = default_locale

    @property
    def request_base_url_v1(self):
        return "https://api.samplicio.us/Demand/v1"

    @classmethod
    def log(cls, text):
        logger.info(f"LUCID RECRUITER: {text}")

    def create_survey(
        self,
        publish_experiment,
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
        if deployment_info.read("mode") == "live" and publish_experiment:
            survey_status_code = "03"
        survey_data["SurveyStatusCode"] = survey_status_code

        request_data = json.dumps({**params, **survey_data})
        response = requests.post(
            f"{self.request_base_url_v1}/Surveys/Create",
            data=request_data,
            headers=self.headers,
        )
        response_data = response.json()

        if "Survey" not in response_data:
            raise LucidServiceException(
                f"LUCID: Survey was missing in response data from request to create survey. Full response data: {response_data}"
            )

        if (
            "SurveySID" not in response_data["Survey"]
            or "SurveyNumber" not in response_data["Survey"]
        ):
            raise LucidServiceException(
                f"LUCID: SurveySID/SurveyNumber was missing in response data from request to create survey. Full response data: {response_data}"
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
        qualifications = self.recruitment_config.get("qualifications")
        if qualifications is None:
            self.log("No qualifications added to survey.")
            return

        for qualification in qualifications:
            request_data = json.dumps(qualification)
            response = requests.post(
                f"{self.request_base_url_v1}/SurveyQualifications/Create/{survey_number}",
                data=request_data,
                headers=self.headers,
            )

            if not response.ok:
                raise LucidServiceException(
                    f"LUCID: Error adding qualifications. Status returned: {response.status_code}, reason: {response.reason}"
                )

        if qualifications:
            self.log("Added qualifications to survey.")

    def get_qualifications(self, survey_number):
        url = f"https://api.samplicio.us/Demand/v1/SurveyQualifications/BySurveyNumber/{survey_number}"
        response = requests.get(url, headers=self.headers)
        assert response.status_code == 200
        return response.json()["Qualifications"]

    def can_be_terminated(self, lucid_rid):
        if (
            datetime.now() - lucid_rid.registered_at
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
                - (datetime.now() - lucid_rid.registered_at).seconds
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

    def set_termination_details(self, rid, reason=None, details=None):
        lucid_rid = get_lucid_rid(rid)
        lucid_rid.terminated_at = datetime.now()
        lucid_rid.termination_reason = reason
        lucid_rid.termination_details = details
        session.commit()

    def terminate_respondent(self, rid, reason, details=None):
        lucid_rid = get_lucid_rid(rid)

        if lucid_rid.completed_at is None and lucid_rid.terminated_at is None:
            response = self.send_terminate_request(rid)
            if response.ok:
                self.set_termination_details(rid, reason, details)
                session.commit()
                self.log("Respondent terminated successfully.")
            else:
                self.log(
                    f"Error terminating respondent. Status returned: {response.status_code}, reason: {response.reason}"
                )
        else:
            self.log(
                "Termination canceled. Respondent has already completed or terminated the survey."
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

    def _lookback_timestamp(self, days_lookback):
        timestamp_format = "%Y-%m-%dT%H:%M:%SZ"
        now = datetime.now()
        return (now - timedelta(days=days_lookback)).strftime(timestamp_format)

    def get_submissions(self, survey_number, days_lookback=60):
        entry_date_after = self._lookback_timestamp(days_lookback)
        url = f"https://api.samplicio.us/demand/v2-beta/sessions?survey_id={survey_number}&entry_date_after={entry_date_after}"
        response = requests.get(url, headers=self.headers)
        assert response.ok
        return response.json()["sessions"]

    def get_lucid_country_language_lookup(self):
        url = "https://api.samplicio.us/Lookup/v1/BasicLookups/BundledLookups/CountryLanguages"
        response = requests.get(url, headers=self.headers)
        assert response.ok
        lookup = pd.DataFrame(response.json()["AllCountryLanguages"])
        codes = lookup.Code.apply(lambda x: x.split("-"))
        names = lookup.Name.apply(lambda x: x.split("-"))
        lookup["language_tag"] = codes.apply(lambda x: x[0].strip())
        lookup["country_tag"] = codes.apply(lambda x: x[1].strip())
        lookup["language_name"] = names.apply(lambda x: x[0].strip())
        lookup["country_name"] = names.apply(lambda x: x[1].strip())
        return lookup[
            ["language_tag", "country_tag", "language_name", "country_name", "Id"]
        ]

    def _get_question_field(self, question_id, field, locale=None):
        if locale is None:
            locale = self.default_locale
        url = f"https://api.samplicio.us/demand/v2-beta/questions?id={question_id}&locale={locale}&fields={field}"
        response = requests.get(url, headers=self.headers)
        assert response.ok
        result = response.json()["result"]
        assert (
            len(result) > 0
        ), f"No question with id {question_id} found for locale {locale}."
        return result

    def get_answer_options(self, question_id, locale=None):
        field = "question_options"
        result = self._get_question_field(question_id, field, locale)
        return pd.DataFrame(result[0][field])

    def get_question_name(self, question_id, locale=None):
        field = "question_text"
        result = self._get_question_field(question_id, field, locale)
        return result[0][field]

    default_fields = [
        "create_date",
        "name",
        "status",
        "total_completes",
        "expected_completes",
        "total_screens",
        "locale",
    ]

    def list_studies(
        self, allowed_statuses=None, n=200, fields=None, order_by="create_date"
    ):
        url = "https://api.samplicio.us/demand/v2-beta/surveys"
        if fields is None:
            fields = self.default_fields
        fields_str = ",".join(fields)
        url += f"?fields={fields_str}&page_size={n}&order_by={order_by}"
        if allowed_statuses is not None:
            url += f"&status={','.join(allowed_statuses)}"
        response = requests.get(url, headers=self.headers)
        assert response.ok
        return response.json()["result"]

    def _get_survey_fields(self, survey_number, fields):
        fields_str = ",".join(fields)
        url = f"https://api.samplicio.us/demand/v2-beta/surveys?id={survey_number}&fields={fields_str}"
        response = requests.get(url, headers=self.headers)
        assert response.ok
        result = response.json()["result"]
        assert len(result) > 0, f"No survey with id {survey_number} found."
        return [result[0][field] for field in fields]

    def get_survey_status(self, survey_number):
        return self._get_survey_fields(survey_number, ["status"])[0]

    def get_summary(self, survey_number, days_lookback=60):
        entry_date_after = self._lookback_timestamp(days_lookback)
        url = f"https://api.samplicio.us/demand/v2-beta/sessions/statistics?survey_id={survey_number}&entry_date_after={entry_date_after}"
        response = requests.get(url, headers=self.headers)
        assert response.ok
        stats = response.json()["statistics"]

        (
            status,
            last_complete_date,
            total_screens,
            total_completes,
        ) = self._get_survey_fields(
            survey_number,
            ["status", "last_complete_date", "total_screens", "total_completes"],
        )

        cost = stats["cost"]

        return {
            "cost": cost["amount"],
            "currency": cost["currency_code"],
            "exchange_rate": cost["exchange_rate"],
            "epc": stats["earnings_per_click"],
            "completion_loi": stats["median_length_of_interview"],
            "termination_loi": stats["system_conversion"],
            "system_conversion": stats["system_conversion"],
            "status": status,
            "last_complete_date": last_complete_date,
            "total_entrants": stats["total_entrants"],
            "total_screens": total_screens,
            "total_completes": total_completes,
        }

    def change_status(self, survey_number, new_status):
        """
        Change the status of a survey.
        The status can be one of the following:
        - awarded (created and only available within your account to adjust)
        - live (available for Suppliers to send respondents to)
        - pending (pausing the Survey in order_by to fix or adjust the Survey or pause the influx of fielding)
        - paused (the Survey is paused and not available for Suppliers to send respondents to)
        - complete (the Survey is finished fielding)
        - archived (Survey deleted)
        Parameters
        ----------
        survey_number: int
        new_status: str

        Returns
        -------

        """
        from psynet.recruiters import BaseLucidRecruiter

        assert new_status in BaseLucidRecruiter.survey_codes

        url = f"https://api.samplicio.us/demand/v2-beta/surveys/{survey_number}"
        data = json.dumps({"status": new_status})
        headers = {
            **self.headers,
            "Content-type": "application/json",
            "Accept": "text/plain",
        }
        response = requests.patch(url, data=data, headers=headers)
        assert response.ok
        logger.info(f"Experiment {survey_number} is set to status: {new_status}")
        return response.json()

    def reconcile(self, survey_number, rid: List[str]):
        assert (
            self.get_survey_status(survey_number) == "complete"
        ), "Survey must be complete to reconcile."
        url = f"https://api.samplicio.us/Demand/v1/Surveys/Reconcile/{survey_number}"
        data = json.dumps({"ResponseIDs": rid})
        headers = {
            **self.headers,
            "Content-type": "application/json",
            "Accept": "text/plain",
        }
        response = requests.post(url, data=data, headers=headers)
        assert response.ok
        return response.json()

    def get_questions(self, standard: bool = True, fields: List[str] = None):
        if fields is None:
            fields = ["name", "id"]
        fields = ",".join(fields)
        class_name = "standard" if standard else "custom"
        url = f"https://api.samplicio.us/demand/v2-beta/questions?fields={fields}&class={class_name}"
        response = requests.get(url, headers=self.headers)
        assert response.ok
        return response.json()["result"]

    def get_qualifications_dict(self):
        qualification_list = self.get_questions(standard=False) + self.get_questions(
            standard=True
        )
        return {q["name"]: q["id"] for q in qualification_list}

    def get_cost(self, survey_number):
        url = "https://api.samplicio.us/v1/reports/surveys/financesummary.json"
        data = json.dumps({"survey_ids": [survey_number]})
        headers = {
            "Content-type": "application/json",
            "Accept": "text/plain",
            **self.headers,
        }
        response = requests.post(url, data=data, headers=headers)
        summary = response.json()["summary"]
        total_completes = summary["completes"]
        total_cost = float(summary["total_cost"])
        cost_per_complete = total_cost / total_completes if total_completes > 0 else 0
        return {
            "total": total_cost,
            "sample": summary["sample_cost"],
            "fee": summary["buyer_fees"],
            "currency": summary["currency"],
            "total_completes": total_completes,
            "cost_per_complete": cost_per_complete,
        }


def get_lucid_service(config=None, recruitment_config=None):
    if os.path.exists("config.txt"):
        if config is None:
            from psynet.utils import get_config

            config = get_config()
        config_entries = config
    else:
        import configparser

        config = configparser.ConfigParser()
        dallinger_config = os.path.join(os.path.expanduser("~"), ".dallingerconfig")
        assert os.path.exists(
            dallinger_config
        ), f"Could not find Dallinger config file at {dallinger_config}"
        config.read(dallinger_config)
        config_entries = {}
        for section in config.sections():
            for key, value in config.items(section):
                config_entries[key] = value
    if recruitment_config is None:
        recruitment_config = {}
    return LucidService(
        api_key=config_entries.get("lucid_api_key"),
        sha1_hashing_key=config_entries.get("lucid_sha1_hashing_key"),
        exp_config=config,
        recruitment_config=recruitment_config,
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
