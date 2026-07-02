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
            """,
            scripts=[
                """
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
                """
            ],
        )

    def get_bot_response(self, experiment, bot):
        return None


class AudioFadeOutPage(Page):
    def __init__(self):
        super().__init__(
            label="audio_fade_out",
            time_estimate=1,
            template_fragment_str="""
                <p id="audio-fade-out-page">
                    Audio fade-out page
                </p>
            """,
            scripts=[
                """
                window.__audioFadeOutLifecycle = { ready: false };

                function writeAscii(view, offset, text) {
                    for (let i = 0; i < text.length; i++) {
                        view.setUint8(offset + i, text.charCodeAt(i));
                    }
                }

                function makeSilentWavBuffer(durationSeconds) {
                    const sampleRate = 8000;
                    const samples = Math.floor(sampleRate * durationSeconds);
                    const dataSize = samples * 2;
                    const buffer = new ArrayBuffer(44 + dataSize);
                    const view = new DataView(buffer);
                    writeAscii(view, 0, "RIFF");
                    view.setUint32(4, 36 + dataSize, true);
                    writeAscii(view, 8, "WAVE");
                    writeAscii(view, 12, "fmt ");
                    view.setUint32(16, 16, true);
                    view.setUint16(20, 1, true);
                    view.setUint16(22, 1, true);
                    view.setUint32(24, sampleRate, true);
                    view.setUint32(28, sampleRate * 2, true);
                    view.setUint16(32, 2, true);
                    view.setUint16(34, 16, true);
                    writeAscii(view, 36, "data");
                    view.setUint32(40, dataSize, true);
                    return buffer;
                }

                psynet.trial.onEvent("trialConstruct", async function () {
                    await psynet.media.addExtraAudioStimulus(
                        makeSilentWavBuffer(0.8),
                        "fadeout_stale_audio"
                    );
                    psynet.audio.fadeout_stale_audio.play({
                        fadeOut: 0.3,
                        gain: 0.001,
                    });
                    window.__audioFadeOutLifecycle.ready = true;
                });
                """
            ],
        )

    def get_bot_response(self, experiment, bot):
        return None


class Exp(psynet.experiment.Experiment):
    label = "Adversarial lifecycle test"

    timeline = Timeline(
        RejectUntilAcceptedPage(),
        TrackedTimerPage(),
        InfoPage("Timer cleanup checkpoint", time_estimate=1),
        AudioFadeOutPage(),
        InfoPage("Audio fade-out checkpoint", time_estimate=1),
        ListenerPage("first"),
        InfoPage("Listener cleanup checkpoint", time_estimate=1),
        ListenerPage("second"),
        InfoPage("Adversarial lifecycle complete", time_estimate=1),
    )
