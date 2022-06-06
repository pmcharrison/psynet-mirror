# pylint: disable=unused-argument,abstract-method

from ..media import recode_wav
from ..utils import get_logger
from .record import (
    MediaImitationChainNetwork,
    MediaImitationChainNode,
    MediaImitationChainSource,
    MediaImitationChainTrial,
    MediaImitationChainTrialMaker,
    RecordTrial,
)

logger = get_logger()


class AudioRecordTrial(RecordTrial):
    __extra_vars__ = {}

    recording_url_key_name = "url"
    recording_key_name = "key"

    def sanitize_recording(self, path):
        recode_wav(path)


class AudioImitationChainNetwork(MediaImitationChainNetwork):
    """
    A Network class for audio imitation chains.
    """

    media_extension = "wav"


class AudioImitationChainTrial(AudioRecordTrial, MediaImitationChainTrial):
    """
    A Trial class for audio imitation chains.
    The user must override
    :meth:`~psynet.trial.audio_imitation_chain.analyze_recording` and
    :meth:`~psynet.trial.audio_imitation_chain.show_trial`.
    """

    pass


class AudioImitationChainNode(MediaImitationChainNode):
    """
    A Node class for audio imitation chains.
    Users must override the
    :meth:`~psynet.trial.audio.AudioImitationChainNode.synthesize_target` method.
    """

    pass


class AudioImitationChainSource(MediaImitationChainSource):
    """
    A Source class for audio imitation chains.
    """

    pass


class AudioImitationChainTrialMaker(MediaImitationChainTrialMaker):
    """
    A TrialMaker class for audio imitation chains;
    see the documentation for
    :class:`~psynet.trial.chain.ChainTrialMaker`
    for usage instructions.
    """
