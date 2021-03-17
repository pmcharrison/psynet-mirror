$(document).ready(function() {
    $('#camera-playback-button').click(function() {
        play_video()
    });

    $('#restart-recording-button').click(function() {
        restart_video_recording();
    });
});


function play_video() {
    $('#camera-playback-button').prop('disabled', true);
    let cameraPlayback = document.getElementById("camera-playback")
    cameraPlayback.play();
    cameraPlayback.onended = function(e) {
        $('#camera-playback-button').prop('disabled', false);
    };
}

function restart_video_recording() {
    window.location.reload();
}

function upload_camera_recording() {
    $("#record-upload").show();
    $('#camera-playback-button').hide()
    $('#video-upload-button').hide()
    $('#restart-recording-button').hide()
    $('#next_button').show();
    startPresignedUrlUpload(psynet.media.data["videoBlob"], psynet.media.presignedUrlCamera)
}

/*** Audio recording helper functions ***/
function startAudioRecording() {
    psynet.log.debug("Starting recording.");
    psynet.register_event("audio_record_start");
    $(".record-alert").hide();
    $("#record-active").show();
    recorder.clear();
    recorder.record();
}

function endAudioRecording() {
    psynet.log.debug("Ending recording.")
    psynet.register_event("audio_record_end");
    recorder.exportWAV(function (blob) {
        $(".record-alert").hide();
        $("#record-upload").show();
        startPresignedUrlUpload(blob, presignedUrl);
    })
}

/*** Screen capture helper functions ***/
function startScreenRecording() {
    psynet.log.debug("Starting screen recording...");
    psynet.register_event("screen_record_start");
    $(".record-alert").hide();
    $("#record-active").show();
}

function stopScreenRecording() {
    psynet.log.debug("Ending screen recording.")
    psynet.register_event("screen_record_end");
    screenRecorder.stopRecording(function () {
        stopScreenCaptureCallback(psynet.media.presignedUrlScreen);
    });

    $(".record-alert").hide();
    $("#record-upload").show();
}

function stopScreenCaptureCallback() {
    let screenBlob = screenRecorder.getBlob();
    screenRecorder.screen.stop();
    screenRecorder.destroy();
    screenRecorder = null;

    startPresignedUrlUpload(screenBlob, psynet.media.presignedUrlScreen);
    psynet.log.debug("Screen recording ended successfully!")
}

function invokeGetDisplayMedia(success, error) {
    if(navigator.mediaDevices.getDisplayMedia) {
        navigator.mediaDevices.getDisplayMedia({ video: true }).then(success).catch(error);
    }
    else {
        navigator.getDisplayMedia({ video: true }).then(success).catch(error);
    }
}

function captureScreen(callback) {
    invokeGetDisplayMedia(function(screen) {
        callback(screen);
    }, function(error) {
        console.error("Unable to capture your screen.", error.name + ":", error.message);
        psynet.next_page();
    });
}

/*** Camera recording helper functions ***/
function startCameraRecording() {
    psynet.log.debug("Starting video recording using camera...");
    psynet.register_event("camera_record_start");

    $(".record-alert").hide();
    $("#record-active").show();

    videoRecorder.startRecording(videoRecorder.stream).then(function() {
        console.info('Recording video using camera...');
    }).catch(function(error) {
        console.error('Cannot start video recording using camera:', error.name + ":", error.message);
    });
}

function stopCameraRecording() {
    psynet.log.debug("Ending recording.")
    psynet.register_event("camera_record_end");

    videoRecorder.stopRecording().then(function() {
        psynet.media.data["videoBlob"] = videoRecorder.blob;
        videoRecorder.stream.stop();

        $(".record-alert").hide();

        if (allow_restart) {
          $('#next_button').hide();
          $('#restart-recording-button').show()
          $('#video-upload-button').show()
        }

        if (playback_before_upload) {
          $('#next_button').hide();
          $('#camera-recording').hide()
          $('#camera-playback').show()
          $('#camera-playback-button').show()
          $('#video-upload-button').show()

          let cameraPlayback = document.getElementById("camera-playback");
          cameraPlayback.src = URL.createObjectURL(psynet.media.data["videoBlob"]);
          cameraPlayback.pause();
          $('#video-upload-button').click(function(){
            upload_camera_recording()
          });
        } else {
          $("#record-upload").show();
          upload_camera_recording()
        }
        psynet.log.debug("Video recording ended successfully!")
    }).catch(function(error) {
        console.error('stopRecording failure', error);
    });
}

/*** General helper functions ***/
function startPresignedUrlUpload(wavAudioBlob, presignedUrl) {
    let xhr = new XMLHttpRequest();
    xhr.open('PUT', presignedUrl, true);
    psynet.log.debug("Presigned URL for upload to S3: " + presignedUrl);

    psynet.register_event("presigned_url_start_upload", {url: presignedUrl});

    xhr.onload = function(e) {
        psynet.log.debug("File uploaded successfully to presigned url.");
        psynet.register_event("presigned_url_end_upload", {url: presignedUrl});
        psynet.submit.ready("finished-recording");
        $(".record-alert").hide();
        $("#record-finish").show();
        $('#next_button').show();
    };

    let wavFile = new File([wavAudioBlob], "s3_upload.wav")
    xhr.send(wavFile);
}

function startTimer(startDelay, countdownContainer, countdown) {
    startDelay -= 1;
    var videoStartCountdown = setInterval(function () {
        if (startDelay <= 0) {
        clearInterval(videoStartCountdown);
            countdownContainer.hide();
        } else {
            countdown.text(startDelay);
        }
        startDelay -= 1;
    }, 1000);
}
