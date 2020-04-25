import psynet.experiment
from psynet.timeline import (
    Timeline
)
from psynet.timeline import PageMaker, join
from psynet.page import (
    AudioSliderPage,
    InfoPage,
    DebugResponsePage,
    SuccessfulEndPage
)

import rpdb
import json
from flask import Markup, escape

def print_dict(x):
    return "<pre style='overflow: scroll; max-height: 200px'>" + json.dumps(x, indent=4) + "</pre>"

def new_example(description, **kwargs):
    assert len(kwargs["sound_locations"]) == 472
    media = {
        "audio": {
            'batch': {
                'url': '/static/stimuli/bier.batch',
                'ids': [_id for _id, _ in kwargs["sound_locations"].items()],
                'type': 'batch'
            }
        }
    }
    prompt = Markup(f"""
        {escape(description)}
        {print_dict(kwargs)}
        <p>
            Slider value is <strong id="slider_value">NA</strong>
        </p>
        <p>
            Just played <strong id="slider_audio">NA</strong>
        </p>
        <script>
            update_value = function() {{
                document.getElementById("slider_value").innerHTML = slider.value;
                document.getElementById("slider_audio").innerHTML = slider.audio;
            }}
            setInterval(update_value, 100);
        </script>
        """)
    return join(
        AudioSliderPage(
            label="slider_page",
            prompt=prompt,
            media=media,
            **kwargs
        ),
        DebugResponsePage()
    )

class CustomExp(psynet.experiment.Experiment):
    ids = [f'audio_{i}' for i in range(472)]

    timeline = Timeline(
        new_example(
            """
            Simple example where no slider snapping is performed. There is one stimulus
            located at each integer position.
            """,
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            snap_values=None,
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_interactions=3,
            time_estimate=5
        ),
        new_example(
            """
            Same example but with slider snapping to sound locations
            (as close as can be achieved given the underlying step size of the slider).
            """,
            sound_locations=dict(zip(ids, [i for i in range(472)])),
            snap_values="sound_locations",
            start_value=200,
            min_value=0,
            max_value=471,
            autoplay=True,
            minimal_interactions=3,
            time_estimate=5
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
            time_estimate=5
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
            time_estimate=5
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
            time_estimate=5
        ),
        new_example(
            "Same example but with slider reversed.",
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
            "Without reversal, with non-integer sound locations.",
            sound_locations=dict(zip(ids, [100 + i / 3 for i in range(472)])),
            start_value=200,
            min_value=100,
            max_value=260,
            autoplay=True,
            minimal_interactions=1,
            time_estimate=5
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
            time_estimate=5
        ),
        SuccessfulEndPage()
    )

extra_routes = CustomExp().extra_routes()
