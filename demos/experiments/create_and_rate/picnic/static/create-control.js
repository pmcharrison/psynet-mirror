function validate() {
    var rule = $("#rule").val();
    var success = true;
    if (rule === "") {
        alert("Please enter a rule");
        success = false;
        return;
    } else if ((rule.split(" ").length - 1) < 3) {
        alert('Your rule must start with "The rule is:"');
        success = false;
        return;
    }
    var questionsObject = {};
    ["difficult", "abstract", "helpful_positive", "helpful_negative"].forEach(function (id) {
        var radio = $("input[name=" + id + "]:checked");
        if (radio.length !== 1) {
            success = false;
        } else {
            questionsObject[id] = radio.val();
        }
    });
    if (!success) {
        alert("Please answer all questions");
        return;
    }
    if (success) {
        psynet.nextPage({
            "rule": rule,
            "questions": questionsObject
        });
    }
}
