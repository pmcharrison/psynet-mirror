import json

from dominate import tags

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, JsPsychPage, SuccessfulEndPage
from psynet.timeline import PageMaker, Timeline


def display_answer(answer):
    prompt = tags.div()
    with prompt:
        tags.p("The jsPsych page generated the following output: ")
        tags.pre(json.dumps(answer, indent=4))
    return InfoPage(prompt)


class Exp(psynet.experiment.Experiment):
    label = "jsPsych demo"

    timeline = Timeline(
        NoConsent(),
        JsPsychPage(
            "reaction_time_task",
            timeline="templates/reaction-time-task.html",
            time_estimate=25,
            js_vars={
                "trial_durations": [250, 500, 750, 1000, 1250, 1500, 1750, 2000],
                "welcome_message": "Welcome to the experiment. Press any key to begin.",
            },
            js_links=[
                "static/jspsych/jspsych.js",
                "static/jspsych/plugin-html-keyboard-response.js",
                "static/jspsych/plugin-image-keyboard-response.js",
                "static/jspsych/plugin-preload.js",
            ],
            css_links=["static/jspsych/jspsych.css"],
            bot_response=None,
        ),
        PageMaker(
            lambda participant: display_answer(participant.answer), time_estimate=5
        ),
        SuccessfulEndPage(),
    )
