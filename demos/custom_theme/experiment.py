import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


class Exp(psynet.experiment.Experiment):
    label = "Custom theme demo"

    timeline = Timeline(
        NoConsent(),
        InfoPage(
            "This demo illustrates custom theming.",
            time_estimate=5,
        ),
        SuccessfulEndPage(),
    )


# The recommended way to style a PsyNet experiment is by including a custom CSS file in the ``static`` directory
# and linking to it via the Experiment class, as follows:
Exp.css_links.append("static/theme.css")

# Alternatively, it is also possible to specify custom CSS directives directly in the Experiment class, as follows:
Exp.css.append(
    """
    /* Note: sometimes you might have to specify !important to ensure that pre-existing
    specifications (e.g. Bootstrap defaults) are overridden.  */

    body {
        background-color: powderblue !important;
    }

    /* Note: In this demo, the next button's border-color attribute is specified both in css_links and css.
    The former takes priority, so the following is therefore ignored: */

    #next-button {
        border-color: red;
    }
    """
)

# Note: The ``append`` method is a good way to add stylesheets because it allows for stylesheets to be inherited
# from the superclass.
