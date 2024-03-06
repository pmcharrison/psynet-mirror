import random

from markupsafe import Markup

from psynet.api import expose_to_api
from psynet.modular_page import ModularPage, Prompt, TextControl
from psynet.participant import Participant


@expose_to_api("hello")
def hello(name):
    return f"Hello {name}!"


class RandomDigitInputPage(ModularPage):
    def __init__(self, label: str, time_estimate: float):
        self.n_digits = 7
        prompt = Markup(
            (
                """
            This data loads after the trial has started:
            <div id="digit"></div>
            <div id="name"></div>
            <div id="page_uuid"></div>
            <script>
            psynet.trial.onEvent("trialStart", function () {
                $.get("/api/random_digit_input", function(data) {
                    $("#digit").text(data.random_number.toString().padStart(7, "0"));
                });
                $.get("/api/hello?name=world", function(data) {
                    $("#name").text(data);
                });
                $.ajax({
                    url: "/api/page_uuid",
                    type: "POST",
                    data: JSON.stringify({participant_id: psynet.participantId}),
                    dataType: "json",
                    contentType: "application/json",
                    success: function(data) {
                    console.log(data);
                        $("#page_uuid").text(data.page_uuid);
                    }
                });
            });
            </script>
            """
            )
        )
        super().__init__(
            label,
            Prompt(prompt),
            control=TextControl(
                block_copy_paste=True,
            ),
            time_estimate=time_estimate,
        )

    @expose_to_api("random_digit_input")
    @staticmethod
    def random_number():
        return {"random_number": random.randint(0, 9999999)}

    # @expose_to_api("raises_exception_because_not_static")
    # def raises_exception_because_not_static(self):
    #     return "This should not be exposed"

    # # raises_exception_because_of_duplicate_endpoint
    # @expose_to_api("hello")
    # @staticmethod
    # def raises_exception_because_of_duplicate_endpoint(self):
    #     return "Endpoint already registered"

    @expose_to_api("page_uuid")
    @staticmethod
    def fetch_last_page_uuid(participant_id):
        participant = Participant.query.filter_by(id=participant_id).one()
        return {"page_uuid": participant.page_uuid}
