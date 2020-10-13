// import { dallinger } from "../../../../../../../../.virtualenvs/dlgr_env/lib/python3.7/site-packages/dallinger/frontend/static/scripts/dallinger2";

/*---------------------------------------------------------------------------
                        global variables
---------------------------------------------------------------------------*/
// key of correct answers for test
var audio_players = [
    ['stim0', '2'],
    ['stim1', '3'],
    ['stim2', '1'],
    ['stim3', '1'],
    ['stim4', '2'],
    ['stim5', '3']
   ];

// variable to track # of correct responses
var numCorrect = 0;
var debug = false;
var app_debug;
var ERR_WAIT_TIME = 10000; // in between trials wait time

// counter to increment through steps of headphone test
var pageCounter = 0;
var pages = ["step0","step1", "step2"];

/*---------------------------------------------------------------------------
       Redirect to practice for debug
---------------------------------------------------------------------------*/
function check_debug_mode() {
reqwest ({
url: "/get_global_params/",
method: 'get',
type: 'json',
success: function (resp) {
if (debug) {
console.log("---> check debug mode" );
console.log(resp);
}
app_debug=JSON.parse(resp.global_params);
if (debug) {
console.log("app_debug: ");
console.log(app_debug);
}
if(app_debug.skip_head_phone_check) {
// if you skip the last step of instructions, then you
// have to manually create the participant here
dallinger.allowExit();
dallinger.goToPage('instructions');
}
},
error: function (err) {
console.log(err);
clearTimeout(err_time);
err_time = setTimeout(function(){create_agent();},ERR_WAIT_TIME);
}
});
}

check_debug_mode();

/*---------------------------------------------------------------------------
       HELPER FUNCTIONS
---------------------------------------------------------------------------*/

function show(elementID) {
document.getElementById(elementID).style.display = 'block';
}

function hide(elementID) {
document.getElementById(elementID).style.display = 'none';
}

// checks whether or not headphone test answers are correct
// increments numCorrect += 1 for each correct answers
function check_answers(audio_players_subarray) {

// then, iterate through the first half of audio_players to check answers
for (var i = 0; i < audio_players_subarray.length; i++) {

// get element name
var name = audio_players_subarray[i][0] + "_response"; // ex. stim0_response

// select associated radio buttons
radios = document.getElementsByName(name);

// iterate through radio buttons
for (var j = 0; j < radios.length; j++) {

// if the radio button is checked and has the correct value
if (radios[j].checked && radios[j].value == audio_players_subarray[i][1]) {
numCorrect ++;
if (debug) {
   console.log(name + " is correct!");
}
break;
}
}
}
}

// show next step
function next(){

// get ID of current page and next page
var currentPage = pages[pageCounter];
var nextPage = pages[pageCounter + 1];

// hide current page and show next step
document.getElementById(currentPage).style.display = "none";
document.getElementById(nextPage).style.display = "block";

// increment page counter
pageCounter += 1;
}

// selects and plays an audio player by HTML ID
function stim_play(stim) {
var clip = document.getElementById(stim);
clip.oncanplay=function () {
clip.onloaddata="";
clip.play();
}
clip.load();
}

/*---------------------------------------------------------------------------
       SETTING ONCLICK EVENTS
---------------------------------------------------------------------------*/

$(document).ready(function(){

/*----------------------------------
PAGE 1
----------------------------------*/
// play calibration audio
$('#calibrationSound').click(function() {
stim_play('myAudio');

// continue button will show when audio finishes playing
document.getElementById('myAudio').onended = function() {
show('next');
}
});

// continue button
$('#next').click(function() {
next();
});

/*----------------------------------
PAGE 2
----------------------------------*/

// Play buttons
$('#play_stim0').click(function(){
// play audio clip
var stim0 = audio_players[0][0];
stim_play(stim0);
});

$('#play_stim1').click(function(){
// play audio clip
var stim1 = audio_players[1][0];
stim_play(stim1);
});

$('#play_stim2').click(function(){
// play audio clip
var stim2 = audio_players[2][0];
stim_play(stim2);

// button will show when audio is done
document.getElementById('stim2').onended = function() {
show('submit1');
}
});

// check answers and go to next page
$("#submit1").click(function() {
// check the first three test sounds
check_answers(audio_players.slice(0, 3));

// go to the next page
next();
});

/*----------------------------------
PAGE 3
----------------------------------*/
// Play buttons
$('#play_stim3').click(function(){
stim_play("stim3");
});

$('#play_stim4').click(function(){
stim_play("stim4");
});

$('#play_stim5').click(function(){
stim_play("stim5");

// button will show when audio is done
document.getElementById('stim5').onended = function() {
show('submit2');
}
});

// submit second page of headphone test
$("#submit2").click(function(){

// check second half of audio_players
check_answers(audio_players.slice(3));
if (numCorrect < 5) {
       dallinger.post("/headphone-check/0/" + numCorrect + "/" + dallinger.identity.participantId).done(function(resp) {
              dallinger.allowExit();
              dallinger.goToPage("failed_headphone");
       })
} else {
       dallinger.post("/headphone-check/1/" + numCorrect + "/" + dallinger.identity.participantId).done(function(resp) {
              alert("Congratulations! You have passed the headphone test, and will now continue "
                     + "on to training for the experiment.");
              dallinger.allowExit();
              dallinger.goToPage(next_page);
       })
}

// window.location = NEXT PAGE
});

});
