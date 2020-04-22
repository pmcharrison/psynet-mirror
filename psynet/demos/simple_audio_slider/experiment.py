import psynet.experiment
from psynet.timeline import (
    Timeline
)
from psynet.timeline import PageMaker, MediaSpec
from psynet.page import (
    AudioSliderPage,
    InfoPage,
    DebugResponsePage,
    SuccessfulEndPage
)

import rpdb


class CustomExp(psynet.experiment.Experiment):
    numbers=[i + 1 for i in range(472)]
    IDs=['MY_SUPER_CUSTOM_ID' + str(i) for i in numbers]
    media=MediaSpec(
        audio={
            'batch': {
                'url': '/static/stimuli/bier.batch',
                'ids': IDs,
                'type': 'batch'
            }
        }
    )

    timeline = Timeline(
        AudioSliderPage(
            label="example_slider_page",
            prompt="Which beer do you like most? Note: you will have to try 3 slider positions before continuing.",
            sound_locations=dict(zip(IDs, numbers)),
            start_value=50,
            min_value=min(numbers),
            max_value=max(numbers),
            allowed_values=numbers,
            autoplay=True,
            media=media,
            time_estimate=10,
            minimal_interactions=3
        ),
        DebugResponsePage(),
        AudioSliderPage(
            label="example_slider_page_reverse",
            prompt="Which beer do you like most? Note: the direction of this scale is reversed from the previous question.",
            sound_locations=dict(zip(IDs, numbers)),
            start_value=50,
            min_value=min(numbers),
            max_value=max(numbers),
            allowed_values=numbers,
            autoplay=True,
            media=media,
            time_estimate=10,
            minimal_interactions=3,
            reverse_scale=True
        ),
        DebugResponsePage(),
        SuccessfulEndPage()
    )


extra_routes = CustomExp().extra_routes()
