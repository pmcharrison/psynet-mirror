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
