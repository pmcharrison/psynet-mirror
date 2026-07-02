import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import Page, Timeline


class RejectUntilAcceptedPage(Page):
    def __init__(self):
        super().__init__(
            label="reject_until_accepted",
            time_estimate=1,
            template_fragment_str="""
                <p id="adversarial-rejection-page">
                    Rejection retry page
                </p>
            """,
        )

    def validate(self, response, **kwargs):
        if response.answer != "accepted":
            return "Please submit the accepted answer."
        return None

    def get_bot_response(self, experiment, bot):
        return "accepted"


def listener_script(page_name):
    return f"""
    window.__adversarialLifecycle = window.__adversarialLifecycle || {{
        listenerClicks: 0,
        cleanupCalls: 0,
        activations: [],
    }};
    window.__adversarialLifecycle.activations.push("{page_name}");

    psynet.addPageEventListener(window, "click", function () {{
        window.__adversarialLifecycle.listenerClicks += 1;
    }});

    psynet.addPageCleanupCallback(function () {{
        window.__adversarialLifecycle.cleanupCalls += 1;
    }});
    """


class ListenerPage(Page):
    def __init__(self, page_name):
        self.page_name = page_name
        super().__init__(
            label=f"listener_{page_name}",
            time_estimate=1,
            template_fragment_str=f"""
                <p id="listener-page" data-page-name="{page_name}">
                    Listener page {page_name}
                </p>
            """,
            scripts=[listener_script(page_name)],
            save_answer=False,
        )

    def get_bot_response(self, experiment, bot):
        return None


class TrackedTimerPage(Page):
    def __init__(self):
        super().__init__(
            label="tracked_timer",
            time_estimate=1,
            template_fragment_str="""
                <p id="tracked-timer-page">
                    Tracked timer page
                </p>
                <script>
                    window.__trackedTimerLifecycle = {
                        timeoutFired: false,
                        intervalTicks: 0,
                    };

                    psynet.trial.onEvent("trialConstruct", function () {
                        psynet.trial.setTimer(function () {
                            window.__trackedTimerLifecycle.timeoutFired = true;
                            psynet.nextPage("stale-timeout");
                        }, 250);

                        psynet.trial.setRepeatingTimer(function () {
                            window.__trackedTimerLifecycle.intervalTicks += 1;
                        }, 25);
                    });
                </script>
            """,
        )

    def get_bot_response(self, experiment, bot):
        return None


class Exp(psynet.experiment.Experiment):
    label = "Adversarial lifecycle test"

    timeline = Timeline(
        RejectUntilAcceptedPage(),
        TrackedTimerPage(),
        InfoPage("Timer cleanup checkpoint", time_estimate=1),
        ListenerPage("first"),
        InfoPage("Listener cleanup checkpoint", time_estimate=1),
        ListenerPage("second"),
        InfoPage("Adversarial lifecycle complete", time_estimate=1),
    )
