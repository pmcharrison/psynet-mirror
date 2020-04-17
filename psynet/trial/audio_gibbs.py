# pylint: disable=unused-argument,abstract-method

from dallinger import db
from .gibbs import GibbsNetwork, GibbsTrialMaker, GibbsTrial, GibbsNode, GibbsSource
from ..field import claim_var
from ..media import make_batch_file, upload_to_s3
from ..page import AudioSliderPage
from ..utils import get_object_from_module

import random
import os
import tempfile

from uuid import uuid4

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

# pylint: disable=unused-import
import rpdb

class AudioGibbsNetwork(GibbsNetwork):
    """
    A Network class for Audio Gibbs Sampler chains.
    The user should customise this by overriding the attributes
    :attr:`~psynet.trial.audio_gibbs.AudioGibbsNetwork.synth_function`,
    :attr:`~psynet.trial.audio_gibbs.AudioGibbsNetwork.vector_length`,
    :attr:`~psynet.trial.audio_gibbs.AudioGibbsNetwork.vector_ranges`,
    and optionally
    :attr:`~psynet.trial.audio_gibbs.AudioGibbsNetwork.granularity`.
    The user is also invited to override the
    :meth:`psynet.trial.chain.ChainNetwork.make_definition` method
    in situations where different chains are to have different properties
    (e.g. different prompts).

    Attributes
    ----------

    synth_function: dict
        A dictionary specifying the function to use for synthesising
        stimuli. The dictionary should contain two arguments:
        one named ``"module"``, which identifies by name the module
        in which the function is contained,
        and one named ``"name"``, corresponding to the name
        of the function within that module.
        The synthesis function should take three arguments:

            - ``vector``, the parameter vector for the stimulus to be generated.

            - ``output_path``, the output path for the audio file to be generated.

            - ``chain_definition``, the ``definition`` dictionary for the current chain.

    s3_bucket : str
        Name of the S3 bucket in which the stimuli should be stored.
        The same bucket can be reused between experiments,
        the UUID system used to generate file names should keep them unique.

    vector_length : int
        Must be overridden with the length of the free parameter vector
        that is manipulated during the Gibbs sampling procedure.

    vector_ranges : list
        Must be overridden with a list with length equal to
        :attr:`~psynet.trial.audio_gibbs.AudioGibbsNetwork.vector_length`.

    granularity : Union[int, str]
        When a new :class:`~psynet.trial.audio_gibbs.AudioGibbsNode`
        is created, a collection of stimuli are generated that
        span a given dimension of the parameter vector.
        If ``granularity`` is an integer, then this integer sets the number
        of stimuli that are generated, and the stimuli will be spaced evenly
        across the closed interval defined by the corresponding element of
        :attr:`~psynet.trial.audio_gibbs.AudioGibbsNetwork.vector_ranges`.
        If ``granularity`` is equal to ``"custom"``, then the spacing of the
        stimuli is instead determined by the audio generation function.
    """
    __mapper_args__ = {"polymorphic_identity": "audio_gibbs_network"}

    synth_function = {"module": "", "name": ""}
    s3_bucket = ""
    vector_length = 0
    vector_ranges = []
    granularity = 100

    def validate(self):
        if not (
            isinstance(self.synth_function, dict) and
            "module" in self.synth_function and
            "name" in self.synth_function and
            len(self.synth_function["module"]) > 0 and
            len(self.synth_function["name"]) > 0
            ):
            raise ValueError(f"Invalid <synth_function> ({self.synth_function}).")

        if not (isinstance(self.s3_bucket, chr) and len(self.s3_bucket) > 0):
            raise ValueError(f"Invalid <s3_bucket> ({self.s3_bucket}).")

        if not (isinstance(self.vector_length, int) and self.vector_length > 0):
            raise TypeError("<vector_length> must be a positive integer.")

        if not (isinstance(self.vector_ranges, list) and len(self.vector_ranges) == self.vector_length):
            raise TypeError("<vector_ranges> must be a list with length equal to <vector_length>.")

        for r in self.vector_ranges:
            if not (len(r) == 2 and r[0] < r[1]):
                raise ValueError(
                    "Each element of <vector_ranges> must be a list of two numbers in increasing order "
                    "identifying the legal range of the corresponding parameter in the vector."
                )

        if not (
            (isinstance(self.granularity, int) and self.granularity > 0)
            or (isinstance(self.granularity, str) and self.granularity == "custom")
        ):
            raise ValueError("<granularity> must be either a positive integer or the string 'custom'.")

    def random_sample(self, i):
        return random.uniform(
            self.vector_ranges[i][0],
            self.vector_ranges[i][1]
        )

class AudioGibbsTrial(GibbsTrial):
    """
    A Trial class for Audio Gibbs Sampler chains.
    The user should customise this by overriding the
    :meth:`~psynet.trial.audio_gibbs.AudioGibbsTrial.get_prompt`
    method.
    """

    __mapper_args__ = {"polymorphic_identity": "audio_gibbs_trial"}

    def show_trial(self, experiment, participant):
        return AudioSliderPage(
            "gibbs_audio_trial",
            self.get_prompt(experiment, participant),
            starting_values=self.initial_vector,
            reverse_scale=self.reverse_scale,
            time_estimate=5,
            media=self.get_media_spec(),
            sound_locations=self.get_sound_locations()
        )

    def get_media_spec(self):
        slider_stimuli = self.slider_stimuli
        return {
            "audio": {
                "slider_stimuli": {
                    "url": slider_stimuli["url"],
                    "ids": [x["id"] for x in slider_stimuli["all"]],
                    "type": "batch"
                }
            }
        }

    def get_sound_locations(self):
        res = {}
        for stimulus in self.slider_stimuli["all"]:
            res[stimulus["id"]] = stimulus["value"]
        return res

    def get_prompt(self, experiment, participant):
        """
        Constructs and returns the prompt to display to the participant.
        This can either be a string of text to display, or raw HTML.
        In the latter case, the HTML should be wrapped in a call to
        ``flask.Markup``.
        """
        raise NotImplementedError

    @property
    def slider_stimuli(self):
        return self.origin.slider_stimuli


class AudioGibbsNode(GibbsNode):
    """
    A Node class for Audio Gibbs sampler chains.
    The user should not have to modify this.
    """
    __mapper_args__ = {"polymorphic_identity": "audio_gibbs_node"}

    slider_stimuli = claim_var("slider_stimuli")

class AudioGibbsSource(GibbsSource):
    """
    A Source class for Audio Gibbs sampler chains.
    The user should not have to modify this.
    """
    __mapper_args__ = {"polymorphic_identity": "audio_gibbs_source"}

class AudioGibbsTrialMaker(GibbsTrialMaker):
    """
    A TrialMaker class for Audio Gibbs sampler chains;
    see the documentation for
    :class:`~psynet.trial.chain.ChainTrialMaker`
    for usage instructions.
    The primary differences is that
    :attr:`~psynet.trial.audio_gibbs.AudioGibbsTrialMaker.async_post_grow_network`
    is overwritten with a routine for synthesising audio.
    The user should only have to customise this through the
    constructor function parameters.
    """

    def __init__(self, **kwargs):
        super().__init__(
            async_post_grow_network="psynet.trial.audio_gibbs.make_audio",
            **kwargs
        )

def make_audio(network_id):
    logger.info("Synthesising audio for network %i...", network_id)
    network = AudioGibbsNetwork.query.filter_by(id=network_id).one()
    node = network.head

    granularity = network.granularity
    vector = node.definition["vector"]
    active_index = node.definition["active_index"]

    with tempfile.TemporaryDirectory() as temp_dir:
        individual_stimuli_dir = os.path.join(temp_dir, "individual_stimuli")
        os.mkdir(individual_stimuli_dir)

        batch_file = f"{uuid4()}.batch"
        batch_path = os.path.join(temp_dir, batch_file)

        args = {
            "vector": vector,
            "active_index": active_index,
            "range_to_sample": network.vector_ranges[active_index],
            "chain_definition": network.definition,
            "output_dir": individual_stimuli_dir,
            "synth_function": get_object_from_module(**network.synth_function)
        }

        if granularity == "custom":
            stimuli = make_audio_custom_intervals(**args)
        else:
            stimuli = make_audio_regular_intervals(granularity=granularity, **args)

        make_audio_batch_file(stimuli, batch_path)
        batch_url = upload_to_s3(batch_path, network.s3_bucket, batch_file)

        node.slider_stimuli = {
            "url": batch_url,
            "all": stimuli
        }

        network.awaiting_process = False

        # pylint: disable=no-member
        db.session.commit()

def make_audio_batch_file(stimuli, output_path):
    paths = [x["path"] for x in stimuli]
    make_batch_file(paths, output_path)

def make_audio_regular_intervals(
    granularity,
    vector,
    active_index,
    range_to_sample,
    chain_definition,
    output_dir,
    synth_function
):
    stimuli = []
    for _i, _value in enumerate(range(range_to_sample[0], range_to_sample[1], granularity)):
        _vector = vector.copy()
        _vector[active_index] = _value
        _id = f"slider_stimulus_{_i}"
        _file = f"{_id}.wav"
        _path = os.path.join(output_dir, _file)
        synth_function(vector=_vector, output_path=_path, chain_definition=chain_definition)

        stimuli.append({"id": _id, "value": _value, "path": _path})
    return stimuli

def make_audio_custom_intervals(vector, active_index, range_to_sample, chain_definition, output_dir, synth_function):
    raise NotImplementedError
