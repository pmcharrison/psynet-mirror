from markupsafe import Markup

import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import Timeline


DEFERRED_SCRIPT = """
window.__psynetDeferredPageScript = {
    scriptExecuted: true,
    trialConstructHandlerRan: false,
};

psynet.trial.onEvent("trialConstruct", function () {
    window.__psynetDeferredPageScript.trialConstructHandlerRan = true;
    const marker = document.getElementById("deferred-trial-construct-marker");
    if (marker) {
        marker.dataset.trialConstructHandlerRan = "true";
        marker.textContent = "trialConstruct handler ran";
    }
});
"""


class Exp(psynet.experiment.Experiment):
    label = "Deferred page script lifecycle test"

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
                """
            ),
            time_estimate=1,
            scripts=[DEFERRED_SCRIPT],
        ),
    )
