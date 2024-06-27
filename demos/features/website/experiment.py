from dominate import tags

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.timeline import GoTo, Timeline, join
from psynet.utils import get_logger

logger = get_logger()


def content_page(label, content, navigation_options):
    return join(
        ModularPage(
            label,
            tags.span(
                tags.p(content),
                tags.p(tags.em("For more content, click one of the buttons below:")),
            ),
            PushButtonControl(navigation_options),
        ),
        GoTo(lambda participant: participant.answer),
    )


class Exp(psynet.experiment.Experiment):
    label = "Simple website demo"

    links = ["welcome", "fish", "dog", "bird"]

    timeline = Timeline(
        main=join(
            NoConsent(),
            GoTo("welcome"),
        ),
        welcome=content_page("welcome", "Welcome to my website!", links),
        fish=content_page("fish", "My favorite fish is the goldfish", links),
        dog=content_page("dog", "My favorite dog is the golden retriever", links),
        bird=content_page("bird", "My favorite bird is the robin", links),
    )

    def run_bot(self, bot):
        assert bot.get_current_page().label == "Welcome"

        bot.submit_response("Bird")
        assert bot.get_current_page().label == "Bird"

        bot.submit_response("Fish")
        assert bot.get_current_page().label == "Fish"

        bot.submit_response("Dog")
        assert bot.get_current_page().label == "Dog"

        bot.submit_response("Welcome")
        assert bot.get_current_page().label == "Welcome"
