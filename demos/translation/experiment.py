from os.path import abspath

from flask import Markup

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import PageMaker, Timeline, join
from psynet.utils import get_logger, get_translator

logger = get_logger()

supported_locales = ["en", "de", "nl"]
reference_language = "en"


def get_timeline_in_locale(locale):
    _, _p, _np = get_translator(
        locale=locale, module="experiment", localedir=abspath("locales")
    )
    return join(
        InfoPage(
            _p("welcome-page", "Welcome to the translation demo!"), time_estimate=2
        ),
        InfoPage(
            Markup(
                "<h2>"
                + f"You have chosen to translate this experiment from {reference_language} to {locale}"
                + "</h2>"
                + "<hr>"
                + "<p>"
                + "Below you will see this text translated! <br>"
                + _("Below you will see this text translated!")
                + "</p>"
                + "<hr>"
            ),
            time_estimate=5,
        ),
        InfoPage(
            Markup(
                "<h2>"
                + "You can also change the translation during the experiment if you like. Try switching to another language!"
                + "</h2>"
                + "<hr>"
                + "<p>"
                + "Below you will see this text translated! <br>"
                + _("Below you will see this text translated!")
                + "</p>"
                + "<hr>"
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
    )


timeline_by_locale = {
    locale: get_timeline_in_locale(locale) for locale in supported_locales
}
reference_timeline = timeline_by_locale[reference_language]

timeline_time_estimate = 0
for elt in reference_timeline:
    if hasattr(elt, "time_estimate"):
        timeline_time_estimate += elt.time_estimate


class Exp(psynet.experiment.Experiment):
    label = "Translation demo"

    config = {
        "language": "de",
        "supported_locales": supported_locales,
        "allow_switching_locale": True,
    }
    timeline = Timeline(
        NoConsent(),
        PageMaker(
            lambda participant, experiment: timeline_by_locale[
                participant.get_locale(experiment)
            ],
            time_estimate=timeline_time_estimate,
        ),
        SuccessfulEndPage(),
    )
