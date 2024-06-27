from dominate import tags

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.timeline import GoTo, Timeline, join
from psynet.utils import get_logger

logger = get_logger()


def content_page(label, content, links):
    return join(
        ModularPage(
            label,
            tags.span(
                tags.p(content),
                tags.p(tags.em("Click below to visit another page.")),
            ),
            PushButtonControl(
                choices=links,
                labels=[choice.capitalize() for choice in links],
                arrange_vertically=False,
            ),
            # We have set the time_estimate to 0.0 to disable time-related payments.
            # An alternative would be to set wage_per_hour = 0.0 in the experiment config.
            time_estimate=0.0,
        ),
        GoTo(lambda participant: participant.answer),
    )


class Exp(psynet.experiment.Experiment):
    label = "Simple website demo"

    config = {
        "show_reward": False,
        "show_progress_bar": False,
    }

    links = ["welcome", "fish", "dogs", "birds"]

    timeline = Timeline(
        main=join(
            NoConsent(),
            GoTo("welcome"),
        ),
        welcome=content_page("welcome", "Welcome to my website!", links),
        fish=content_page("fish", "My favorite fish is the goldfish.", links),
        dogs=content_page("dogs", "My favorite dog is the golden retriever.", links),
        birds=content_page("birds", "My favorite bird is the robin.", links),
    )

    def run_bot(self, bot):
        assert bot.get_current_page().label == "welcome"

        bot.submit_response("birds")
        assert bot.get_current_page().label == "birds"

        bot.submit_response("fish")
        assert bot.get_current_page().label == "fish"

        bot.submit_response("dogs")
        assert bot.get_current_page().label == "dogs"

        bot.submit_response("welcome")
        assert bot.get_current_page().label == "welcome"
