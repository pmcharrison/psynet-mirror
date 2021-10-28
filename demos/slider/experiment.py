import json

from flask import Markup

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, SliderControl
from psynet.page import DebugResponsePage, SuccessfulEndPage
from psynet.timeline import Timeline, join


def print_dict(x):
    return "<pre>" + json.dumps(x, indent=4) + "</pre>"


def make_example(args):
    prompt = Markup(
        f"""
        Raw slider value is <strong id="slider-raw-value">NA</strong> <br>
        Output slider value is <strong id="slider-output-value">NA</strong>
        (phase = <strong id="phase">NA</strong>, random wrap = <strong id="random-wrap">NA</strong>)
        {print_dict(args)}
        <script>
            update_value = function() {{
                document.getElementById("slider-raw-value").innerHTML = parseFloat(slider.getAttribute("raw-value")).toFixed(2);
                document.getElementById("slider-output-value").innerHTML = parseFloat(slider.getAttribute("output-value")).toFixed(2);
                document.getElementById("phase").innerHTML = parseFloat(slider.getAttribute("phase")).toFixed(2);
                document.getElementById("random-wrap").innerHTML = slider.getAttribute("random-wrap");
            }}
            psynet.trial.onEvent("trialConstruct", () => setInterval(update_value, 100));
        </script>
        """
    )

    return join(
        ModularPage(
            "slider_page",
            prompt,
            control=SliderControl("slider_control", **args),
            time_estimate=5,
        ),
        DebugResponsePage(),
    )


example_1 = {
    "start_value": 15,
    "min_value": 10,
    "max_value": 20,
    "num_steps": 11,
    "snap_values": None,
    "minimal_interactions": 3,
    "random_wrap": False,
}

example_2 = {
    "start_value": 15,
    "min_value": 10,
    "max_value": 20,
    "num_steps": 11,
    "snap_values": None,
    "minimal_interactions": 3,
    "random_wrap": True,
}
# TODO reverse direction

example_3 = {
    "start_value": 10,
    "min_value": 5,
    "max_value": 15,
    "num_steps": 100,
    "snap_values": None,
    "minimal_interactions": 3,
    "input_type": "circular_slider",
    "random_wrap": False,
}

example_4 = {
    "start_value": 10,
    "min_value": 5,
    "max_value": 15,
    "num_steps": 100,
    "snap_values": None,
    "minimal_interactions": 3,
    "input_type": "circular_slider",
    "random_wrap": True,
}

example_5 = {
    "start_value": 0.5,
    "min_value": 0.1,
    "max_value": 0.9,
    "num_steps": 48,
    "snap_values": None,
    "minimal_interactions": 5,
    "input_type": "circular_slider",
    "random_wrap": True,
}

example_6 = {
    "start_value": 15,
    "min_value": 10,
    "max_value": 20,
    "num_steps": 1000,
    "snap_values": [10, 11, 12, 13, 14, 15, 20],
    "minimal_interactions": 0,
}


class CustomExp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        make_example(example_1),
        make_example(example_2),
        make_example(example_3),
        make_example(example_4),
        make_example(example_5),
        make_example(example_6),
        SuccessfulEndPage(),
    )
