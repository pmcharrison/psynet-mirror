from dominate import tags

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import SuccessfulEndPage
from psynet.timeline import CodeBlock, Timeline, join
from psynet.utils import get_logger

logger = get_logger()


all_content = {
    "Welcome": "Welcome to my website!",
    "Fish": "My favorite kind of fish is the goldfish.",
    "Dog": "My favourite kind of dog is the golden retriever.",
    "Bird": "My favourite kind of bird is the robin.",
}


def content_page(label, content, navigation_options):
    return join(
        ModularPage(
            label,
            tags.span(
                tags.p(content),
                tags.p("For more content, click one of the buttons below:"),
            ),
            PushButtonControl(navigation_options),
        ),
        CodeBlock(lambda participant: participant.go_to(participant.answer)),
    )


class Exp(psynet.experiment.Experiment):
    label = "Simple website demo"

    timeline = Timeline(
        NoConsent(),
        CodeBlock(lambda participant: participant.go_to("Welcome")),
        SuccessfulEndPage(),
    )

    def get_logic(self):
        return {
            **super().get_logic(),
            **{
                label: content_page(
                    label, content, navigation_options=all_content.keys()
                )
                for label, content in all_content.items()
            },
        }

    def run_bot(self, bot):
        assert bot.get_current_page().label == "Welcome"

        bot.submit_response("Bird")  # submit_response can be a wrapper for take_page
        assert bot.get_current_page().label == "Bird"

        bot.submit_response("Fish")
        assert bot.get_current_page().label == "Fish"

        bot.submit_response("Dog")
        assert bot.get_current_page().label == "Dog"

        bot.submit_response("Welcome")
        assert bot.get_current_page().label == "Welcome"
