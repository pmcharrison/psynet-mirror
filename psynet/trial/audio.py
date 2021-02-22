# pylint: disable=unused-argument,abstract-method

import os
import tempfile
from uuid import uuid4

import dominate.tags as tags
from dallinger import db

from ..field import claim_var, extra_var
from ..media import download_from_s3, get_s3_url, recode_wav, upload_to_s3
from ..utils import get_logger
from .imitation_chain import (
    ImitationChainNetwork,
    ImitationChainNode,
    ImitationChainSource,
    ImitationChainTrial,
    ImitationChainTrialMaker,
)

logger = get_logger()


class AudioRecordTrial:
    __extra_vars__ = {}

    run_async_post_trial = True
    analysis = claim_var("analysis", __extra_vars__)

    @property
    def recording_info(self):
        answer = self.answer
        if answer is None:
            return None
        try:
            return {
                "s3_bucket": answer["s3_bucket"],
                "key": answer["key"],
                "url": answer["url"],
            }
        except KeyError as e:
            raise KeyError(
                str(e) + " Did the trial include an AudioRecordControl, as required?"
            )

    @property
    @extra_var(__extra_vars__)
    def has_recording(self):
        return self.recording_info is not None

    @property
    @extra_var(__extra_vars__)
    def audio_url(self):
        if self.has_recording:
            return self.recording_info["url"]

    @property
    @extra_var(__extra_vars__)
    def plot_key(self):
        if self.has_recording:
            base = os.path.splitext(self.recording_info["key"])[0]
            return base + ".png"

    @property
    @extra_var(__extra_vars__)
    def s3_bucket(self):
        if self.has_recording:
            return self.recording_info["s3_bucket"]

    @property
    @extra_var(__extra_vars__)
    def plot_url(self):
        if self.has_recording:
            return get_s3_url(self.s3_bucket, self.plot_key)

    @property
    def visualization_html(self):
        html = super().visualization_html
        if self.has_recording:
            html += tags.div(
                tags.img(src=self.plot_url, style="max-width: 100%;"),
                style="border-style: solid; border-width: 1px;",
            ).render()
        return html

    def async_post_trial(self):
        logger.info("Analysing recording for trial %i...", self.id)
        with tempfile.NamedTemporaryFile() as temp_recording:
            with tempfile.NamedTemporaryFile() as temp_plot:
                self.download_recording(temp_recording.name)
                recode_wav(temp_recording.name)
                self.analysis = self.analyse_recording(
                    temp_recording.name, temp_plot.name
                )
                if not (
                    "no_plot_generated" in self.analysis
                    and self.analysis["no_plot_generated"]
                ):
                    self.upload_plot(temp_plot.name)
                try:
                    if self.analysis["failed"]:
                        self.fail()
                except KeyError:
                    raise KeyError(
                        "The recording analysis failed to contain a 'failed' attribute."
                    )
                finally:
                    db.session.commit()

    def download_recording(self, local_path):
        recording_info = self.recording_info
        download_from_s3(local_path, recording_info["s3_bucket"], recording_info["key"])

    def upload_plot(self, local_path):
        upload_to_s3(
            local_path,
            self.recording_info["s3_bucket"],
            self.plot_key,
            public_read=True,
        )

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
            The following optional terms are also recognised by PsyNet:

            - ``no_plot_generated``: Set this to ``True`` if the function did not generate any output plot,
              and this will tell PsyNet not to try uploading the output plot to S3.
              The default value (i.e. the assumed value if no value is provided) is ``False``.
        """
        raise NotImplementedError


class AudioImitationChainNetwork(ImitationChainNetwork):
    """
    A Network class for audio imitation chains.
    """

    __mapper_args__ = {"polymorphic_identity": "audio_imitation_chain_network"}

    s3_bucket = ""

    def validate(self):
        if self.s3_bucket == "":
            raise ValueError(
                "The AudioImitationChainNetwork must possess a valid s3_bucket attribute."
            )

    run_async_post_grow_network = True

    def async_post_grow_network(self):
        logger.info("Synthesising audio for network %i...", self.id)

        node = self.head

        if isinstance(node, AudioImitationChainSource):
            logger.info(
                "Network %i only contains a Source, no audio to be synthesised.",
                self.id,
            )
        else:
            with tempfile.NamedTemporaryFile() as temp_file:
                node.synthesise_target(temp_file.name)
                recode_wav(temp_file.name)
                target_key = f"{uuid4()}.wav"
                node.target_url = upload_to_s3(
                    temp_file.name,
                    self.s3_bucket,
                    key=target_key,
                    public_read=True,
                    create_new_bucket=True,
                )["url"]


class AudioImitationChainTrial(AudioRecordTrial, ImitationChainTrial):
    """
    A Trial class for audio imitation chains.
    The user must override
    :meth:`~psynet.trial.audio_imitation_chain.analyse_recording`.
    """

    __mapper_args__ = {"polymorphic_identity": "audio_imitation_chain_trial"}
    __extra_vars__ = {
        **AudioRecordTrial.__extra_vars__,
        **ImitationChainTrial.__extra_vars__,
    }


class AudioImitationChainNode(ImitationChainNode):
    """
    A Node class for audio imitation chains.
    Users must override the
    :meth:`~psynet.trial.audio.AudioImitationChainNode.synthesise_target` method.
    """

    __mapper_args__ = {"polymorphic_identity": "audio_imitation_chain_node"}
    __extra_vars__ = ImitationChainNode.__extra_vars__.copy()

    target_url = claim_var("target_url", __extra_vars__)

    def synthesise_target(self, output_file):
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
