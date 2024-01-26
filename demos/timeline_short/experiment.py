from dominate import tags

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline, switch


class Exp(psynet.experiment.Experiment):
    label = "Short timeline demo"

    config = {
        "min_accumulated_reward_for_abort": 0.2,
        "show_abort_button": True,
    }

    def with_recruiter(self, nickname):
        # We use this for patching the recruiter while testing the recruiter UI
        if self.var.has("with_recruiter"):
            patched_recruiter = self.var.with_recruiter
            return nickname == patched_recruiter

        return super().with_recruiter(nickname)

    timeline = Timeline(
        NoConsent(),
        switch(
            "switch",
            lambda participant: (participant.id - 1) % 6,
            {
                0: InfoPage(
                    content=tags.div(tags.h2("Participant 1")), time_estimate=101
                ),
                1: InfoPage(
                    content=tags.div(tags.h2("Participant 2")), time_estimate=101
                ),
                2: InfoPage(
                    content=tags.div(tags.h2("Participant 3")), time_estimate=101
                ),
                3: InfoPage(
                    content=tags.div(tags.h2("Participant 4")), time_estimate=101
                ),
                4: InfoPage(
                    content=tags.div(tags.h2("Participant 5")), time_estimate=101
                ),
                5: InfoPage(
                    content=tags.div(tags.h2("Participant 6")), time_estimate=101
                ),
            },
            fix_time_credit=False,
        ),
        SuccessfulEndPage(),
    )
