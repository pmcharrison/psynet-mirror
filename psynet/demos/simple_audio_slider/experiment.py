import psynet.experiment
from psynet.timeline import (
    Timeline
)
from psynet.page import (
    SliderAudioPage,
    SuccessfulEndPage
)


class CustomExp(psynet.experiment.Experiment):
    numbers = [i + 1 for i in range(472)]
    IDs = [str(i) for i in numbers]
    media = {
        "audio": {
            'batch': {
                'url': '/static/stimuli/bier.batch',
                'ids': IDs,
                'type': 'batch'
            }
        }
    }

    timeline = Timeline(
        SliderAudioPage(
            label="example_slider_page",
            prompt="Which beer do you like most?",
            sound_locations=dict(zip(IDs, numbers)),
            start_value=50,
            min_value=min(numbers),
            max_value=max(numbers),
            allowed_values=numbers,
            autoplay=True,
            media=media,
            time_estimate=10
        ),

        SuccessfulEndPage()
    )


extra_routes = CustomExp().extra_routes()
