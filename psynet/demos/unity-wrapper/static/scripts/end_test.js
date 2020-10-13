/*---------------------------------------------------------------------------
                        SETTING ONCLICK EVENTS
---------------------------------------------------------------------------*/
// document.getElementById("next").addEventListener("click", get_responses);
var count_submited=0
var responses = {
};

function get_responses(){

    // populate the responses object
    responses.gender = document.getElementById("gender").value;
    responses.age = document.getElementById("age").value;
    responses.country = document.getElementById("country").value;
    responses.experiment_feedback = document.getElementById("experiment_feedback").value.trim();
    responses.issues = document.getElementById("issues").value.trim();
    


    // ensure that all fields are filled
    keys = Object.keys(responses)
    for (var i = 0; i < keys.length; i++) {
        var key = keys[i]
        if (responses[key] == "") {
            alert("Please fill out all of the fields!");
            return;
        }
    }
    
    //dallinger.post('/participant_counter/'+ dallinger.identity.participantId).done(function(){dallinger.submitQuestionnaire();});
    dallinger.submitQuestionnaire();

    console.log(responses);
}

