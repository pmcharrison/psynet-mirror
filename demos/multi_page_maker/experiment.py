import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import NumberControl, PushButtonControl
from psynet.page import CodeBlock, InfoPage, ModularPage, Prompt, SuccessfulEndPage
from psynet.timeline import Timeline, multi_page_maker, while_loop
from psynet.utils import get_logger

logger = get_logger()


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        NoConsent(),
        # ModularPage(
        #     "choose_number",
        #     Prompt("What number would you like to count to?"),
        #     control=PushButtonControl(
        #         ["1", "2", "3", "4", "5"], arrange_vertically=False
        #     ),
        #     time_estimate=0,
        # ),
        # CodeBlock(
        #     lambda participant: participant.var.set(
        #         "num_pages", int(participant.answer)
        #     )
        # ),
        # multi_page_maker(
        #     "example_multi_page_maker",
        #     lambda participant: [
        #         InfoPage(f"Page {i + 1}/{participant.var.num_pages}", time_estimate=1)
        #         for i in range(participant.var.num_pages)
        #     ],
        #     total_time_estimate=3,
        #     expected_num_pages=3,
        # ),
        # InfoPage(
        #     "We'll now test a multi-page maker that contains a code block.",
        #     time_estimate=5,
        # ),
        # multi_page_maker(
        #     "code_block_in_multi_page_maker",
        #     lambda participant: [
        #         ModularPage(
        #             "number_input",
        #             "Give me a number to multiply by 2...",
        #             NumberControl(),
        #             time_estimate=5,
        #             save_answer="number_to_multiply",
        #         ),
        #         CodeBlock(
        #             lambda participant: participant.var.set(
        #                 "multiplied_number",
        #                 int(participant.var.get("number_to_multiply")) * 2,
        #             )
        #         ),
        #         InfoPage(
        #             # Note that we have to use default values here so that we don't get an error
        #             # when the function is evaluated before number_input and multiplied_number
        #             # have been set.
        #             f"{participant.var.get('number_to_multiply', has_default=True, default=0.0)} * 2 = "
        #             f"{participant.var.get('multiplied_number', has_default=True, default=0.0)}",
        #             time_estimate=5,
        #         ),
        #     ],
        #     expected_num_pages=2,
        #     total_time_estimate=10,
        # ),
        InfoPage(
            "We'll now test a multi-page maker that contains a while loop.",
            time_estimate=5,
        ),
        CodeBlock(
            lambda participant: participant.var.set("while_loop_counter", 0)
        ),
        multi_page_maker(
            "while_loop_in_multi_page_maker",
            lambda participant: while_loop(
                "while_loop",
                lambda participant: participant.var.while_loop_counter < 2,
                [
                    CodeBlock(participant.var.inc("while_loop_counter")),
                    InfoPage(
                        f"You are on iteration {[participant.var.while_loop_counter]}/3.",
                        time_estimate=5,
                    )
                ],
                expected_repetitions=3,
            ),
            expected_num_pages=3,
            total_time_estimate=5*3,
        ),
        SuccessfulEndPage(),
    )
