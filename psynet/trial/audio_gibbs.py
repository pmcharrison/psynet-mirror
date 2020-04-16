# pylint: disable=unused-argument,abstract-method

from dallinger import db
from .gibbs import GibbsNetwork, GibbsTrialMaker, GibbsTrial, GibbsNode, GibbsSource
from ..field import claim_var
from ..media import make_batch_file, upload_to_s3
from ..utils import get_object_from_module, log_time_taken

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

    Attributes
    ----------

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

    vector_length = 0
    vector_ranges = []
    vector_granularity = 100

    def validate(self):
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
    __mapper_args__ = {"polymorphic_identity": "audio_gibbs_trial"}

    def show_trial(self, experiment, participant):
        return AudioSliderPage(
            "gibbs_audio_trial",
            self.get_prompt(experiment, participant),
            starting_values=self.initial_vector,
            reverse_scale=self.reverse_scale,
            time_estimate=5
        )

    def get_prompt(self, experiment, participant):
        raise NotImplementedError

    @property
    def slider_stimuli(self):
        return self.origin.slider_stimuli


class AudioGibbsNode(GibbsNode):
    """
    A Node class for Audio Gibbs sampler chains.
    """
    __mapper_args__ = {"polymorphic_identity": "audio_gibbs_node"}

    slider_stimuli = claim_var("slider_stimuli")

class AudioGibbsSource(GibbsSource):
    """
    A Source class for Audio Gibbs sampler chains.
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
            "network_definition": network.definition,
            "output_dir": individual_stimuli_dir,
            "synth_function": get_object_from_module(**network.synth_function)
        }

        if granularity == "custom":
            stimuli = make_audio_custom_intervals(**args)
        else:
            stimuli = make_audio_regular_intervals(granularity=granularity, **args)

        batch_stimulus_ids = make_audio_batch_file(stimuli, batch_path)
        batch_url = upload_to_s3(batch_path, network.s3_bucket, batch_file)

        node.slider_stimuli = {
            "url": batch_url,
            "ids": batch_stimulus_ids,
            "type": "batch"
        }

        network.awaiting_process = False

        # pylint: disable=no-member
        db.session.commit()

def make_audio_batch_file(stimuli, output_path):
    stimulus_ids = []
    paths = []
    for _stimulus_id, _contents in stimuli.items():
        _path = _contents["path"]
        stimulus_ids.append(_stimulus_id)
        paths.append(_path)
    make_batch_file(paths, output_path)
    return stimulus_ids

def make_audio_regular_intervals(
    granularity,
    vector,
    active_index,
    range_to_sample,
    network_definition,
    output_dir,
    synth_function
):
    stimuli = {}
    for _i, _value in enumerate(range(range_to_sample[0], range_to_sample[1], granularity)):
        _vector = vector.copy()
        _vector[active_index] = _value
        _id = f"stimulus_{_i}"
        _file = f"{_id}.wav"
        _path = os.path.join(output_dir, _file)
        synth_function(vector=_vector, output_path=_path, network_definition=network_definition)

        stimuli[_id] = {"value": _value, "path": _path}
    return stimuli

def make_audio_custom_intervals(vector, active_index, range_to_sample, network_definition, output_dir, synth_function):
    raise NotImplementedError
