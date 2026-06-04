psynet.trial.onEvent("trialConstruct", function () {
    var button = document.getElementById("next-button");
    psynet.addPageEventListener(button, "click", function () {
        psynet.submitResponse();
    });
});
