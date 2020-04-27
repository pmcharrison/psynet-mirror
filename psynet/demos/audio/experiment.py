import flask

import dallinger.deployment
from dallinger.models import Info, Node, Transformation
from dallinger.networks import Chain
from dallinger.nodes import Source

import psynet.experiment
from psynet.timeline import (
    Timeline,
    PageMaker,
    CodeBlock,
    while_loop,
    conditional,
    MediaSpec
)
from psynet.page import (
    InfoPage,
    SuccessfulEndPage,
    NAFCPage,
    TextInputPage
)
from psynet.modular_page import(
    ModularPage,
    AudioMeterControl,
    AudioPrompt
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

from datetime import datetime

example_preloading = InfoPage(
    flask.Markup(
        f"""
        <p>Welcome to the demo!</p>
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
            'bier': '/static/audio/bier.wav',
            'batch': {
                'url': '/static/audio/file_concatenated.mp3',
                'ids': ['funk_game_loop', 'honey_bee', 'there_it_is'],
                'type': 'batch'
            }
        }
    ),
    css=[
        """
        .btn {
            margin: 2px
        }
        """
    ]
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
            'bier': '/static/audio/bier.wav',
            'batch': {
                'url': '/static/audio/file_concatenated.mp3',
                'ids': ['funk_game_loop', 'honey_bee', 'there_it_is'],
                'type': 'batch'
            }
        }
    ),
    scripts=[
        """
        psynet.media.register_on_loaded_routine(function() {
            alert("Media has finished loading!");
        });
        """
    ]
)

example_audio_meter = ModularPage(
    "audio_meter",
    "This page shows an audio meter.",
    AudioMeterControl(),
    time_estimate=5
)

example_audio_meter_with_audio = ModularPage(
    "audio_meter",
    AudioPrompt(
        "/static/audio/train1.wav",
        "This page shows an audio meter alongside an audio stimulus.",
        loop=True,
        enable_response_after=2.5
    ),
    AudioMeterControl(min_time=2.5),
    time_estimate=5
)

example_audio_page = ModularPage(
    "audio_page",
    AudioPrompt(
        "/static/audio/bier.wav",
        "This page illustrates a simple audio page with one stimulus."
    ),
    time_estimate=5
)

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        example_audio_meter,
        example_audio_meter_with_audio,
        example_audio_page,
        example_preloading,
        example_on_loaded,
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
