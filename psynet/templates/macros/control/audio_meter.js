/*
The MIT License (MIT)

Copyright (c) 2014 Chris Wilson, modified 2020 by Peter Harrison

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

var audioMeterControl = {}

audioMeterControl.init = function(json) {
    config = JSON.parse(json);

    this.displayRange = config.display_range;
    this.decay = config.decay;
    this.threshold = config.threshold;
    this.grace = config.grace
    this.warnOnClip = config.warn_on_clip
    this.msgDuration = config.msg_duration;

    this.audioContext = null;
    this.audioMeter = null;
    this.audioMeterText = document.getElementById("audio-meter-text");
    this.canvasContext = null;
    this.audioMeterMaxWidth=300;
    this.audioMeterMaxHeight=50;
    this.rafID = null;

    this.timeLastTooLow = -1e20;
    this.timeLastTooHigh = -1e20;
    this.timeUntilTooLow = 1.5; // ms
    this.timeUntilTooHigh = 0.0; // ms

    this.timeLastNotTooLow = -1e20;
    this.timeLastNotTooHigh = -1e20;

    this.messageTimer = null;

    var audioMeterControl = this;
    psynet.trial.onEvent("trialConstruct",function() {
        audioMeterControl.canvasContext = document.getElementById("audio-meter").getContext("2d");
        audioMeterControl.audioContext = psynet.media.audioContext;
        return new Promise((resolve) => {
            navigator.mediaDevices.getUserMedia({ audio: true, video: false })
            .then(function(stream) {
                audioMeterControl.onMicrophoneGranted(stream);
                resolve();
            });
        });
    });
    setTimeout(function() {
        audioMeterControl.audioMeterText.style.display = "block";
    }, 1000);
}

audioMeterControl.onMicrophoneDenied = function() {
    alert('Microphone permission denied. You may refresh the page to try again.');
}

audioMeterControl.onMicrophoneGranted = function(stream) {
    this.showMessage("Starting audio meter...", "blue");

    // Create an AudioNode from the stream.
    var mediaStreamSource = this.audioContext.createMediaStreamSource(stream);

    // Create a new volume meter and connect it.
    this.audioMeter = this.createAudioMeter(this.audioContext);
    mediaStreamSource.connect(this.audioMeter);

    // kick off the visual updating
    var audioMeterControl = this;
    window.requestAnimationFrame(function(time) {
        audioMeterControl.onLevelChange(time);
    });
}

audioMeterControl.showMessage = function(message, color) {
    this.audioMeterText.innerHTML = message;
    this.audioMeterText.style.color = color;
    this.canvasContext.fillStyle = color;

    clearTimeout(this.messageTimer);

    var self = this;
    setTimeout(function() {
        self.resetMessage();
    }, self.msgDuration * 2000);
}

audioMeterControl.resetMessage = function() {
    this.audioMeterText.innerHTML = "Just right.";
    this.audioMeterText.style.color = "green";
    this.canvasContext.fillStyle = "green";
}

audioMeterControl.onLevelChange = function(time) {
    this.canvasContext.clearRect(0, 0, this.audioMeterMaxWidth, this.audioMeterMaxHeight);

    if (this.audioMeter.volume.high >= this.threshold.high) {
        this.timeLastTooHigh = time;
    } else {
        this.timeLastNotTooHigh = time;
    }

    if (this.audioMeter.volume.low <= this.threshold.low) {
        this.timeLastTooLow = time;
    } else {
        this.timeLastNotTooLow = time;
    }

    if (
        this.audioMeter.checkClipping() ||
        time - this.timeLastNotTooHigh > this.timeUntilTooHigh * 1000.0
    ) {
        this.showMessage("Too loud!", "red")
    } else if (time - this.timeLastNotTooLow > this.timeUntilTooLow * 1000.0) {
        this.showMessage("Too quiet!", "red")
    }

    // draw a bar based on the current volume
    var proportion;
    if (this.audioMeter.volume.display <= this.displayRange.min) {
        proportion = 0.0;
    } else if (this.audioMeter.volume.display >= this.displayRange.max) {
        proportion = 1.0;
    } else {
        proportion = (this.audioMeter.volume.display - this.displayRange.min) / (this.displayRange.max - this.displayRange.min);
    }

    this.canvasContext.fillRect(0, 0, proportion * this.audioMeterMaxWidth, this.audioMeterMaxHeight);

    // set up the next visual callback
    var audioMeterControl = this;
    this.rafID = window.requestAnimationFrame(function(time) {
        audioMeterControl.onLevelChange(time);
    });
}

/*
    Usage:
    audioNode = createAudioMeter(audioContext,clipLevel,averaging,clipLag);
    audioContext: the AudioContext you're using.
    clipLevel: the level (0 to 1) that you would consider "clipping".
    Defaults to 0.98.
    averaging: how "smoothed" you would like the meter to be over time.
    Should be between 0 and less than 1.  Defaults to 0.95.
    clipLag: how long you would like the "clipping" indicator to show
    after clipping has occured, in milliseconds.  Defaults to 750ms.
    Access the clipping through node.checkClipping(); use node.shutdown to get rid of it.
    */

audioMeterControl.createAudioMeter = function(audioContext, clipLevel, averaging, clipLag) {
    var audioMeterControl = this;
    var processor = this.audioContext.createScriptProcessor(512);
    processor.onaudioprocess = function(event) {
        audioMeterControl.volumeAudioProcess(event);
    }
    processor.clipping = false;
    processor.lastClip = 0;
    processor.volume = {
        display: 0.0,
        high: 0.0,
        low: 0.0
    }
    processor.clipLevel = clipLevel || 0.98;
    processor.averaging = averaging || 0.95;
    processor.clipLag = clipLag || 750;

    // this will have no effect, since we don't copy the input to the output,
    // but works around a current Chrome bug.
    processor.connect(audioContext.destination);

    processor.checkClipping =
        function(){
            if (!this.clipping)
                return false;
            if ((this.lastClip + this.clipLag) < window.performance.now())
                this.clipping = false;
            return this.clipping;
        };

    processor.shutdown =
        function(){
            this.disconnect();
            this.onaudioprocess = null;
        };

    return processor;
}

audioMeterControl.volumeAudioProcess = function(event) {
    var buf = event.inputBuffer.getChannelData(0);
    var bufLength = buf.length;
    var sum = 0;
    var x;

    // Do a root-mean-square on the samples: sum up the squares...
    for (var i = 0; i < bufLength; i++) {
        x = buf[i];
        if (Math.abs(x) >= this.clipLevel) {
            this.clipping = true;
            this.lastClip = window.performance.now();
        }
        sum += x * x;
    }

    // ... then take the square root of the sum.
    var rms =  Math.sqrt(sum / bufLength);

    var bufferDuration = bufLength / event.inputBuffer.sampleRate;


    // Now smooth this out with the averaging factor applied
    // to the previous sample - take the max here because we
    // want "fast attack, slow release."
    var self = this;
    ["display", "high", "low"].forEach(function(x) {
        // Exponential smmoothing, see https://en.wikipedia.org/wiki/Exponential_smoothing
        var alpha = 1 - Math.exp(- bufferDuration / self.decay[x]);
        self.audioMeter.volume[x] = (1 - alpha) * self.audioMeter.volume[x] + alpha * self.rmsToDb(rms);
    })

    // this.volume = Math.max(rms, this.volume*this.averaging);
}

audioMeterControl.rmsToDb = function(rms) {
    return Math.max(-100, 20 * Math.log10(rms));
}

audioMeterControl.updateFromSliders = function() {
    this.decay = {
        display: $("#decay-display").get(0).value,
        high: $("#decay-high").get(0).value,
        low: $("#decay-low").get(0).value
    }

    this.threshold = {
        high: $("#threshold-high").get(0).value,
        low: $("#threshold-low").get(0).value,
    }

    this.grace = {
        high: $("#grace-high").get(0).value,
        low: $("#grace-low").get(0).value,
    }

    this.warnOnClip = Boolean($("#warn-on-clip").get(0).value)

    this.msgDuration = {
        high: $("#msg-duration-high").get(0).value,
        low: $("#msg-duration-low").get(0).value,
    }
}
