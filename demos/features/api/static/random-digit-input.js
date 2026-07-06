psynet.trial.onEvent("trialStart", function () {
    $.get("/api/random_digit_input", function(data) {
        $("#digit").text(data.random_number.toString().padStart(7, "0"));
    });
    $.get("/api/hello?name=world", function(data) {
        $("#name").text(data);
    });
    $.ajax({
        url: "/api/page_uuid",
        type: "POST",
        data: JSON.stringify({participant_id: psynet.participantId}),
        dataType: "json",
        contentType: "application/json",
        success: function(data) {
            $("#page_uuid").text(data.page_uuid);
        }
    });
});
