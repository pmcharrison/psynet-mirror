from markupsafe import Markup

import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import Page, Timeline

CUSTOM_STYLE_PAGE_TEMPLATE = """
{% extends "timeline-page.html" %}

{% block stylesheets %}
    {{ super() }}
    <style>
        #custom-stylesheet-marker {
            color: rgb(12, 34, 56);
            border-left: 7px solid rgb(78, 90, 12);
            padding-left: 13px;
        }
    </style>
{% endblock %}

{% block main_body %}
    <p id="custom-stylesheet-marker">Styled custom template page</p>
    <button id="next-button" type="button" class="btn btn-primary submit">Next</button>
    <script>
        psynet.trial.onEvent("trialConstruct", function () {
            var button = document.getElementById("next-button");
            psynet.addPageEventListener(button, "click", function () {
                psynet.submitResponse();
            });
        });
    </script>
{% endblock %}
"""


class CustomStylesheetPage(Page):
    def __init__(self):
        super().__init__(
            label="custom_stylesheet",
            template_str=CUSTOM_STYLE_PAGE_TEMPLATE,
            save_answer=False,
            time_estimate=1,
        )

    def get_bot_response(self, experiment, bot):
        return None


class Exp(psynet.experiment.Experiment):
    label = "Custom template stylesheet lifecycle test"

    timeline = Timeline(
        InfoPage("First page", time_estimate=1),
        CustomStylesheetPage(),
        InfoPage(
            Markup(
                """
                <p>Cleanup page</p>
                <p id="custom-stylesheet-marker">Unstyled cleanup marker</p>
                """
            ),
            time_estimate=1,
        ),
    )
