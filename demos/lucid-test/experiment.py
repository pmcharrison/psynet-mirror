from flask import Markup

import psynet.experiment
import psynet.media
from psynet.consent import MainConsent
from psynet.demography.general import BasicDemography
from psynet.demography.gmsi import GMSI
from psynet.lucid import LucidService
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.prescreen import AttentionTest, HeadphoneTest, LexTaleTest
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()


##########################################################################################
# SETTINGS
##########################################################################################
# TODO
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

    from dallinger.experiment import scheduled_task

    @scheduled_task("interval", minutes=0.1, max_instances=1)
    @staticmethod
    def check_pending_participant():
        import json

        import requests
        from dallinger.config import get_config

        from psynet.participant import Participant

        config = get_config()
        lucidservice = LucidService(
            api_key=config.get("lucid_api_key"),
            sha1_hashing_key=config.get("lucid_sha1_hashing_key"),
            sandbox=config.get("mode") != "live",
            recruitment_config=json.loads(config.get("lucid_recruitment_config")),
        )
        redirect_url = "https://samplicio.us/s/ClientCallBack.aspx?RIS=20&RID="
        for participant in Participant.query.all():
            if participant.progress == 0:
                lucidservice.log(f"Terminating participant {participant.id}")
                redirect_url += f"{participant.assignment_id}&hash={lucidservice.sha1_hash(redirect_url)}"
                lucidservice.log(f"Exit redirect: {redirect_url}")
                requests.get(redirect_url)
