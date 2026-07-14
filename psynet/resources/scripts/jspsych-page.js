export function activate({psynet}) {
    const jsPsych = globalThis.jsPsych;
    const timeline = globalThis.psynetJsPsychTimeline;
    if (!jsPsych) {
        throw new Error(
            "The jsPsych instance could not be initialized. Please check the jsPsych dependencies."
        );
    }
    if (!timeline) {
        throw new Error(
            "The jsPsych timeline object could not be found. Please check the timeline script for errors."
        );
    }

    let completed = false;
    let deactivating = false;
    globalThis.psynetJsPsychOnFinish = function () {
        completed = true;
        if (!deactivating) {
            return psynet.nextPage(jsPsych.data.get().json());
        }
    };

    jsPsych.run(timeline).catch(function (error) {
        if (!deactivating) {
            psynet.log.error(error.stack || String(error));
        }
    });

    return function cleanup() {
        deactivating = true;
        if (!completed && jsPsych.timeline) {
            jsPsych.endExperiment();
        }
        window.removeEventListener(
            "beforeunload",
            jsPsych.getInitSettings().on_close
        );
        document.documentElement.removeAttribute("jspsych");
        globalThis.psynetJsPsychOnFinish = undefined;
        if (globalThis.jsPsych === jsPsych) {
            globalThis.jsPsych = undefined;
        }
        if (globalThis.psynetJsPsychTimeline === timeline) {
            globalThis.psynetJsPsychTimeline = undefined;
        }
        if (globalThis.timeline === timeline) {
            globalThis.timeline = undefined;
        }
    };
}
