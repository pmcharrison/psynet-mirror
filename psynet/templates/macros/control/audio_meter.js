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

var audio_meter_control = {}

audio_meter_control.init = function(json) {
    config = JSON.parse(json);

    this.display_range = config.display_range;
    this.decay = config.decay;
    this.threshold = config.threshold;
    this.grace = config.grace
    this.warn_on_clip = config.warn_on_clip
    this.msg_duration = config.msg_duration;

    this.audioContext = null;
    this.audio_meter = null;
    this.audio_meter_text = document.getElementById("audio_meter_text");
    this.canvasContext = null;
    this.audio_meter_max_width=300;
    this.audio_meter_max_height=50;
    this.rafID = null;

    this.time_last_too_low = -1e20;
    this.time_last_too_high = -1e20;
    this.time_until_too_low = 1.5; // ms
    this.time_until_too_high = 0.0; // ms

    this.time_last_not_too_low = -1e20;
    this.time_last_not_too_high = -1e20;

    this.message_timer = null;

    var audio_meter_control = this;
    psynet.media.register_on_loaded_routine(function() {
        audio_meter_control.canvasContext = document.getElementById( "audio_meter" ).getContext("2d");
        audio_meter_control.audioContext = psynet.media.audio_context;

        navigator.mediaDevices.getUserMedia({ audio: true, video: false })
        .then(function(stream) {
            audio_meter_control.onMicrophoneGranted(stream);
        })
    });
}

audio_meter_control.onMicrophoneDenied = function() {
    alert('Microphone permission denied. You may refresh the page to try again.');
}

audio_meter_control.onMicrophoneGranted = function(stream) {
    this.show_message("Starting audio meter...", "blue");

    // Create an AudioNode from the stream.
    var mediaStreamSource = this.audioContext.createMediaStreamSource(stream);

    // Create a new volume meter and connect it.
    this.audio_meter = this.createAudioMeter(this.audioContext);
    mediaStreamSource.connect(this.audio_meter);

    // kick off the visual updating
    var audio_meter_control = this;
    window.requestAnimationFrame(function(time) {
        audio_meter_control.onLevelChange(time)
    });
}

audio_meter_control.show_message = function(message, colour) {
    this.audio_meter_text.innerHTML = message;
    this.audio_meter_text.style.color = colour;
    this.canvasContext.fillStyle = colour;

    clearTimeout(this.message_timer);

    var self = this;
    setTimeout(function() {
        self.reset_message();
    }, self.msg_duration * 1000);
}

audio_meter_control.reset_message = function() {
    this.audio_meter_text.innerHTML = "Just right.";
    this.audio_meter_text.style.color = "green";
    this.canvasContext.fillStyle = "green";
}

audio_meter_control.onLevelChange = function(time) {
    this.canvasContext.clearRect(0, 0, this.audio_meter_max_width, this.audio_meter_max_height);

    if (this.audio_meter.volume.high >= this.threshold.high) {
        this.time_last_too_high = time;
    } else {
        this.time_last_not_too_high = time;
    }

    if (this.audio_meter.volume.low <= this.threshold.low) {
        this.time_last_too_low = time;
    } else {
        this.time_last_not_too_low = time;
    }

    if (
        this.audio_meter.checkClipping() ||
        time - this.time_last_not_too_high > this.time_until_too_high * 1000.0
    ) {
        this.show_message("Too loud!", "red")
    } else if (time - this.time_last_not_too_low > this.time_until_too_low * 1000.0) {
        this.show_message("Too quiet!", "red")
    }

    // draw a bar based on the current volume
    var proportion;
    if (this.audio_meter.volume.display <= this.display_range.min) {
        proportion = 0.0;
    } else if (this.audio_meter.volume.display >= this.display_range.max) {
        proportion = 1.0;
    } else {
        proportion = (this.audio_meter.volume.display - this.display_range.min) / (this.display_range.max - this.display_range.min);
    }

    this.canvasContext.fillRect(0, 0, proportion * this.audio_meter_max_width, this.audio_meter_max_height);

    // set up the next visual callback
    var audio_meter_control = this;
    this.rafID = window.requestAnimationFrame(function(time) {
        audio_meter_control.onLevelChange(time)
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

audio_meter_control.createAudioMeter = function(audioContext, clipLevel, averaging, clipLag) {
    var audio_meter_control = this;
    var processor = this.audioContext.createScriptProcessor(512);
    processor.onaudioprocess = function(event) {
        audio_meter_control.volumeAudioProcess(event);
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

audio_meter_control.volumeAudioProcess = function(event) {
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

    var buffer_duration = bufLength / event.inputBuffer.sampleRate;


    // Now smooth this out with the averaging factor applied
    // to the previous sample - take the max here because we
    // want "fast attack, slow release."
    var self = this;
    ["display", "high", "low"].forEach(function(x) {
        // Exponential smmoothing, see https://en.wikipedia.org/wiki/Exponential_smoothing
        var alpha = 1 - Math.exp(- buffer_duration / self.decay[x]);
        self.audio_meter.volume[x] = (1 - alpha) * self.audio_meter.volume[x] + alpha * self.rms_to_db(rms);
    })

    // this.volume = Math.max(rms, this.volume*this.averaging);
}

audio_meter_control.rms_to_db = function(rms) {
    return Math.max(-100, 20 * Math.log10(rms));
}

audio_meter_control.update_from_sliders = function() {
    this.decay = {
        display: $("#decay_display").get(0).value,
        high: $("#decay_high").get(0).value,
        low: $("#decay_low").get(0).value
    }

    this.threshold = {
        high: $("#threshold_high").get(0).value,
        low: $("#threshold_low").get(0).value,
    }

    this.grace = {
        high: $("#grace_high").get(0).value,
        low: $("#grace_low").get(0).value,
    }

    this.warn_on_clip = Boolean($("#warn_on_clip").get(0).value)

    this.msg_duration = {
        high: $("#msg_duration_high").get(0).value,
        low: $("#msg_duration_low").get(0).value,
    }
}