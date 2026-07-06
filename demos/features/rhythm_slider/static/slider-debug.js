update_value = function() {
    document.getElementById("slider-audio").innerHTML = findClosestMedia(slider);
    document.getElementById("slider-raw-value").innerHTML = parseFloat(slider.getAttribute("raw-value")).toFixed(2);
    document.getElementById("slider-output-value").innerHTML = parseFloat(slider.getAttribute("output-value")).toFixed(2);
    document.getElementById("phase").innerHTML = parseFloat(slider.getAttribute("phase")).toFixed(2);
    document.getElementById("random-wrap").innerHTML = slider.getAttribute("random-wrap");
};

psynet.trial.onEvent("trialConstruct", () => psynet.trial.setRepeatingTimer(update_value, 100));
