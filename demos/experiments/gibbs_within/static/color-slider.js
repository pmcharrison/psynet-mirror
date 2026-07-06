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

updateSliderBackground();
psynet.page.control.slider.onSliderEvent = updateSliderBackground;
