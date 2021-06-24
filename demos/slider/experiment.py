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
    Slider value is <strong id="slider_value">NA</strong>
    {print_dict(args)}
    <script>
        update_value = function() {{
            document.getElementById("slider_value").innerHTML = slider.value;
        }}
        psynet.response.register_on_ready_routine(function() {{
            setInterval(update_value, 100);
        }});
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
    "snap_values": 11,
    "minimal_interactions": 3,
}

example_2 = {
    "start_value": 15,
    "min_value": 10,
    "max_value": 20,
    "num_steps": 1000,
    "snap_values": 11,
    "minimal_interactions": 0,
}

example_3 = {
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
        SuccessfulEndPage(),
    )
