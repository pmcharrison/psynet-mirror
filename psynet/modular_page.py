from flask import Markup
from typing import Union, Optional

from .page import (
    Page,
    MediaSpec
)

class Prompt():
    @property
    def macro(self):
        raise NotImplementedError

    @property
    def metadata(self):
        raise NotImplementedError

class AudioPrompt():
    def __init__(self, url: str, text: Union[str, Markup]):
        self.text = text
        self.url = url

    macro = "audio_prompt"

    @property
    def metadata(self):
        return {
            "url": self.url
        }

class Control():
    @property
    def macro(self):
        raise NotImplementedError

    @property
    def metadata(self):
        raise NotImplementedError

    def format_answer(self, raw_answer, **kwargs):
        """
        Formats the raw answer object returned from the participant's browser.

        Parameters
        ----------

        raw_answer
            The raw answer object returned from the participant's browser.

        **kwargs
            Keyword arguments, including:

            1. ``blobs``:
               A dictionary of any blobs that were returned from the
               participant's browser.

            2. ``metadata``:
               The metadata returned from the participant's browser.

            3. ``experiment``:
               An instantiation of :class:`psynet.experiment.Experiment`,
               corresponding to the current experiment.

            4. ``participant``:
               An instantiation of :class:`psynet.participant.Participant`,
               corresponding to the current participant.

        Returns
        -------

        Object
            The formatted answer, suitable for serialisation to JSON
            and storage in the database.
        """
        # pylint: disable=unused-argument
        return raw_answer

    def validate(self, response, **kwargs):
        # pylint: disable=unused-argument
        """
        Takes the :class:`psynet.timeline.Response` object
        created by the page and runs a validation check
        to determine whether the participant may continue to the next page.

        Parameters
        ----------

        response:
            An instance of :class:`psynet.timeline.Response`.
            Typically the ``answer`` attribute of this object
            is most useful for validation.

        **kwargs:
            Keyword arguments, including:

            1. ``experiment``:
               An instantiation of :class:`psynet.experiment.Experiment`,
               corresponding to the current experiment.

            2. ``participant``:
               An instantiation of :class:`psynet.participant.Participant`,
               corresponding to the current participant.

        Returns
        -------

        ``None`` or an object of class :class:`psynet.timeline.FailedValidation`
            On the case of failed validation, an instantiation of
            :class:`psynet.timeline.FailedValidation`
            containing a message to pass to the participant.
        """
        return None

class NullControl(Control):
    macro = "null_control"
    metadata = {}

class ModularPage(Page):
    def __init__(
        self,
        label: str,
        prompt,
        control=NullControl(),
        time_estimate: Optional[float] = None,
        media: Optional[dict] = None,
        **kwargs
    ):

        template_str = f"""
        {{% extends "timeline-page.html" %}}

        {{% block prompt %}}
        {{{{ super() }}}}

        {{{{ {prompt.macro}(prompt) }}}}

        {{% endblock %}}

        {{% block input %}}
        {{{{ super() }}}}

        {{{{ {control.macro}(control) }}}}

        {{% endblock %}}
        """

        if media is None:
            media = MediaSpec()

        self.prompt = prompt
        self.control = control

        if isinstance(prompt, AudioPrompt):
            media.add("audio", {"prompt": prompt.url})

        super().__init__(
            label=label,
            time_estimate=time_estimate,
            template_str=template_str,
            template_arg={
                "prompt": prompt,
                "control": control
            },
            media=media,
            **kwargs
        )

    def format_answer(self, raw_answer, **kwargs):
        """
        By default, the ``format_answer`` method is extracted from the
        page's :class:`~psynet.page.Control` member.
        """
        self.control.format_answer(raw_answer=raw_answer, **kwargs)

    def validate(self, response, **kwargs):
        """
        By default, the ``validate`` method is extracted from the
        page's :class:`~psynet.page.Control` member.
        """
        self.control.validate(response=response, **kwargs)

    def metadata(self, **kwargs):
        return {
            "prompt": self.prompt.metadata,
            "input": self.control.metadata
        }
