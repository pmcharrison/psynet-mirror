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
        startPresignedUrlUpload(blob, presignedUrl);
    })
}

/*** Screen capture functions ***/
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
        stopScreenCaptureCallback(presignedUrlScreen);
    });

    $(".record-alert").hide();
    $("#record-upload").show();
}

function stopScreenCaptureCallback(presignedUrl) {
    let screenBlob = screenRecorder.getBlob();
    screenRecorder.screen.stop();
    screenRecorder.destroy();
    screenRecorder = null;

    startPresignedUrlUpload(screenBlob, presignedUrl);
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

function stopCameraRecording(presignedUrl) {
    psynet.log.debug("Ending recording.")
    psynet.register_event("camera_record_end");

    videoRecorder.stopRecording().then(function() {
        let videoBlob = videoRecorder.blob;
        videoRecorder.stream.stop();

        $(".record-alert").hide();
        $("#record-upload").show();

        startPresignedUrlUpload(videoBlob, presignedUrl);
        psynet.log.debug("Video recording ended successfully!")
    }).catch(function(error) {
        console.error('stopRecording failure', error);
    });
}

/*** General functions start ***/
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
