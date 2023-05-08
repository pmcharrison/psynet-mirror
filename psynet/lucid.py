import json
from datetime import datetime

import requests
from dallinger.db import session
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from psynet.participant import Participant

from .utils import get_logger

logger = get_logger()


def compute_lucid_reach(
    initial_recruitment_size,
    days,
    completion_time,
    incidence_rate,
    price_ceiling,
    language_code,
    country_code,
    api_key,
):
    url = "https://api.samplicio.us/demand/v2-beta/reach/audience-estimate"
    data = json.dumps(
        {
            "qualifications": [
                {
                    # MS_is_mobile
                    "question_id": 8214,
                    "condition": "false",
                },
                {
                    # MS_browser_type_Non_Wurfl
                    "question_id": 1035,
                    "condition": "Chrome",
                },
            ],
            "completes": initial_recruitment_size,
            "days": days,
            "length_of_interview": completion_time,
            "incidence_rate": incidence_rate,
            "price_ceiling": price_ceiling,
            "locale": f"{language_code}_{country_code}",
        }
    )
    headers = {
        "Content-type": "application/json",
        "Authorization": api_key,
        "Accept": "text/plain",
    }
    response = requests.post(url, data=data, headers=headers)
    assert response.status_code == 200, f"Error: {response.status_code} {response.text}"
    return response.json()


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
        sandbox=True,
        max_wait_secs=0,
    ):
        self.api_key = api_key
        self.sha1_hashing_key = sha1_hashing_key
        self.exp_config = exp_config
        self.recruitment_config = recruitment_config
        self.sandbox = False  # sandbox
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
        survey_data = self.recruitment_config["survey"]
        survey_data["CountryLanguageID"] = get_country_language_id(
            self.recruitment_config["country"], self.recruitment_config["language"]
        )
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
            response_data = response.json()

        return response_data

    def can_be_terminated(self, lucid_rid):
        rid = lucid_rid.rid
        participant_rids = [
            participant.entry_information.get("worker_id")
            for participant in Participant.query.all()
        ]

        if (
            datetime.now() - lucid_rid.creation_time
        ).seconds <= self.recruitment_config["termination_time_in_s"]:
            return False

        if rid not in participant_rids:
            return True

        try:
            participant = Participant.query.filter_by(worker_id=rid).one()
        except NoResultFound:
            raise NoResultFound(
                f"Method 'can_be_terminated': No participant for Lucid RID '{rid}' found. This should never happen."
            )
        except MultipleResultsFound:
            raise MultipleResultsFound(
                f"Multiple participants for Lucid RID '{rid}' found. This should never happen."
            )
        if participant.progress == 0:
            return True

        return False

    def check_respondent_termination(self, rid):
        lucid_rid = get_lucid_rid(rid)

        if lucid_rid.terminated_at is not None:
            return -1

        if self.can_be_terminated(lucid_rid):
            self.terminate_respondent(rid)
        else:
            time_until_termination_in_s = (
                self.recruitment_config["termination_time_in_s"]
                - (datetime.now() - lucid_rid.creation_time).seconds
            )
            logger.info(
                f"Seconds until termination of RID '{rid}': {time_until_termination_in_s}"
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

    def terminate_respondent(self, rid):
        lucid_rid = get_lucid_rid(rid)

        if lucid_rid.completed_at is None and lucid_rid.terminated_at is None:
            response = self.send_terminate_request(rid)
            if response.ok:
                lucid_rid.terminated_at = datetime.now()
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


def get_country_language_id(country, lang):
    data = {
        "Chinese Traditional": {
            "Hong Kong": {"id": 2, "code": "CHI-HK"},
            "Taiwan": {"id": 3, "code": "CHI-TW"},
        },
        "Dutch": {
            "Netherlands": {"id": 4, "code": "DUT-NL"},
            "Belgium": {"id": 28, "code": "DUT-BE"},
        },
        "English": {
            "Australia": {"id": 5, "code": "ENG-AU"},
            "Canada": {"id": 6, "code": "ENG-CA"},
            "India": {"id": 7, "code": "ENG-IN"},
            "United Kingdom": {"id": 8, "code": "ENG-GB"},
            "United States": {"id": 9, "code": "ENG-US"},
            "Switzerland": {"id": 36, "code": "ENG-CH"},
            "Ireland": {"id": 43, "code": "ENG-IE"},
            "South Africa": {"id": 49, "code": "ENG-ZA"},
            "Singapore": {"id": 50, "code": "ENG-SG"},
            "New Zealand": {"id": 57, "code": "ENG-NZ"},
            "Philippines": {"id": 58, "code": "ENG-PH"},
            "Indonesia": {"id": 59, "code": "ENG-ID"},
            "Malaysia": {"id": 61, "code": "ENG-MY"},
            "Hong Kong": {"id": 73, "code": "ENG-HK"},
            "Germany": {"id": 74, "code": "ENG-DE"},
            "Nigeria": {"id": 84, "code": "ENG-NG"},
            "United Arab Emirates": {"id": 93, "code": "ENG-AE"},
            "Netherlands": {"id": 95, "code": "ENG-NL"},
            "Kenya": {"id": 97, "code": "ENG-KE"},
            "China": {"id": 98, "code": "ENG-CN"},
            "France": {"id": 99, "code": "ENG-FR"},
            "Russia": {"id": 100, "code": "ENG-RU"},
            "Algeria": {"id": 101, "code": "ENG-DZ"},
            "Lebanon": {"id": 102, "code": "ENG-LB"},
            "Morocco": {"id": 103, "code": "ENG-MA"},
            "Argentina": {"id": 107, "code": "ENG-AR"},
            "Brazil": {"id": 108, "code": "ENG-BR"},
            "Colombia": {"id": 109, "code": "ENG-CO"},
            "Greece": {"id": 110, "code": "ENG-GR"},
            "Israel": {"id": 111, "code": "ENG-IL"},
            "Italy": {"id": 112, "code": "ENG-IT"},
            "Japan": {"id": 113, "code": "ENG-JP"},
            "Korea": {"id": 114, "code": "ENG-KR"},
            "Mexico": {"id": 115, "code": "ENG-MX"},
            "Turkey": {"id": 116, "code": "ENG-TR"},
            "Spain": {"id": 119, "code": "ENG-ES"},
            "Pakistan": {"id": 120, "code": "ENG-PK"},
            "Austria": {"id": 122, "code": "ENG-AT"},
            "Puerto Rico": {"id": 125, "code": "ENG-PR"},
            "Egypt": {"id": 128, "code": "ENG-EG"},
            "Belgium": {"id": 144, "code": "ENG-BE"},
            "Chile": {"id": 145, "code": "ENG-CL"},
            "Denmark": {"id": 146, "code": "ENG-DK"},
            "Finland": {"id": 147, "code": "ENG-FI"},
            "Norway": {"id": 148, "code": "ENG-NO"},
            "Saudi Arabia": {"id": 149, "code": "ENG-SA"},
            "Vietnam": {"id": 150, "code": "ENG-VN"},
            "Malta": {"id": 159, "code": "ENG-MT"},
            "Poland": {"id": 162, "code": "ENG-PL"},
            "Romania": {"id": 163, "code": "ENG-RO"},
            "Sweden": {"id": 164, "code": "ENG-SE"},
            "Thailand": {"id": 165, "code": "ENG-TH"},
            "Hungary": {"id": 167, "code": "ENG-HU"},
            "Bahamas": {"id": 187, "code": "ENG-BS"},
            "Belize": {"id": 188, "code": "ENG-BZ"},
            "Jamaica": {"id": 193, "code": "ENG-JM"},
            "Ethiopia": {"id": 197, "code": "ENG-ET"},
            "Luxembourg": {"id": 201, "code": "ENG-LU"},
            "Angola": {"id": 210, "code": "ENG-AO"},
            "Benin": {"id": 211, "code": "ENG-BJ"},
            "Botswana": {"id": 212, "code": "ENG-BW"},
            "Burkina Faso": {"id": 213, "code": "ENG-BF"},
            "Cameroon": {"id": 214, "code": "ENG-CM"},
            "Cape Verde": {"id": 215, "code": "ENG-CV"},
            "Chad": {"id": 216, "code": "ENG-TD"},
            "Comoros": {"id": 217, "code": "ENG-KM"},
            "Republic of the Congo": {"id": 218, "code": "ENG-CG"},
            "Djibouti": {"id": 219, "code": "ENG-DJ"},
            "Equatorial Guinea": {"id": 220, "code": "ENG-GQ"},
            "Eritrea": {"id": 221, "code": "ENG-ER"},
            "Gabon": {"id": 222, "code": "ENG-GA"},
            "Gambia": {"id": 223, "code": "ENG-GM"},
            "Ghana": {"id": 224, "code": "ENG-GH"},
            "Guinea": {"id": 225, "code": "ENG-GN"},
            "Guinea-Bissau": {"id": 226, "code": "ENG-GW"},
            "Kuwait": {"id": 227, "code": "ENG-KW"},
            "Lesotho": {"id": 228, "code": "ENG-LS"},
            "Liberia": {"id": 229, "code": "ENG-LR"},
            "Madagascar": {"id": 230, "code": "ENG-MG"},
            "Malawi": {"id": 231, "code": "ENG-MW"},
            "Mali": {"id": 232, "code": "ENG-ML"},
            "Mauritania": {"id": 233, "code": "ENG-MR"},
            "Mauritius": {"id": 234, "code": "ENG-MU"},
            "Mozambique": {"id": 235, "code": "ENG-MZ"},
            "Namibia": {"id": 236, "code": "ENG-NA"},
            "Niger": {"id": 237, "code": "ENG-NE"},
            "Qatar": {"id": 238, "code": "ENG-QA"},
            "Republic of the Côte d'Ivoire": {"id": 239, "code": "ENG-CI"},
            "Rwanda": {"id": 240, "code": "ENG-RW"},
            "São Tomé and Príncipe": {"id": 241, "code": "ENG-ST"},
            "Senegal": {"id": 242, "code": "ENG-SN"},
            "Seychelles": {"id": 243, "code": "ENG-SC"},
            "Sierra Leone": {"id": 244, "code": "ENG-SL"},
            "Swaziland": {"id": 245, "code": "ENG-SZ"},
            "Tanzania": {"id": 246, "code": "ENG-TZ"},
            "Togo": {"id": 247, "code": "ENG-TG"},
            "Tunisia": {"id": 248, "code": "ENG-TN"},
            "Uganda": {"id": 249, "code": "ENG-UG"},
            "Zambia": {"id": 250, "code": "ENG-ZM"},
            "Portugal": {"id": 271, "code": "ENG-PT"},
            "Myanmar": {"id": 274, "code": "ENG-MM"},
            "Guyana": {"id": 280, "code": "ENG-GY"},
            "Bulgaria": {"id": 282, "code": "ENG-BG"},
            "Costa Rica": {"id": 283, "code": "ENG-CR"},
            "Croatia": {"id": 284, "code": "ENG-HR"},
            "Czech Republic": {"id": 285, "code": "ENG-CZ"},
            "Dominican Republic": {"id": 286, "code": "ENG-DO"},
            "Ecuador": {"id": 287, "code": "ENG-EC"},
            "El Salvador": {"id": 288, "code": "ENG-SV"},
            "Estonia": {"id": 289, "code": "ENG-EE"},
            "Guatemala": {"id": 290, "code": "ENG-GT"},
            "Honduras": {"id": 291, "code": "ENG-HN"},
            "Iceland": {"id": 292, "code": "ENG-IS"},
            "Iraq": {"id": 293, "code": "ENG-IQ"},
            "Jordan": {"id": 294, "code": "ENG-JO"},
            "Latvia": {"id": 295, "code": "ENG-LV"},
            "Libyan Arab Jamahiriya": {"id": 296, "code": "ENG-LY"},
            "Lithuania": {"id": 297, "code": "ENG-LT"},
            "Nicaragua": {"id": 298, "code": "ENG-NI"},
            "Oman": {"id": 299, "code": "ENG-OM"},
            "Palestine": {"id": 300, "code": "ENG-PS"},
            "Panama": {"id": 301, "code": "ENG-PA"},
            "Paraguay": {"id": 302, "code": "ENG-PY"},
            "Peru": {"id": 303, "code": "ENG-PE"},
            "Serbia": {"id": 304, "code": "ENG-RS"},
            "Slovakia (Slovak Republic)": {"id": 305, "code": "ENG-SK"},
            "Slovenia": {"id": 306, "code": "ENG-SI"},
            "Sri Lanka": {"id": 307, "code": "ENG-LK"},
            "Taiwan Province Of China": {"id": 308, "code": "ENG-TW"},
            "Ukraine": {"id": 309, "code": "ENG-UA"},
            "Uruguay": {"id": 310, "code": "ENG-UY"},
            "Venezuela": {"id": 311, "code": "ENG-VE"},
            "Yemen": {"id": 312, "code": "ENG-YE"},
            "Haiti": {"id": 313, "code": "ENG-HT"},
            "Democratic Republic of the Congo": {"id": 324, "code": "ENG-CD"},
        },
        "French": {
            "France": {"id": 10, "code": "FRE-FR"},
            "Canada": {"id": 25, "code": "FRE-CA"},
            "Belgium": {"id": 26, "code": "FRE-BE"},
            "Switzerland": {"id": 34, "code": "FRE-CH"},
            "Luxembourg": {"id": 124, "code": "FRE-LU"},
            "Tunisia": {"id": 131, "code": "FRE-TN"},
            "Algeria": {"id": 199, "code": "FRE-DZ"},
            "Morocco": {"id": 203, "code": "FRE-MA"},
            "Benin": {"id": 251, "code": "FRE-BJ"},
            "Burkina Faso": {"id": 252, "code": "FRE-BF"},
            "Cameroon": {"id": 253, "code": "FRE-CM"},
            "Chad": {"id": 254, "code": "FRE-TD"},
            "Comoros": {"id": 255, "code": "FRE-KM"},
            "Republic of the Congo": {"id": 256, "code": "FRE-CG"},
            "Djibouti": {"id": 257, "code": "FRE-DJ"},
            "Equatorial Guinea": {"id": 258, "code": "FRE-GQ"},
            "Gabon": {"id": 259, "code": "FRE-GA"},
            "Guinea": {"id": 260, "code": "FRE-GN"},
            "Mauritius": {"id": 261, "code": "FRE-MU"},
            "Niger": {"id": 262, "code": "FRE-NE"},
            "Republic of the Côte d'Ivoire": {"id": 263, "code": "FRE-CI"},
            "Senegal": {"id": 264, "code": "FRE-SN"},
            "Seychelles": {"id": 265, "code": "FRE-SC"},
            "Togo": {"id": 266, "code": "FRE-TG"},
            "Madagascar": {"id": 318, "code": "FRE-MG"},
            "Mali": {"id": 319, "code": "FRE-ML"},
            "Rwanda": {"id": 321, "code": "FRE-RW"},
            "Haiti": {"id": 323, "code": "FRE-HT"},
            "Democratic Republic of the Congo": {"id": 325, "code": "FRE-CD"},
        },
        "German": {
            "Germany": {"id": 11, "code": "GER-DE"},
            "Switzerland": {"id": 12, "code": "GER-CH"},
            "Austria": {"id": 38, "code": "GER-AT"},
            "Belgium": {"id": 94, "code": "GER-BE"},
            "Luxembourg": {"id": 200, "code": "GER-LU"},
        },
        "Italian": {
            "Italy": {"id": 13, "code": "ITA-IT"},
            "Switzerland": {"id": 35, "code": "ITA-CH"},
        },
        "Japanese": {
            "Japan": {"id": 14, "code": "JPN-JP"},
            "United States": {"id": 143, "code": "JPN-US"},
        },
        "Polish": {"Poland": {"id": 15, "code": "POL-PL"}},
        "Portuguese": {
            "Brazil": {"id": 16, "code": "POR-BR"},
            "Portugal": {"id": 17, "code": "POR-PT"},
            "Angola": {"id": 267, "code": "POR-AO"},
            "Mozambique": {"id": 268, "code": "POR-MZ"},
            "Cape Verde": {"id": 314, "code": "POR-CV"},
            "Equatorial Guinea": {"id": 315, "code": "POR-GQ"},
            "Guinea-Bissau": {"id": 317, "code": "POR-GW"},
            "Sao Tome And Principe": {"id": 322, "code": "POR-ST"},
        },
        "Russian": {
            "Russia": {"id": 18, "code": "RUS-RU"},
            "Kazakhstan": {"id": 86, "code": "RUS-KZ"},
        },
        "Spanish": {
            "Argentina": {"id": 19, "code": "SPA-AR"},
            "Colombia": {"id": 20, "code": "SPA-CO"},
            "Mexico": {"id": 21, "code": "SPA-MX"},
            "Spain": {"id": 22, "code": "SPA-ES"},
            "United States": {"id": 27, "code": "SPA-US"},
            "Venezuela": {"id": 41, "code": "SPA-VE"},
            "Chile": {"id": 47, "code": "SPA-CL"},
            "Costa Rica": {"id": 64, "code": "SPA-CR"},
            "El Salvador": {"id": 65, "code": "SPA-SV"},
            "Guatemala": {"id": 66, "code": "SPA-GT"},
            "Honduras": {"id": 67, "code": "SPA-HN"},
            "Nicaragua": {"id": 68, "code": "SPA-NI"},
            "Panama": {"id": 69, "code": "SPA-PA"},
            "Peru": {"id": 80, "code": "SPA-PE"},
            "Ecuador": {"id": 89, "code": "SPA-EC"},
            "Dominican Republic": {"id": 123, "code": "SPA-DO"},
            "Puerto Rico": {"id": 126, "code": "SPA-PR"},
            "Bolivia": {"id": 189, "code": "SPA-BO"},
            "Paraguay": {"id": 194, "code": "SPA-PY"},
            "Uruguay": {"id": 196, "code": "SPA-UY"},
            "Equatorial Guinea": {"id": 270, "code": "SPA-GQ"},
        },
        "Swedish": {"Sweden": {"id": 23, "code": "SWE-SE"}},
        "Korean": {
            "Korea ": {"id": 24, "code": "KOR-KR"},
            "United States": {"id": 117, "code": "KOR-US"},
        },
        "Arabic": {
            "Saudi Arabia": {"id": 29, "code": "ARA-SA"},
            "Egypt": {"id": 77, "code": "ARA-EG"},
            "United Arab Emirates": {"id": 82, "code": "ARA-AE"},
            "Qatar": {"id": 83, "code": "ARA-QA"},
            "Jordan": {"id": 87, "code": "ARA-JO"},
            "Algeria": {"id": 104, "code": "ARA-DZ"},
            "Lebanon": {"id": 105, "code": "ARA-LB"},
            "Morocco": {"id": 106, "code": "ARA-MA"},
            "Mauritania": {"id": 129, "code": "ARA-MR"},
            "Tunisia": {"id": 130, "code": "ARA-TN"},
            "Libya": {"id": 132, "code": "ARA-LY"},
            "Iraq": {"id": 134, "code": "ARA-IQ"},
            "Kuwait": {"id": 136, "code": "ARA-KW"},
            "Yemen": {"id": 137, "code": "ARA-YE"},
            "Oman": {"id": 138, "code": "ARA-OM"},
            "Palestine": {"id": 139, "code": "ARA-PS"},
            "Bahrain": {"id": 141, "code": "ARA-BH"},
            "United States": {"id": 204, "code": "ARA-US"},
            "Chad": {"id": 205, "code": "ARA-TD"},
            "Comoros": {"id": 206, "code": "ARA-KM"},
            "Djibouti": {"id": 207, "code": "ARA-DJ"},
            "Eritrea": {"id": 316, "code": "ARA-ER"},
        },
        "Norwegian": {"Norway": {"id": 30, "code": "NOR-NO"}},
        "Danish": {"Denmark": {"id": 31, "code": "DAN-DK"}},
        "Finnish": {"Finland": {"id": 32, "code": "FIN-FI"}},
        "Turkish": {"Turkey": {"id": 37, "code": "TUR-TR"}},
        "Czech": {"Czech Republic": {"id": 39, "code": "CZE-CZ"}},
        "Greek": {"Greece": {"id": 40, "code": "GRE-GR"}},
        "Icelandic": {"Iceland": {"id": 42, "code": "ICE-IS"}},
        "Romanian": {"Romania": {"id": 45, "code": "RUM-RO"}},
        "Bulgarian": {"Bulgaria": {"id": 46, "code": "BUL-BG"}},
        "Luxembourg": {"Luxembourg": {"id": 51, "code": "LTZ-LU"}},
        "Indonesian": {"Indonesia": {"id": 52, "code": "IND-ID"}},
        "Malay": {
            "Malaysia": {"id": 53, "code": "MAY-MY"},
            "Indonesia": {"id": 151, "code": "MAY-ID"},
            "Singapore": {"id": 153, "code": "MAY-SG"},
        },
        "Thai": {"Thailand": {"id": 54, "code": "THA-TH"}},
        "Tagalog": {"Philippines": {"id": 55, "code": "TGL-PH"}},
        "Ukrainian": {"Ukraine": {"id": 56, "code": "UKR-UA"}},
        "Hungarian": {"Hungary": {"id": 62, "code": "HUN-HU"}},
        "Latvian": {"Latvia": {"id": 63, "code": "LAT-LV"}},
        "Estonian": {"Estonia": {"id": 70, "code": "EST-EE"}},
        "Lithuanian": {"Lithuania": {"id": 71, "code": "LIT-LT"}},
        "Hebrew": {"Israel": {"id": 72, "code": "HEB-IL"}},
        "Zulu": {"South Africa": {"id": 75, "code": "ZUL-ZA"}},
        "Hindi": {"India": {"id": 76, "code": "HIN-IN"}},
        "Slovak": {"Slovakia": {"id": 78, "code": "SLK-SK"}},
        "Slovene": {"Slovenia": {"id": 79, "code": "SLV-SI"}},
        "Vietnamese": {
            "Vietnam": {"id": 81, "code": "VIE-VN"},
            "United States": {"id": 118, "code": "VIE-US"},
        },
        "Croatian": {"Croatia": {"id": 85, "code": "HRV-HR"}},
        "Flemish": {"Belgium": {"id": 88, "code": "NLD-BE"}},
        "Chinese Simplified": {
            "Singapore": {"id": 90, "code": "CHI-SG"},
            "Malaysia": {"id": 91, "code": "CHI-MY"},
            "United States": {"id": 142, "code": "CHI-US"},
            "Canada": {"id": 273, "code": "CHN-CA"},
        },
        "Serbian": {"Serbia": {"id": 92, "code": "SRP-RS"}},
        "Swahili": {
            "Kenya": {"id": 96, "code": "SWA-KE"},
            "Tanzania": {"id": 281, "code": "SWA-TZ"},
        },
        "Urdu": {
            "Pakistan": {"id": 121, "code": "URD-PK"},
            "India": {"id": 186, "code": "URD-IN"},
        },
        "Bengali": {
            "Bangladesh": {"id": 127, "code": "BEN-BD"},
            "India": {"id": 169, "code": "BEN-IN"},
        },
        "Kurdish": {"Iraq": {"id": 135, "code": "KUR-IQ"}},
        "Maltese": {"Malta": {"id": 160, "code": "MLT-MT"}},
        "Cantonese": {"China": {"id": 161, "code": "YUE-CN"}},
        "Assamese": {"India": {"id": 168, "code": "ASM-IN"}},
        "Dogri": {"India": {"id": 170, "code": "DOI-IN"}},
        "Gujrati": {"India": {"id": 171, "code": "GUJ-IN"}},
        "Kannada": {"India": {"id": 172, "code": "KAN-IN"}},
        "Kashmiri": {"India": {"id": 173, "code": "KAS-IN"}},
        "Konkani": {"India": {"id": 174, "code": "KOK-IN"}},
        "Maithili": {"India": {"id": 175, "code": "MAI-IN"}},
        "Manipuri": {"India": {"id": 176, "code": "MNI-IN"}},
        "Marathi": {"India": {"id": 177, "code": "MAR-IN"}},
        "Nepali": {"India": {"id": 178, "code": "NEP-IN"}},
        "Odia": {"India": {"id": 179, "code": "ORI-IN"}},
        "Punjabi": {
            "India": {"id": 180, "code": "PAN-IN"},
            "Pakistan": {"id": 320, "code": "PAN-PK"},
        },
        "Sanskrit": {"India": {"id": 181, "code": "SAN-IN"}},
        "Santali": {"India": {"id": 182, "code": "SAT-IN"}},
        "Sindhi": {"India": {"id": 183, "code": "SND-IN"}},
        "Tamil": {"India": {"id": 184, "code": "TAM-IN"}},
        "Telugu": {"India": {"id": 185, "code": "TEL-IN"}},
        "Amharic": {"Ethiopia": {"id": 198, "code": "AMH-ET"}},
        "Sesotho": {"Lesotho": {"id": 269, "code": "SOT-LS"}},
        "Afrikaans": {"South Africa": {"id": 272, "code": "AFR-ZA"}},
        "Burmese": {"Myanmar": {"id": 275, "code": "BUR-MM"}},
        "Kazakh": {"Kazakhstan": {"id": 276, "code": "KAZ-KZ"}},
        "Bokmal": {"Norway": {"id": 277, "code": "NOB-NO"}},
        "Sinhala": {"Sri Lanka": {"id": 279, "code": "SIN-LK"}},
    }

    return data[lang][country]["id"]
