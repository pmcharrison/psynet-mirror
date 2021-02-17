##########################################################################################
# Imports
##########################################################################################

import psynet.experiment
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import ColorVocabularyTest
from psynet.timeline import Timeline

##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
        ColorVocabularyTest(),
        InfoPage(
            "You passed the color vocabulary task! Congratulations.", time_estimate=3
        ),
        SuccessfulEndPage(),
    )


extra_routes = Exp().extra_routes()
