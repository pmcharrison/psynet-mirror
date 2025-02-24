from markupsafe import Markup

import psynet.experiment
import psynet.media
from psynet.consent import LucidConsent
from psynet.demography.general import BasicDemography
from psynet.demography.gmsi import GMSI
from psynet.page import InfoPage
from psynet.prescreen import AttentionTest, HugginsHeadphoneTest, LexTaleTest
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


##########################################################################################
# SETTINGS
##########################################################################################
INITIAL_RECRUITMENT_SIZE = 1


class Exp(psynet.experiment.Experiment):
    label = "LUCID demo"

    timeline = Timeline(
        LucidConsent(),
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
        HugginsHeadphoneTest(performance_threshold=0),
        LexTaleTest(performance_threshold=0),
        GMSI(),
        BasicDemography(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = INITIAL_RECRUITMENT_SIZE
