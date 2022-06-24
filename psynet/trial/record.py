import os
import tempfile
from uuid import uuid4

import dominate.tags as tags
from dallinger import db

from ..field import claim_var, extra_var
from ..media import download_from_s3, get_s3_url, upload_to_s3
from ..utils import get_logger
from .imitation_chain import (
    ImitationChainNetwork,
    ImitationChainNode,
    ImitationChainSource,
    ImitationChainTrial,
    ImitationChainTrialMaker,
)

logger = get_logger()


class RecordTrial:
    __extra_vars__ = {}

    run_async_post_trial = True
    analysis = claim_var("analysis", __extra_vars__)
    recording_url_key_name = None
    recording_key_name = None

    @property
    def media_answer(self):
        if isinstance(self.answer, list):  # multipage
            for a in self.answer:
                try:
                    if a["supports_record_trial"]:
                        return a
                except (KeyError, TypeError) as e:  # noqa
                    continue
        else:
            return self.answer

    @property
    def recording_info(self):
        answer = self.media_answer
        if answer is None:
            return None
        try:
            return {
                "s3_bucket": answer["s3_bucket"],
                "key": answer[self.recording_key_name],
                "url": answer[self.recording_url_key_name],
            }
        except KeyError as e:
            raise KeyError(
                str(e)
                + " Did the trial include an AudioRecordControl or VideoRecordControl, as required?"
            )

    @property
    @extra_var(__extra_vars__)
    def has_recording(self):
        return self.recording_info is not None

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
    @extra_var(__extra_vars__)
    def recording_url(self):
        if self.has_recording:
            return self.recording_info["url"]

    @property
    def visualization_html(self):
        html = super().visualization_html
        if self.has_recording:
            html += tags.div(
                tags.img(src=self.plot_url, style="max-width: 100%;"),
                style="border-style: solid; border-width: 1px;",
            ).render()
        return html

    def sanitize_recording(self, path):
        pass

    def async_post_trial(self):
        logger.info("Analyzing recording for trial %i...", self.id)
        with tempfile.NamedTemporaryFile() as temp_recording:
            with tempfile.NamedTemporaryFile() as temp_plot:
                self.download_recording(temp_recording.name)
                self.sanitize_recording(temp_recording.name)
                self.analysis = self.analyze_recording(
                    temp_recording.name, temp_plot.name
                )
                if not (
                    "no_plot_generated" in self.analysis
                    and self.analysis["no_plot_generated"]
                ):
                    self.upload_plot(temp_plot.name)
                try:
                    if self.analysis["failed"]:
                        self.fail(reason="analysis")
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

    def analyze_recording(self, audio_file: str, output_plot: str):
        """
        Analyzes the recording produced by the participant.

        Parameters
        ----------

        audio_file
            Path to the audio file to be analyzed.

        output_plot
            Path to the output plot to be created.

        Returns
        -------

        dict :
            A dictionary of analysis information to be saved in the trial's ``analysis`` slot.
            This dictionary must include the boolean attribute ``failed``, determining
            whether the trial is to be failed.
            The following optional terms are also recognized by PsyNet:

            - ``no_plot_generated``: Set this to ``True`` if the function did not generate any output plot,
              and this will tell PsyNet not to try uploading the output plot to S3.
              The default value (i.e. the assumed value if no value is provided) is ``False``.
        """
        raise NotImplementedError


class MediaImitationChainNetwork(ImitationChainNetwork):
    """
    A Network class for media imitation chains.
    """

    s3_bucket = ""

    media_extension = None

    def validate(self):
        if self.s3_bucket == "":
            raise ValueError(
                "The MediaImitationChainNetwork must possess a valid s3_bucket attribute."
            )

    run_async_post_grow_network = True

    def async_post_grow_network(self):
        logger.info("Synthesizing media for network %i...", self.id)

        node = self.head

        if isinstance(node, MediaImitationChainSource):
            logger.info(
                "Network %i only contains a Source, no media to be synthesized.",
                self.id,
            )
        else:
            with tempfile.NamedTemporaryFile() as temp_file:
                node.synthesize_target(temp_file.name)
                target_key = f"{uuid4()}.{self.media_extension}"
                node.target_url = upload_to_s3(
                    temp_file.name,
                    self.s3_bucket,
                    key=target_key,
                    public_read=True,
                    create_new_bucket=True,
                )["url"]


class MediaImitationChainTrial(RecordTrial, ImitationChainTrial):
    """
    A Trial class for media imitation chains.
    The user must override
    :meth:`~psynet.trial.MediaImitationChainTrial.analyze_recording`.
    """

    __extra_vars__ = {
        **RecordTrial.__extra_vars__,
        **ImitationChainTrial.__extra_vars__,
    }


class MediaImitationChainNode(ImitationChainNode):
    """
    A Node class for media imitation chains.
    Users must override the
    :meth:`~psynet.trial.audio.MediaImitationChainNode.synthesize_target` method.
    """

    __extra_vars__ = ImitationChainNode.__extra_vars__.copy()

    target_url = claim_var("target_url", __extra_vars__)

    def synthesize_target(self, output_file):
        """
        Generates the target stimulus (i.e. the stimulus to be imitated by the participant).
        This method will typically rely on the ``self.definition`` attribute,
        which carries the definition of the current node.
        """
        raise NotImplementedError


class MediaImitationChainSource(ImitationChainSource):
    """
    A Source class for media imitation chains.
    """

    pass


class MediaImitationChainTrialMaker(ImitationChainTrialMaker):
    """
    A TrialMaker class for media imitation chains;
    see the documentation for
    :class:`~psynet.trial.chain.ChainTrialMaker`
    for usage instructions.
    """
