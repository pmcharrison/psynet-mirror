import psynet.experiment
from psynet.page import CodeBlock, InfoPage, NAFCPage, SuccessfulEndPage
from psynet.timeline import Timeline, multi_page_maker
from psynet.utils import get_logger

logger = get_logger()


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
        NAFCPage(
            "choose_number",
            "What number would you like to count to?",
            ["1", "2", "3", "4", "5"],
            time_estimate=5,
        ),
        CodeBlock(
            lambda participant: participant.var.set(
                "num_pages", int(participant.answer)
            )
        ),
        multi_page_maker(
            "example_multi_page_maker",
            lambda participant: [
                InfoPage(
                    f"Page {i + 1}/{participant.var.num_pages}", time_estimate=None
                )
                for i in range(participant.var.num_pages)
            ],
            total_time_estimate=5,
            expected_num_pages=3,
        ),
        SuccessfulEndPage(),
    )


extra_routes = Exp().extra_routes()
