export async function activate({root, trial}) {
    const slider = root.querySelector("#slider");
    let intervalId;

    function updateValue() {
        root.querySelector("#slider-raw-value").textContent =
            parseFloat(slider.getAttribute("raw-value")).toFixed(2);
        root.querySelector("#slider-output-value").textContent =
            parseFloat(slider.getAttribute("output-value")).toFixed(2);
        root.querySelector("#phase").textContent =
            parseFloat(slider.getAttribute("phase")).toFixed(2);
        root.querySelector("#random-wrap").textContent =
            slider.getAttribute("random-wrap");
    }

    trial.onEvent("trialConstruct", function () {
        intervalId = trial.setRepeatingTimer(updateValue, 100);
    });

    return function cleanup() {
        window.clearInterval(intervalId);
    };
}
