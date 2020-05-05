# pylint: disable=unused-import,abstract-method,unused-argument,no-member

# Note: parselmouth must be installed with pip install praat-parselmouth

##########################################################################################
# Imports
##########################################################################################

from random import random
import psynet.experiment
from psynet.headphone import headphone_check
from psynet.timeline import (
    Timeline,
    CodeBlock,
    conditional,
    join
)
from psynet.page import (
    Page,
    InfoPage,
    NumberInputPage,
    NAFCPage,
    SuccessfulEndPage,
    VolumeCalibration,
)
from psynet.trial.audio_gibbs import (
    AudioGibbsNetwork, AudioGibbsTrial, AudioGibbsNode, AudioGibbsSource, AudioGibbsTrialMaker
)

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

from flask import Markup

import os
import json


def get_template(name):
    assert isinstance(name, str)
    data_path = os.path.join('templates', name)
    with open(data_path, encoding='utf-8') as fp:
        template_str = fp.read()
    return template_str


class LanguagePage(Page):
    """
        This page solicits a text response from the user.
        By default this response is saved in the database as a
        :class:`psynet.timeline.Response` object,
        which can be found in the ``Questions`` table.

        Parameters
        ----------

        label:
            Internal label for the page (used to store results).

        prompt:
            Prompt to display to the user. Use :class:`flask.Markup`
            to display raw HTML.

        time_estimate:
            Time estimated for the page.

        **kwargs:
            Further arguments to pass to :class:`psynet.timeline.Page`.
        """

    def __init__(
            self,
            label: str,
            prompt: str,
            time_estimate: float,
            **kwargs
    ):
        self.prompt = prompt
        with open('languages.json', 'r') as f:
            languages = json.load(f)
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("language-input-page.html"),
            label=label,
            template_arg={
                "prompt": prompt,
                "languages": languages
            },
            **kwargs
        )

    def metadata(self, **kwargs):
        # pylint: disable=unused-argument
        return {
            "prompt": self.prompt
        }


# Custom parameters, change these as you like!
DIMENSIONS = 5
# SD = round(267*2.2)
SD = 600
RANGE = [-SD, SD]
NUMBER_OF_SLIDER_TICKS = 120
NUM_TRAILS_PER_CHAIN = 10
SNAP_SLIDER = True
AUTOPLAY = True
MIN_DURATION = 5
DEBUG = False


class CriticismNetwork(AudioGibbsNetwork):
    __mapper_args__ = {"polymorphic_identity": "criticism_network"}

    synth_function_location = {
        "module_name": "custom_synth",
        "function_name": "synth_stimulus"
    }

    s3_bucket = "audio-gibbs-demo"
    vector_length = DIMENSIONS
    vector_ranges = [RANGE for _ in range(DIMENSIONS)]
    granularity = NUMBER_OF_SLIDER_TICKS

    def make_definition(self):
        return {"target": 'criticism'}


class SuggestionNetwork(AudioGibbsNetwork):
    __mapper_args__ = {"polymorphic_identity": "suggestion_network"}

    synth_function_location = {
        "module_name": "custom_synth",
        "function_name": "synth_stimulus"
    }

    s3_bucket = "audio-gibbs-demo"
    vector_length = DIMENSIONS
    vector_ranges = [RANGE for _ in range(DIMENSIONS)]
    granularity = NUMBER_OF_SLIDER_TICKS

    def make_definition(self):
        return {"target": 'suggestion'}


class SuggestionTrial(AudioGibbsTrial):
    __mapper_args__ = {"polymorphic_identity": "suggestion_trial"}

    debug = DEBUG
    snap_slider = SNAP_SLIDER
    autoplay = AUTOPLAY
    minimal_time = MIN_DURATION

    def choose_reverse_scale(self):
        return False

    def get_prompt(self, experiment, participant):
        return Markup(
            "Adjust the slider so that the word sounds most like "
            f"<strong>{self.network.definition['target']}</strong>."
        )


class CriticismTrial(AudioGibbsTrial):
    __mapper_args__ = {"polymorphic_identity": "criticsm_trial"}

    debug = DEBUG
    snap_slider = SNAP_SLIDER
    autoplay = AUTOPLAY
    minimal_time = MIN_DURATION

    def choose_reverse_scale(self):
        return False

    def get_prompt(self, experiment, participant):
        return Markup(
            "Adjust the slider so that the word sounds most like "
            f"<strong>{self.network.definition['target']}</strong>."
        )


class CustomNode(AudioGibbsNode):
    __mapper_args__ = {"polymorphic_identity": "custom_node"}


class CustomSource(AudioGibbsSource):
    __mapper_args__ = {"polymorphic_identity": "custom_source"}


def make_instructions(target, initial=False):
    with open("instructions/%s.html" % target, "r") as f:
        text = f.read()
    context = InfoPage(Markup(text), time_estimate=3)
    if initial:
        return InfoPage(Markup("Let's start with %s: <br><br>" % target + text + "<br><br> We will start with an example."), time_estimate=3)
    else:
        return context


def make_block(target, phase="experiment"):
    if target == 'suggestion':
        network_class = SuggestionNetwork
        trial_class = SuggestionTrial
    elif target == 'criticism':
        network_class = CriticismNetwork
        trial_class = CriticismTrial
    else:
        raise NotImplementedError()

    if phase == 'experiment':
        num_chains_per_participant = 3
        num_nodes_per_chain = NUM_TRAILS_PER_CHAIN + 1
        num_trials_per_participant = (num_nodes_per_chain + 1) * num_chains_per_participant
    else:
        num_trials_per_participant = 2
        num_nodes_per_chain = 2
        num_chains_per_participant = 1

    trial_maker = AudioGibbsTrialMaker(
        network_class=network_class,
        trial_class=trial_class,
        node_class=CustomNode,
        source_class=CustomSource,
        phase=phase,  # can be whatever you like
        time_estimate_per_trial=5,
        chain_type="within",  # can be "within" or "across"
        num_trials_per_participant=num_trials_per_participant,
        num_nodes_per_chain=num_nodes_per_chain,
        num_chains_per_participant=num_chains_per_participant,  # set to None if chain_type="across"
        num_chains_per_experiment=None,  # set to None if chain_type="within"
        trials_per_node=1,
        active_balancing_across_chains=True,
        check_performance_at_end=False,
        check_performance_every_trial=False,
        propagate_failure=False,
        recruit_mode="num_participants",
        target_num_participants=10
    )
    return trial_maker


##########################################################################################
# Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    with open("instructions/instructions.html", "r") as f:
        instruction_text = f.read()

    timeline = Timeline(
        # Perform volume check
        VolumeCalibration(),
        headphone_check(),

        # Demographic data
        NumberInputPage(
            label='age',
            prompt='What is your age?',
            time_estimate=2
        ),
        NAFCPage(
            label='gender',
            prompt='With what gender do you most identify yourself?',
            time_estimate=2,
            choices=['male', 'female', 'other']
        ),
        NAFCPage(
            label='education',
            prompt='What is your highest educational qualification?',
            time_estimate=2,
            choices=['none', 'elementary school', 'middle school', 'high school', 'bachelor', 'master', 'PhD']
        ),
        LanguagePage(
            'daily_language',
            'Which language(s) do you most frequently speak in your daily life?',
            time_estimate=2
        ),
        LanguagePage(
            'child_language',
            'Which language(s) did you speak during childhood?',
            time_estimate=2
        ),

        # Instructions
        InfoPage(
            Markup(instruction_text),
            time_estimate=3
        ),


        # Main experiment
        CodeBlock(lambda experiment, participant: participant.var.set("suggestion_first", round(random()) == 1)),
        conditional(
            "main_block",
            lambda experiment, participant: participant.var.suggestion_first,
            join(
                make_instructions("suggestion", initial=True),
                # Practice trials
                make_block("suggestion", phase="training"),
                InfoPage(Markup('You will now start the experiment.'), time_estimate=3),
                make_block("suggestion"),
                InfoPage(Markup("You did very well. Let's continue with criticism."), time_estimate=3),
                make_instructions("criticism"),
                make_block("criticism"),
            ),
            join(
                make_instructions("criticism", initial=True),
                # Practice trials
                make_block("criticism", phase="training"),
                InfoPage(Markup('You will now start the experiment.'), time_estimate=3),
                make_block("criticism"),
                InfoPage(Markup("You did very well. Let's continue with suggestion."), time_estimate=3),
                make_instructions("suggestion"),
                make_block("suggestion"),
            ),
            fix_time_credit=False
        ),
        SuccessfulEndPage()
    )

    def __init__(self, session=None):
        super().__init__(session)
        # Change this if you want to simulate multiple simultaneous participants.
        self.initial_recruitment_size = 1


extra_routes = Exp().extra_routes()
