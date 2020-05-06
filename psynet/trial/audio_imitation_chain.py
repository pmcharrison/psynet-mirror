# pylint: disable=unused-argument,abstract-method

import os
import tempfile

from ..media import download_from_s3, upload_to_s3
from ..field import claim_field
from .imitation_chain import ImitationChainNetwork, ImitationChainTrial, ImitationChainNode, ImitationChainSource, ImitationChainTrialMaker

class AudioImitationChainNetwork(ImitationChainNetwork):
    """
    A Network class for audio imitation chains.
    """
    __mapper_args__ = {"polymorphic_identity": "audio_imitation_chain_network"}

class AudioImitationChainTrial(ImitationChainTrial):
    """
    A Trial class for audio imitation chains.
    The user must override
    :meth:`~psynet.trial.audio_imitation_chain.analyse_recording`.
    """

    __mapper_args__ = {"polymorphic_identity": "audio_imitation_chain_trial"}

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
            A dictionary of analysis information.
        """
        raise NotImplementedError

class AudioImitationChainNode(ImitationChainNode):
    """
    A Node class for audio imitation chains.
    """
    __mapper_args__ = {"polymorphic_identity": "audio_imitation_chain_node"}

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