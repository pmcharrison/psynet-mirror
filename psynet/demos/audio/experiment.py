# This is a minimal experiment implementation for prototyping the monitor route.
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
    conditional
)
from psynet.page import (
    InfoPage, 
    SuccessfulEndPage, 
    NAFCPage, 
    TextInputPage
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

from datetime import datetime

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        InfoPage(
            flask.Markup(
                f"""
                <p>Welcome to the demo!</p>
                <p>
                    This page demonstrates audio preloading.
                    A progress bar fills up on the bottom of the screen
                    as the audio files are loaded into the client's browser.
                    Once these audio files are loaded, you can access them programmatically.
                </p>
                <ul>
                    <li> <a onclick="psynet.audio.bier.play();">Play 'bier'.</a></li>
                    <li> <a onclick="psynet.audio.bier.stop();">Stop 'bier'.</a></li>
                </ul>
                <ul>
                    <li> <a onclick="psynet.audio.funk_game_loop.play();">Play 'funk_game_loop'.</a></li>
                    <li> <a onclick="psynet.audio.funk_game_loop.stop();">Stop 'funk_game_loop'.</a></li>
                </ul>
                <ul>
                    <li> <a onclick="psynet.audio.honey_bee.play();">Play 'honey_bee'.</a></li>
                    <li> <a onclick="psynet.audio.honey_bee.stop();">Stop 'honey_bee'.</a></li>
                </ul>
                <ul>
                    <li> <a onclick="psynet.audio.there_it_is.play();">Play 'there_it_is'.</a></li>
                    <li> <a onclick="psynet.audio.there_it_is.stop();">Stop 'there_it_is'.</a></li>
                </ul>
                """
            ),
            time_estimate=5,
            media={
                "audio": {
                    'bier': '/static/audio/bier.wav',
                    'batch': {
                        'url': '/static/audio/file_concatenated.mp3',
                        'ids': ['funk_game_loop', 'honey_bee', 'there_it_is'],
                        'type': 'batch'
                    }
                }
            }
        ),
        SuccessfulEndPage()
    )

extra_routes = Exp().extra_routes()
