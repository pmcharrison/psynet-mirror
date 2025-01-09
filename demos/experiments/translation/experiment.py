from dominate import tags

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.utils import get_logger, get_translator, get_translator_with_context

logger = get_logger()

_ = get_translator()
_p = get_translator_with_context()


class Exp(psynet.experiment.Experiment):
    label = "Translation demo"

    # You could also set these in the config.txt file
    config = {
        "locale": "de",
        "supported_locales": ["en", "de", "nl"],
    }
    timeline = Timeline(
        NoConsent(),
        InfoPage(
            _p("welcome-page", "Welcome to the translation demo!"), time_estimate=2
        ),
        InfoPage(
            tags.span(
                tags.h2(
                    f"You have chosen to translate this experiment to {config.get('locale')}."
                ),
                tags.hr(),
                tags.p(
                    "Below you will see this text translated!",
                    tags.br(),
                    _("Below you will see this text translated!"),
                ),
                tags.hr(),
            ),
            time_estimate=5,
        ),
        InfoPage(
            tags.span(
                tags.h2(
                    "You can also change the translation during the experiment if you like. Try switching to another locale!"
                ),
                tags.hr(),
                tags.p(
                    "Below you will see this text translated!",
                    tags.br(),
                    _("Below you will see this text translated!"),
                ),
                tags.hr(),
            ),
            time_estimate=5,
        ),
        InfoPage(
            tags.span(
                tags.p(
                    "This is a use of an inline variable:",
                    _("My name is {NAME}.").format(NAME="Alice"),
                    _("My favorite food is {FOOD}.").format(FOOD="pizza"),
                    _("My least favorite food is {FOOD}.").format(FOOD="pizza"),
                ),
                tags.hr(),
            ),
            time_estimate=5,
        ),
        ModularPage(
            "modular_translation",
            prompt=_(
                "You can also translate text in push buttons or any kind of page!"
            ),
            control=PushButtonControl(
                [
                    _p("button", "Click"),
                    _p("button", "on"),
                    _p("button", "translation"),
                ],
                arrange_vertically=False,
            ),
            time_estimate=4,
        ),
        SuccessfulEndPage(),
    )
