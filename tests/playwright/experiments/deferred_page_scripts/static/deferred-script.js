window.__psynetDeferredPageScript = window.__psynetDeferredPageScript || {
    scriptExecutions: 0,
    trialConstructRuns: 0,
};

window.__psynetDeferredPageScript.scriptExecutions += 1;

psynet.trial.onEvent("trialConstruct", function () {
    window.__psynetDeferredPageScript.trialConstructRuns += 1;
    const marker = document.getElementById("deferred-trial-construct-marker");
    if (marker) {
        marker.dataset.trialConstructHandlerRan = "true";
        marker.textContent = "trialConstruct handler ran";
    }
});
