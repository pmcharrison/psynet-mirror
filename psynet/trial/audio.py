# pylint: disable=unused-argument,abstract-method

import os
import tempfile

from uuid import uuid4

from ..media import download_from_s3, upload_to_s3
from ..field import claim_field

from .main import Trial
from .imitation_chain import (
    ImitationChainNetwork,
    ImitationChainTrial,
    ImitationChainNode,
    ImitationChainSource,
    ImitationChainTrialMaker
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

class AudioRecordTrial(Trial):
    __mapper_args__ = {"polymorphic_identity": "audio_record_trial"}

    run_async_post_trial = True
    analysis = claim_field(5)

    @property
    def recording_info(self):
        answer = self.answer
        if answer is None:
            return None
        try:
            return {
                "s3_bucket": answer["s3_bucket"],
                "key": answer["key"],
                "url": answer["url"]
            }
        except KeyError as e:
            raise KeyError(str(e) + " Did the trial include an AudioRecordControl, as required?")

    @property
    def plot_key(self):
        base = os.path.splitext(self.recording_info["key"])[0]
        return base + ".png"

    def async_post_trial(self):
        with tempfile.NamedTemporaryFile() as temp_recording:
            with tempfile.NamedTemporaryFile() as temp_plot:
                self.download_recording(temp_recording.name)
                self.analysis = self.analyse_recording(temp_recording.name, temp_plot.name)
                self.upload_plot(temp_plot.name)
                try:
                    if self.analysis["failed"]:
                        self.fail()
                except KeyError:
                    raise KeyError("The recording analysis failed to contain a 'failed' attribute.")

    def download_recording(self, local_path):
        recording_info = self.recording_info
        download_from_s3(local_path, recording_info["s3_bucket"], recording_info["key"])

    def upload_plot(self, local_path):
        upload_to_s3(local_path, self.recording_info["s3_bucket"], self.plot_key, public_read=True)

    def analyse_recording(self, audio_file: str, output_plot: str):
        """
        Analyses the recording produced by the participant.

        Parameters
        ----------

        audio_file
            Path to the audio file to be analysed.

        output_plot
            Path to the output plot to be created.

        Returns
        -------

        dict :
            A dictionary of analysis information to be saved in the trial's ``analysis`` slot.
            This dictionary must include the boolean attribute ``failed``, determining
            whether the trial is to be failed.
        """
        raise NotImplementedError


class AudioImitationChainNetwork(ImitationChainNetwork):
    """
    A Network class for audio imitation chains.
    """
    __mapper_args__ = {"polymorphic_identity": "audio_imitation_chain_network"}

    run_async_post_grow_network = True

    def async_post_grow_network(self):
        logger.info("Synthesising audio for network %i...", self.id)

        node = self.head

        if isinstance(node, AudioImitationChainSource):
            logger.info("Network %i only contains a Source, no audio to be synthesised.", self.id)
        else:
            with tempfile.NamedTemporaryFile() as temp_file:
                node.synthesise_target(temp_file)
                target_key = f"{uuid4()}.wav"
                node.target_url = upload_to_s3(temp_file, self.s3_bucket, key=target_key, public_read=True)["url"]


class AudioImitationChainTrial(ImitationChainTrial, AudioRecordTrial):
    """
    A Trial class for audio imitation chains.
    The user must override
    :meth:`~psynet.trial.audio_imitation_chain.analyse_recording`.
    """

    __mapper_args__ = {"polymorphic_identity": "audio_imitation_chain_trial"}

class AudioImitationChainNode(ImitationChainNode):
    """
    A Node class for audio imitation chains.
    Users must override the
    :meth:`~psynet.trial.audio.AudioImitationChainNode.synthesise_target` method.
    """
    __mapper_args__ = {"polymorphic_identity": "audio_imitation_chain_node"}

    def synthesise_target(self, file):
        """
        Generates the target stimulus (i.e. the stimulus to be imitated by the participant).
        This method will typically rely on the ``self.definition`` attribute,
        which carries the definition of the current node.
        """
        raise NotImplementedError

class AudioImitationChainSource(ImitationChainSource):
    """
    A Source class for imitation chains.
    """
    __mapper_args__ = {"polymorphic_identity": "audio_imitation_chain_source"}

class AudioImitationChainTrialMaker(ImitationChainTrialMaker):
    """
    A TrialMaker class for audio imitation chains;
    see the documentation for
    :class:`~psynet.trial.chain.ChainTrialMaker`
    for usage instructions.
    """