from markupsafe import Markup

import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import Page, Timeline


class CustomStylesheetPage(Page):
    def __init__(self):
        super().__init__(
            label="custom_stylesheet",
            template_fragment_path="templates/custom-stylesheet-page.html",
            save_answer=False,
            time_estimate=1,
            js_links=["/static/custom-style-page.js"],
            css_links=["/static/deferred-page-scripts.css"],
        )

    def get_bot_response(self, experiment, bot):
        return None


class Exp(psynet.experiment.Experiment):
    label = "In-place timeline transition lifecycle test"

    timeline = Timeline(
        InfoPage("First page", time_estimate=1),
        InfoPage(
            Markup(
                """
                <p>Deferred page script lifecycle page</p>
                <p
                    id="deferred-trial-construct-marker"
                    data-trial-construct-handler-ran="false"
                >
                    trialConstruct handler has not run
                </p>
                <p id="deferred-css-marker">Inline partial CSS marker</p>
                """
            ),
            time_estimate=1,
            js_links=["/static/deferred-script.js"],
            css_links=["/static/deferred-page-scripts.css"],
        ),
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
