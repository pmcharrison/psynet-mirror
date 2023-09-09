import psynet.experiment
from psynet.consent import NoConsent
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import SuccessfulEndPage
from psynet.timeline import Response, Timeline
from psynet.utils import get_logger

logger = get_logger()


class NoGreenControl(PushButtonControl):
    def validate(self, response, **kwargs):
        if response.answer == "green":
            return "Green is an invalid answer!"


class Exp(psynet.experiment.Experiment):
    label = "Validation demo"

    timeline = Timeline(
        NoConsent(),
        ModularPage(
            "colors_no_blue",
            prompt="This page has a custom validation function that prohibits the answer 'blue'.",
            control=PushButtonControl(
                ["red", "green", "blue"],
                ["Red", "Green", "Blue"],
            ),
            time_estimate=5,
            validate=lambda answer: "Blue is an invalid answer!"
            if answer == "blue"
            else None,
            bot_response="blue",
        ),
        ModularPage(
            "colors_no_green",
            prompt="This control has a custom validation method that prohibits the answer 'green'.",
            control=NoGreenControl(
                ["red", "green", "blue"],
                ["Red", "Green", "Blue"],
            ),
            time_estimate=5,
        ),
        SuccessfulEndPage(),
    )

    def run_bot(self, bot):
        page = bot.get_current_page()
        assert (
            page.prompt.text
            == "This page has a custom validation function that prohibits the answer 'blue'."
        )

        bot.take_page(page, response="blue")
        response = (
            Response.query.filter_by(participant_id=bot.id)
            .order_by(Response.creation_time.desc())
            .first()
        )
        assert response.successful_validation is not None
        assert not response.successful_validation
        page = bot.get_current_page()
        assert (
            page.prompt.text
            == "This page has a custom validation function that prohibits the answer 'blue'."
        )

        bot.take_page(page, response="green")
        response = (
            Response.query.filter_by(participant_id=bot.id)
            .order_by(Response.creation_time.desc())
            .first()
        )
        assert response.successful_validation

        page = bot.get_current_page()
        assert (
            page.prompt.text
            == "This control has a custom validation method that prohibits the answer 'green'."
        )
        bot.take_page(page, response="green")
        response = (
            Response.query.filter_by(participant_id=bot.id)
            .order_by(Response.creation_time.desc())
            .first()
        )
        assert response.successful_validation is not None
        assert not response.successful_validation
        page = bot.get_current_page()
        assert (
            page.prompt.text
            == "This control has a custom validation method that prohibits the answer 'green'."
        )

        bot.take_page(page, response="red")
        response = (
            Response.query.filter_by(participant_id=bot.id)
            .order_by(Response.creation_time.desc())
            .first()
        )
        assert response.successful_validation

        bot.run_to_completion()
