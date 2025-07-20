def get_mock_prolific_recruiter(study_id):
    return {
        "recruiter": "mockprolific",
        "prolific_recruitment_config": {"study_id": study_id},
    }


def get_mock_lucid_recruiter(survey_sid, survey_number):
    return {
        "show_reward": False,
        "recruiter": "mocklucid",
        "lucid_recruitment_config": {
            "survey_sid": survey_sid,
            "survey_number": survey_number,
            "termination_time_in_s": 30 * 60,
            "inactivity_timeout_in_s": 120,
            "no_focus_timeout_in_s": 60,
            "aggressive_no_focus_timeout_in_s": 3,
            "initial_response_within_s": 180,
            "survey": {
                "CountryLanguageID": "9",
                "FulcrumExchangeAllocation": 0,
                "FulcrumExchangeHedgeAccess": True,
                "IndustryID": 30,
                "StudyTypeID": 1,
                "UniqueIPAddress": True,
                "UniquePID": True,
                "BidIncidence": 66,
                "CollectsPII": False,
            },
            "qualifications": [],
            "country": "US",
            "language": "ENG",
        },
    }
