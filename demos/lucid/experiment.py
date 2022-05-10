from flask import Markup

import psynet.experiment
import psynet.media
from psynet.consent import MainConsent
from psynet.demography.general import BasicDemography
from psynet.demography.gmsi import GMSI
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import AttentionTest, HeadphoneTest, LexTaleTest
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


##########################################################################################
# SETTINGS
##########################################################################################
INITIAL_RECRUITMENT_SIZE = 1

##########################################################################################
# EXPERIMENT
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        MainConsent(),
        InfoPage(
            Markup(
                """
                Welcome to the experiment! <br><br>
                In this experiment you will participate in various tests.
                """
            ),
            time_estimate=2,
        ),
        AttentionTest(fail_on=None),
        HeadphoneTest(performance_threshold=0),
        LexTaleTest(performance_threshold=0),
        GMSI(),
        BasicDemography(),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = INITIAL_RECRUITMENT_SIZE
