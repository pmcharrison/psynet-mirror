import flask

import psynet.experiment
from psynet.consent import MTurkAudiovisualConsent, MTurkStandardConsent
from psynet.js_synth import Chord, InstrumentTimbre, JSSynth, Note, Rest, ShepardTimbre
from psynet.modular_page import (
    AudioMeterControl,
    AudioPrompt,
    AudioRecordControl,
    ModularPage,
    SliderControl,
    TappingAudioMeterControl,
    VideoPrompt,
    VideoRecordControl,
)
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import (
    Event,
    MediaSpec,
    PageMaker,
    ProgressDisplay,
    ProgressStage,
    Timeline,
    join,
)
from psynet.utils import get_logger

logger = get_logger()

example_js_synth_1 = ModularPage(
    "js_synth",
    JSSynth(
        "The JS synthesizer uses by default a harmonic complex tone as the timbre.",
        [
            Note(60),
            Note(64),
            Note(67),
            Rest(duration=1.0),
            Note(59),
            Note(62),
            Note(67),
        ],
    ),
    time_estimate=5,
)

example_js_synth_2 = ModularPage(
    "js_synth",
    JSSynth(
        "It is also possible to select various instrument sounds, for example the piano.",
        [
            Note(60),
            Note(63),
            Note(67),
        ],
        timbre=InstrumentTimbre("piano"),
        default_duration=0.5,
        default_silence=0.25,
    ),
    time_estimate=5,
)

example_js_synth_3 = ModularPage(
    "js_synth",
    JSSynth(
        "We can manipulate individual notes with a slider.",
        [
            Note(60),
            Note(63),
            Note(67),
        ],
        timbre=InstrumentTimbre("piano"),
        default_duration=0.5,
        default_silence=0.25,
    ),
    SliderControl(label="slider", start_value=63, min_value=57, max_value=70),
    time_estimate=5,
    events={
        "playMelody": Event(
            is_triggered_by="sliderChange",
            js="stimulus.notes[1].pitches = [info.outputValue]; psynet.trial.restart();",
        ),
        "disableSlider": Event(
            is_triggered_by="promptStart", js="slider.disabled = true;"
        ),
        "enableSlider": Event(
            is_triggered_by="promptEnd", js="slider.disabled = false;"
        ),
    },
)

example_js_synth_4 = ModularPage(
    "js_synth",
    JSSynth(
        "These chords are played with Shepard tones.",
        [
            Chord([60, 64, 67]),
            Chord([59, 62, 67]),
            Chord([60, 64, 67]),
        ],
        timbre=ShepardTimbre(),
    ),
    time_estimate=5,
)

example_preloading = InfoPage(
    flask.Markup(
        """
        <p>
            This page demonstrates audio preloading.
            A progress bar fills up on the bottom of the screen
            as the audio files are loaded into the client's browser.
            Once these audio files are loaded, you can access them programmatically.
        </p>
        <p>
            If you're running this demo locally, the audio files will load too
            fast for you to see the progress bar. However, you can simulate
            a slower internet connection by using the Developer Options
            of your browser.
            Note how the buttons only become enabled once the audio has finished loading.
        </p>
        <ul>
            <li> <button type="button" class="btn btn-primary wait-for-media-load" onclick="psynet.audio.bier.play();">Play 'bier'.</button></li>
            <li> <button type="button" class="btn btn-primary wait-for-media-load" onclick="psynet.audio.bier.stop();">Stop 'bier'.</button></li>
        </ul>
        <ul>
            <li> <button type="button" class="btn btn-primary wait-for-media-load" onclick="psynet.audio.funk_game_loop.play();">Play 'funk_game_loop'.</button></li>
            <li> <button type="button" class="btn btn-primary wait-for-media-load" onclick="psynet.audio.funk_game_loop.stop();">Stop 'funk_game_loop'.</button></li>
        </ul>
        <ul>
            <li> <button type="button" class="btn btn-primary wait-for-media-load" onclick="psynet.audio.honey_bee.play();">Play 'honey_bee'.</button></li>
            <li> <button type="button" class="btn btn-primary wait-for-media-load" onclick="psynet.audio.honey_bee.stop();">Stop 'honey_bee'.</button></li>
        </ul>
        <ul>
            <li> <button type="button" class="btn btn-primary wait-for-media-load" onclick="psynet.audio.there_it_is.play();">Play 'there_it_is'.</button></li>
            <li> <button type="button" class="btn btn-primary wait-for-media-load" onclick="psynet.audio.there_it_is.stop();">Stop 'there_it_is'.</button></li>
        </ul>
        """
    ),
    time_estimate=5,
    media=MediaSpec(
        audio={
            "bier": "/static/audio/bier.wav",
            "batch": {
                "url": "/static/audio/file_concatenated.mp3",
                "ids": ["funk_game_loop", "honey_bee", "there_it_is"],
                "type": "batch",
            },
        }
    ),
    css=[
        """
        .btn {
            margin: 2px
        }
        """
    ],
)

example_audio_meter = ModularPage(
    "audio_meter",
    """
    This page shows an audio meter.
    """,
    AudioMeterControl(calibrate=False),
    time_estimate=5,
)

example_audio_meter_calibrate = ModularPage(
    "audio_meter",
    "Here you can experiment with different audio meter parameters.",
    AudioMeterControl(calibrate=True),
    time_estimate=5,
)

example_audio_meter_calibrate_with_audio = ModularPage(
    "audio_meter",
    AudioPrompt(
        "/static/audio/train1.wav",
        "The default meter parameters are designed to work well for music playback.",
        loop=True,
    ),
    AudioMeterControl(calibrate=True),
    time_estimate=5,
)

example_audio_meter_with_audio = ModularPage(
    "audio_meter",
    AudioPrompt(
        "/static/audio/train1.wav",
        "This page shows an audio meter alongside an audio stimulus.",
        loop=True,
    ),
    AudioMeterControl(calibrate=True),
    time_estimate=5,
)

example_audio_meter_calibrate_with_tapping = ModularPage(
    "audio_meter",
    """
    The TappingAudioMeterControl class is a version of the AudioMeterControl class
    with defaults specialised for tapping experiments. In particular,
    we disable the clipping warning, decrease the smoothing,
    and increase the grace period for the
    too-high warning, to make sure that the short loud tap doesn't cause
    a warning message.
    """,
    TappingAudioMeterControl(calibrate=True),
    time_estimate=5,
)

example_audio_page = ModularPage(
    "audio_page",
    AudioPrompt(
        "/static/audio/bier.wav",
        "This page illustrates a simple audio page with one stimulus.",
        loop=False,
    ),
    time_estimate=5,
)

example_audio_page_2 = ModularPage(
    "audio_page",
    AudioPrompt(
        "/static/audio/bier.wav",
        "This page adds audio playback controls.",
        controls=True,
        loop=False,
    ),
    time_estimate=5,
)

example_audio_page_3 = ModularPage(
    "audio_page",
    AudioPrompt(
        "/static/audio/train1.wav",
        """
        This page illustrates a 'play window' combined with fade-in, fade-out, and loop.
        """,
        play_window=[5, 9],
        fade_in=0.75,
        fade_out=0.75,
        loop=True,
        controls=True,
    ),
    time_estimate=5,
)

example_record_page = join(
    ModularPage(
        "record_page",
        "This page lets you record audio. Note that, in this version, you must click 'Upload' when finished.",
        AudioRecordControl(
            duration=3.0,
            s3_bucket="audio-record-demo",
            show_meter=True,
            public_read=True,
            controls=True,
            auto_advance=True,
        ),
        time_estimate=5,
        progress_display=ProgressDisplay(
            duration=3.0,
            stages=[
                ProgressStage([0.0, 3.0], "Recording...", "red"),
            ],
        ),
    ),
    PageMaker(
        lambda participant: ModularPage(
            "playback",
            AudioPrompt(
                participant.answer["url"], "Here's the recording you just made."
            ),
        ),
        time_estimate=5,
    ),
)

example_listen_then_record_page = join(
    ModularPage(
        "record_page",
        AudioPrompt(
            url="https://headphone-check.s3.amazonaws.com/funk_game_loop.wav",
            text="""
            Here we play audio then activate the recorder 3 seconds afterwards.
            """,
            play_window=[0, 5.0],
        ),
        AudioRecordControl(
            duration=1.0,
            s3_bucket="audio-record-demo",
            show_meter=True,
            public_read=True,
            controls=True,
            auto_advance=True,
        ),
        time_estimate=5,
        events={"recordStart": Event(is_triggered_by="trialStart", delay=3.0)},
        progress_display=ProgressDisplay(
            duration=5.0,
            stages=[
                ProgressStage([0.0, 3.0], "Waiting to record..."),
                ProgressStage([3.0, 4.0], "Recording...", "red"),
                ProgressStage(
                    [4.0, 5.0], "Finished recording.", "green", persistent=True
                ),
            ],
        ),
    ),
)


example_record_audio_video = join(
    ModularPage(
        "record_page",
        AudioPrompt(
            # url="https://s3.amazonaws.com/headphone-check/antiphase_HC_ISO.wav",
            url="https://headphone-check.s3.amazonaws.com/funk_game_loop.wav",
            text="""
            This page plays audio and records video after a couple of seconds.
            It'll work best if you wear headphones.
            The red portion of the progress bar identifies the period when the video
            will be recording.
            Note how we overrode the 'trialPrepare' event, meaning that the
            trial does not start itself automatically;
            instead the trial only starts once the user explicitly presses the
            'Start recording' button.
            """,
            play_window=[0, 4.6],
            fade_in=0.2,
        ),
        VideoRecordControl(
            duration=2.0,
            s3_bucket="audio-record-demo",
            recording_source="camera",
            show_preview=True,
            show_meter=False,
            public_read=True,
            controls=True,
            loop_playback=False,
            auto_advance=True,
        ),
        progress_display=ProgressDisplay(
            duration=4.6,
            stages=[
                ProgressStage([0.0, 2.6], "Waiting to record...", color="grey"),
                ProgressStage([2.6, 4.0], "Recording!", color="red"),
                ProgressStage([4.0, 4.6], "Recording finished.", color="green"),
            ],
        ),
        events={
            "trialPrepare": Event(is_triggered_by=None),
            "audioStart": Event(is_triggered_by="trialStart", delay=0.0),
            "recordStart": Event(is_triggered_by="trialStart", delay=2.6),
        },
        time_estimate=5,
    ),
    PageMaker(
        lambda participant: ModularPage(
            "playback",
            VideoPrompt(
                participant.answer["camera_url"], "Here's the recording you just made."
            ),
            # You can alternatively use an AudioPrompt here to play back just the
            # audio component of the recording.
            # AudioPrompt(
            #     participant.answer["camera_url"], "Here's the recording you just made."
            # ),
        ),
        time_estimate=5,
    ),
)


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        MTurkStandardConsent(),
        MTurkAudiovisualConsent(),
        example_js_synth_1,
        example_js_synth_2,
        example_js_synth_3,
        example_js_synth_4,
        example_audio_page,
        example_audio_page_2,
        example_audio_page_3,
        example_audio_meter,
        example_record_page,
        example_listen_then_record_page,
        example_record_audio_video,
        example_audio_meter_calibrate_with_audio,
        example_audio_meter_calibrate_with_tapping,
        example_preloading,
        SuccessfulEndPage(),
    )
