# pylint: disable=unused-import,abstract-method

##########################################################################################
# Imports
##########################################################################################

import logging

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, SurveyJSControl
from psynet.page import DebugResponsePage, SuccessfulEndPage
from psynet.timeline import Timeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


class Exp(psynet.experiment.Experiment):
    label = "SurveyJS demo"
    initial_recruitment_size = 1

    timeline = Timeline(
        NoConsent(),
        ModularPage(
            "example_1",
            "Here's a simple SurveyJS example.",
            SurveyJSControl(
                {
                    "logoPosition": "right",
                    "pages": [
                        {
                            "name": "page1",
                            "elements": [
                                {
                                    "type": "text",
                                    "name": "name",
                                    "title": "Please enter your name",
                                },
                                {
                                    "type": "dropdown",
                                    "name": "gender",
                                    "title": "Select your gender",
                                    "choices": [
                                        {"value": "male", "text": "Male"},
                                        {"value": "female", "text": "Female"},
                                        {"value": "non_binary", "text": "Non-binary"},
                                        {
                                            "value": "prefer_not_to_say",
                                            "text": "Prefer not to say",
                                        },
                                    ],
                                    "showOtherItem": True,
                                    "otherText": "Other (please specify)",
                                },
                                {
                                    "type": "ranking",
                                    "name": "animal_preferences",
                                    "title": "Please rank these in order of preference",
                                    "choices": [
                                        {"value": "cats", "text": "Cats"},
                                        {"value": "dogs", "text": "Dogs"},
                                        {"value": "goldfish", "text": "Goldfish"},
                                    ],
                                },
                                {
                                    "type": "rating",
                                    "name": "weather",
                                    "title": "Please rate your weather today.",
                                    "rateValues": [
                                        {"value": "1", "text": "1"},
                                        {"value": "2", "text": "2"},
                                        {"value": "3", "text": "3"},
                                        {"value": "4", "text": "4"},
                                        {"value": "5", "text": "5"},
                                    ],
                                    "minRateDescription": "Awful",
                                    "maxRateDescription": "Amazing",
                                },
                            ],
                        },
                        {
                            "name": "page2",
                            "elements": [
                                {
                                    "type": "text",
                                    "name": "final_question",
                                    "title": "Here's a final question before you submit the questionnaire...",
                                }
                            ],
                        },
                    ],
                },
            ),
            time_estimate=5,
        ),
        DebugResponsePage(),
        SuccessfulEndPage(),
    )
