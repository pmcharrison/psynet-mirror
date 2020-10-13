from uuid import uuid4

import psynet.experiment
from psynet.page import (
    InfoPage,
    SuccessfulEndPage,
    UnityPage,
)
from psynet.timeline import Timeline


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class UnityExperiment(psynet.experiment.Experiment):
    session_id = str(uuid4())
    timeline = Timeline(
        UnityPage(
            title="Unity experiment demo - Session 1",
            game_container_width="960px",
            game_container_height="600px",
            contents={"aaa": "1st page", "bbb": "1st page",},
            resources="/static",
            time_estimate=5,
            session_id = session_id,
        ),
        UnityPage(
            title="Unity experiment demo - Session 1",
            game_container_width="960px",
            game_container_height="600px",
            contents={"iii": "2nd page", "jjj": "2nd page",},
            resources="/static",
            time_estimate=5,
            session_id = session_id,
        ),
        UnityPage(
            title="Unity experiment demo - Session 2",
            game_container_width="360px",
            game_container_height="200px",
            contents={"xxx": "3rd page", "yyy": "3rd page",},
            resources="/static",
            time_estimate=5,
            session_id = str(uuid4()),
        ),
        SuccessfulEndPage()
    )

extra_routes = UnityExperiment().extra_routes()
