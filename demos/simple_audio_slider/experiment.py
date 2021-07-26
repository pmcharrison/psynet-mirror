import json

from flask import Markup, escape

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import AudioSliderControl, ModularPage
from psynet.page import DebugResponsePage, SuccessfulEndPage
from psynet.timeline import MediaSpec, Timeline, join


def print_dict(x, **kwargs):
    return (
        "<pre style='overflow: scroll; max-height: 200px'>"
        + json.dumps(x, indent=4)
        + "</pre>"
    )

    MediaSpec(
        audio={
            "batch": {
                "url": "/static/stimuli/bier.batch",
                "ids": [_id for _id, _ in kwargs["sound_locations"].items()],
                "type": "batch",
            }
        }
    )


def new_example(description, **kwargs):
    assert len(kwargs["sound_locations"]) == 472
    media = MediaSpec(
        audio={
            "batch": {
                "url": "/static/stimuli/bier.batch",
                "ids": [_id for _id, _ in kwargs["sound_locations"].items()],
                "type": "batch",
            }
        }
    )
    prompt = Markup(
        f"""
        {escape(description)}
        {print_dict(kwargs)}
        <p>
            Raw slider value is <strong id="slider_raw_value">NA</strong> <br>
            Output slider value is <strong id="slider_output_value">NA</strong>
            (phase = <strong id="phase">NA</strong>, random wrap = <strong id="random-wrap">NA</strong>)
        </p>
        <p>
            Just played <strong id="slider_audio">NA</strong>
        </p>
        <script>
            update_value = function() {{
                document.getElementById("slider_audio").innerHTML = slider.audio;
                document.getElementById("slider_raw_value").innerHTML = parseFloat(slider.getAttribute("raw_value")).toFixed(2);
                document.getElementById("slider_output_value").innerHTML = parseFloat(slider.getAttribute("output_value")).toFixed(2);
                document.getElementById("phase").innerHTML = parseFloat(slider.getAttribute("phase")).toFixed(2);
                document.getElementById("random-wrap").innerHTML = slider.getAttribute("random_wrap");
            }};
            psynet.trial.onEvent("trialConstruct", () => setInterval(update_value, 100));

        </script>
        """
    )
    time_estimate = kwargs.pop("time_estimate")

    return join(
        ModularPage(
            "slider_page",
            prompt,
            control=AudioSliderControl("slider_control", audio=media.audio, **kwargs),
            media=media,
            time_estimate=time_estimate,
        ),
        DebugResponsePage(),
    )


class CustomExp(psynet.experiment.Experiment):
    ids = [f"audio_{i}" for i in range(472)]

    timeline = Timeline(
        NoConsent(),
        new_example(
            """
            Simple example where no slider snapping is performed. There is one stimulus
            located at each integer position. The user must wait 2 seconds before
            they are allowed to submit their response.
            """,
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            snap_values=None,
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_time=2,
            time_estimate=5,
        ),
        new_example(
            """
            Same example with wrapping, i.e., then slider is wrapped twice so that there are no boundary jumps.
            """,
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            snap_values=None,
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_time=2,
            time_estimate=5,
            random_wrap=True,
        ),
        new_example(
            """
            Example with circular slider and wrapping.
            """,
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            snap_values=None,
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_time=2,
            time_estimate=5,
            random_wrap=True,
            input_type="circular_slider",
        ),
        new_example(
            """
            We come back to the simple example (without wrapping), but this
            with slider snapping to sound locations
            (as close as can be achieved given the underlying step size of the slider).
            """,
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            snap_values="sound_locations",
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_interactions=3,
            time_estimate=5,
        ),
        new_example(
            "Same example but with slider snapping to deciles.",
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            snap_values=11,
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_interactions=3,
            time_estimate=5,
        ),
        new_example(
            "Same example but where the slider can only be dragged through deciles.",
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            num_steps=11,
            snap_values=11,
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_interactions=3,
            time_estimate=5,
        ),
        new_example(
            "Same example but where the slider can only be dragged through sound locations.",
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            snap_values=None,
            num_steps="num_sounds",
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_interactions=3,
            time_estimate=5,
        ),
        new_example(
            "Same example with non-directional slider.",
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_interactions=1,
            time_estimate=5,
            directional=False,
        ),
        new_example(
            "Same example with slider reversed.",
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_interactions=1,
            time_estimate=5,
            reverse_scale=True,
        ),
        new_example(
            "Same example with reversed non-directional slider.",
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_interactions=1,
            time_estimate=5,
            reverse_scale=True,
            directional=False,
        ),
        new_example(
            "Without reversal, with non-integer sound locations.",
            sound_locations=dict(zip(ids, [100 + i / 3 for i in range(472)])),
            start_value=200,
            min_value=100,
            max_value=260,
            autoplay=True,
            minimal_interactions=1,
            time_estimate=5,
        ),
        new_example(
            "Without autoplay, without minimal interactions.",
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            snap_values=None,
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=False,
            minimal_interactions=0,
            time_estimate=5,
        ),
        SuccessfulEndPage(),
    )
