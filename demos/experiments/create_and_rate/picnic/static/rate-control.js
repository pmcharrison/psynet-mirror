(function () {
    "use strict";

    psynet.trial.onEvent("trialConstruct", function () {
        psynet.addPageEventListener(document, "change", function (e) {
            if (e.target.value === "none") {
                $(".rules").prop("checked", false);
            } else {
                $("#none").prop("checked", false);
            }
        });
        psynet.addPageEventListener(
            document.getElementById("rate-submit"),
            "click",
            validate
        );
    });

    function validate() {
        var rule_dict = {};
        var n_checked = 0;
        $("input").each(function (i, elem) {
            var is_checked = $(elem).is(":checked");
            if (is_checked) {
                n_checked += 1;
            }
            rule_dict[elem.id] = {
                "checked": is_checked,
                "rule": $(elem).val()
            };
        });
        if (n_checked > 0) {
            psynet.nextPage(rule_dict);
        } else {
            alert("You need to interact with the page before you can continue.");
        }
    }
})();
