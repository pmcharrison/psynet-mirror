/*** Audio recording functions ***/
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
        startPresignedUrlUpload(blob);
    })
}

/*** Screen capture functions ***/
function startScreenRecording() {
    psynet.log.debug("Starting screen recording...");
    psynet.register_event("video_record_start");
    $(".record-alert").hide();
    $("#record-active").show();
}

function stopScreenRecording() {
    psynet.log.debug("Ending screen recording.")
    psynet.register_event("screen_record_end");
    screenRecorder.stopRecording(stopscreenCaptureCallback);

    $(".record-alert").hide();
    $("#record-upload").show();
}

function stopscreenCaptureCallback() {
    var blob = screenRecorder.getBlob();
    psynet.log.debug(blob);
    screenRecorder.screen.stop();
    screenRecorder.destroy();
    screenRecorder = null;
    startPresignedUrlUpload(blob);
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

/*** Video/Screen recording functions ***/
function startVideoRecording() {
    psynet.log.debug("Starting video recording...");
    psynet.register_event("video_record_start");
    $(".record-alert").hide();
    $("#record-active").show();
    videoRecorder.startRecording(videoRecorder.stream).then(function() {
        console.info('Recording video...');
    }).catch(function(error) {
        console.error('Cannot start video recording:', error.name + ":", error.message);
    });
}

function stopVideoRecording() {
    psynet.log.debug("Ending recording.")
    psynet.register_event("video_record_end");
    videoRecorder.stopRecording().then(function() {
        psynet.log.debug("Video recording ended successfully!")
        var blob = videoRecorder.blob;

        videoRecorder.stream.stop();
        $(".record-alert").hide();
        $("#record-upload").show();
        startPresignedUrlUpload(blob);
    }).catch(function(error) {
        console.error('stopRecording failure', error);
    });
}

/*** General functions start ***/
function startPresignedUrlUpload(wavAudioBlob) {
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
    };

    let wavFile = new File([wavAudioBlob], "s3_upload.wav")
    xhr.send(wavFile);
}

function retrieve_response() {
    return {
        raw_answer: presignedUrl,
    }
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
