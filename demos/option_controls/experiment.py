import psynet.experiment
from psynet.timeline import (
    Timeline,
    Module,
)
from psynet.modular_page import (
    AudioPrompt,
    CheckboxControl,
    DropdownControl,
    ModularPage,
    PushButtonControl,
    RadioButtonControl,
)
from psynet.page import (
    SuccessfulEndPage
)

from psynet.utils import get_logger
logger = get_logger()

from datetime import datetime


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        ModularPage(
            "response",
            prompt="This is an example of a push button page with vertically arranged buttons.",
            control=PushButtonControl(
                ["red", "green", "blue"],
                ["Red", "Green", "Blue"],
            ),
            time_estimate=5
        ),
        ModularPage(
            "response",
            prompt="This is an example of a push button page with horizontally arranged buttons.",
            control=PushButtonControl(
                ["red", "green", "blue"],
                ["Red", "Green", "Blue"],
                arrange_vertically=False,
            ),
            time_estimate=5
        ),
        ModularPage(
            "response",
            prompt="This is an example of a dropdown page.",
            control=DropdownControl(
                ["cirrus", "stratus", "cumulus"],
                ["Cirrus", "Stratus", "Cumulus"],
                name="clouds",
            ),
            time_estimate=5
        ),
        ModularPage(
            "response",
            prompt="This is an example of a checkbox page with vertically arranged checkboxes.",
            control=CheckboxControl(
                ["sneakers", "sandals", "clogs"],
                ["Sneakers", "Sandals", "Clogs"],
                name="shoes",
            ),
            time_estimate=5
        ),
        ModularPage(
            "response",
            prompt="This is an example of a checkbox page with horizontally arranged checkboxes and forced selection.",
            control=CheckboxControl(
                ["sneakers", "sandals", "clogs"],
                ["Sneakers", "Sandals", "Clogs"],
                name="shoes",
                arrange_vertically=False,
                force_selection=True,
            ),
            time_estimate=5
        ),
        ModularPage(
            "response",
            prompt="This is an example of a radiobutton page with vertically arranged radiobuttons.",
            control=RadioButtonControl(
                ["maple", "cottonwood", "alder"],
                ["Maple", "Cottonwood", "Alder"],
                name="trees",
                arrange_vertically=True,
            ),
            time_estimate=5
        ),
        ModularPage(
            "response",
            prompt="This is an example of a radiobutton page with horizontally arranged radiobuttons without forcing an answer.",
            control=RadioButtonControl(
                ["maple", "cottonwood", "alder"],
                ["Maple", "Cottonwood", "Alder"],
                name="trees",
                arrange_vertically=False,
                force_selection=False,
            ),
            time_estimate=5
        ),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
