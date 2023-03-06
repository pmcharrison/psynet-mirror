# pylint: disable=unused-argument,abstract-method

from ..utils import get_logger
from .record import (
    MediaImitationChainNetwork,
    MediaImitationChainNode,
    MediaImitationChainTrial,
    MediaImitationChainTrialMaker,
    RecordTrial,
)

logger = get_logger()


class CameraRecordTrial(RecordTrial):
    __extra_vars__ = {}

    recording_url_key_name = "camera_url"
    recording_key_name = "camera_key"


class ScreenRecordTrial(RecordTrial):
    __extra_vars__ = {}

    recording_url_key_name = "screen_url"
    recording_key_name = "screen_key"


class CameraImitationChainNetwork(MediaImitationChainNetwork):
    """
    A Network class for camera imitation chains.
    """

    media_extension = ".webm"


class CameraImitationChainTrial(CameraRecordTrial, MediaImitationChainTrial):
    """
    A Trial class for camera imitation chains.
    The user must override
    :meth:`~psynet.trial.video_imitation_chain.analyze_recording` and
    :meth:`~psynet.trial.video_imitation_chain.show_trial`.
    """

    pass


class CameraImitationChainNode(MediaImitationChainNode):
    """
    A Node class for camera imitation chains.
    Users must override the
    :meth:`~psynet.trial.audio.VideoImitationChainNode.synthesize_target` method.
    """

    media_extension = ".webm"


class CameraImitationChainTrialMaker(MediaImitationChainTrialMaker):
    """
    A TrialMaker class for camera imitation chains;
    see the documentation for
    :class:`~psynet.trial.chain.ChainTrialMaker`
    for usage instructions.
    """

    @property
    def default_network_class(self):
        return CameraImitationChainNetwork
