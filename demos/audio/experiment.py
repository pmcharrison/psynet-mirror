import flask

import psynet.experiment
from psynet.modular_page import (
    AudioMeterControl,
    AudioPrompt,
    AudioRecordControl,
    ModularPage,
    TappingAudioMeterControl,
)
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import MediaSpec, PageMaker, Timeline, join
from psynet.utils import get_logger

logger = get_logger()

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

example_on_loaded = InfoPage(
    flask.Markup(
        """
        <p>
            This page demonstrates the use of the media on_loaded routine,
            whereby you can register a function to be called once
            the page's media has finished loading.
            Here, we make an 'alert' box appear.
        </p>
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
    scripts=[
        """
        psynet.media.register_on_loaded_routine(function() {
            alert("Media has finished loading!");
        });
        """
    ],
)

example_audio_meter = ModularPage(
    "audio_meter",
    "This page shows an audio meter.",
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
        enable_submit_after=0,
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
        enable_submit_after=2.5,
    ),
    AudioMeterControl(min_time=2.5, calibrate=True),
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
    ),
    time_estimate=5,
)

example_audio_page_2 = ModularPage(
    "audio_page",
    AudioPrompt(
        "/static/audio/train1.wav",
        "This page illustrates a play window combined with a loop.",
        play_window=[5, 9],
        loop=True,
        enable_submit_after=2,
    ),
    time_estimate=5,
)

example_record_page = join(
    ModularPage(
        "record_page",
        "This page lets you record audio.",
        AudioRecordControl(
            duration=3.0,
            s3_bucket="audio-record-demo",
            show_meter=True,
            public_read=True,
        ),
        time_estimate=5,
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

example_record_with_audio_prompt = join(
    ModularPage(
        "record_page",
        AudioPrompt(
            # url="https://s3.amazonaws.com/headphone-check/antiphase_HC_ISO.wav",
            url="https://headphone-check.s3.amazonaws.com/funk_game_loop.wav",
            text="This page enables the recorder and plays the audio 0.5 seconds later.",
            prevent_response=False,
            start_delay=0.5,
            enable_submit_after=5.5,
        ),
        AudioRecordControl(
            duration=5.0,
            s3_bucket="audio-record-demo",
            show_meter=True,
            public_read=True,
        ),
        time_estimate=5,
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


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        example_audio_page,
        example_audio_page_2,
        example_record_with_audio_prompt,
        example_record_page,
        example_audio_meter,
        example_audio_meter_calibrate_with_audio,
        example_audio_meter_calibrate_with_tapping,
        example_preloading,
        example_on_loaded,
        SuccessfulEndPage(),
    )


extra_routes = Exp().extra_routes()
