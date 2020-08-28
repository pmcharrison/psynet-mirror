# This demo contains a modified, extended consent form.
# At some point we will get rid of this and make it part of an external library.

import psynet.experiment
from psynet.timeline import (
    Timeline,
)
from psynet.page import (
    InfoPage,
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
        InfoPage("That's the end of the demo.", time_estimate=5),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
