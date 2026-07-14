export function activate({root, psynet}) {
    const timeline = globalThis.timeline;
    if (!timeline) {
        throw new Error(
            "The jsPsych timeline object could not be found. Please check the timeline script for errors."
        );
    }

    let completed = false;
    let deactivating = false;
    const jsPsych = initJsPsych({
        display_element: root.querySelector("#js-psych"),
        on_finish: function () {
            completed = true;
            if (!deactivating) {
                return psynet.nextPage(jsPsych.data.get().json());
            }
        }
    });
    globalThis.jsPsych = jsPsych;

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
        if (globalThis.jsPsych === jsPsych) {
            globalThis.jsPsych = undefined;
        }
        if (globalThis.timeline === timeline) {
            globalThis.timeline = undefined;
        }
    };
}
