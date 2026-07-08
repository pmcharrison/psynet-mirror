function pad(n) {
    return (n.length < 2) ? "0" + n : n;
}

function updateSliderBackground() {
    psynet.log.debug("Updating slider background");
    var rHex = parseInt(document.getElementById("red").value, 10).toString(16),
        gHex = parseInt(document.getElementById("green").value, 10).toString(16),
        bHex = parseInt(document.getElementById("blue").value, 10).toString(16),
        hex = "#" + pad(rHex) + pad(gHex) + pad(bHex);
    document.getElementById("color-box").style.backgroundColor = hex;
}

// In-place timeline transitions execute page js_links before the slider
// control's main-body macro script initialises psynet.page.control.slider,
// so register the hook via the trialConstruct lifecycle event, which fires
// after the control is initialised in both legacy and in-place modes.
psynet.trial.onEvent("trialConstruct", function () {
    updateSliderBackground();
    psynet.page.control.slider.onSliderEvent = updateSliderBackground;
});
