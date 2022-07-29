import gettext
import os

from flask import Markup

import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.utils import get_language, get_logger

from .parts import textLib

logger = get_logger()

# Load language parameter from config.txt file
LANGUAGE = get_language()

# Load translation files
domain_name = os.path.basename(__file__)[
    :-3
]  # strip ".py" extension, this returns the name of the file e.g. "experiment"
lang = gettext.translation(domain_name, localedir="locale", languages=[LANGUAGE])
lang.install()  # install _() function

###################
# Translation files
# 1) .pot are the template files that just contain the strings for
# translation that are found in a python module through the _() function.
# 2) .po are based on .pot files and contain the actuall translations.
# 3) .mo files are created from the .po files and are used at runtime
# to load the translation.
# We refer you to Psynet Learning to see how you can create these files.


class Exp(psynet.experiment.Experiment):
    label = "Translation demo"

    timeline = Timeline(
        NoConsent(),
        InfoPage(_("Welcome to the translation demo!"), time_estimate=2),
        InfoPage(
            Markup(
                "<h2>"
                + f"You have chosen to translate this experiment from English (en) to {LANGUAGE}"
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
                + "Translation imported from another file"
                + "</h2>"
                + "<hr>"
                + "<p>"
                + """Sometimes you might want to spread your experiment implementation over multiple files.
                        You can just translate every file on its own, so that each file has a corresponding .po and .mo file.
                        These files should also be in the locale directory of the specified language!
                    """
                "Here we see a text line from another file in the experiment directory:<br>"
                + "</p>"
                + "<p>"
                + textLib["info_translation_1"]
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
                [_("Click"), _("on"), _("translation")],
                arrange_vertically=False,
            ),
            time_estimate=4,
        ),
        SuccessfulEndPage(),
    )
