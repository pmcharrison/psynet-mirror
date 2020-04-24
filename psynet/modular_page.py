from flask import Markup
from typing import Union, Optional, List

from .page import (
    Page,
    MediaSpec
)

from .utils import merge_dicts

class Prompt():
    """
    The Prompt class displays some kind of media to the participant,
    to which they will have to respond.

    Currently the prompt must be written as a Jinja2 macro
    in ``templates/macros.html``. In the future, we will update the API
    to allow macros to be defined in external files.

    Parameters
    ----------

    text
        Optional text to display to the participant.
        This can either be a string, which will be HTML-escaped
        and displayed as regular text, or an HTML string
        as produced by ``flask.Markup``.

    Attributes
    ----------

    macro : str
        The name of the Jinja2 macro as defined within the respective template file.

    ready_for_response : bool
        Whether or not the page starts ready for a user response.
        Set this to False if you want the page to wait for a custom
        event to happen before the response options are enabled.
        This event can be triggered with ``psynet.response.ready();``
        in Javascript.

    metadata : Object
        Metadata to save about the prompt; can take arbitrary form,
        but must be serialisable to JSON.

    media : MediaSpec
        Optional object of class :class:`~psynet.timeline.MediaSpec`
        that provisions media resources for the prompt.

    external_template : Optional[str]
        Optionally specifies a custom Jinja2 template from which the
        prompt macro should be sourced.
        If not provided, the prompt macro will be assumed to be located
        in PsyNet's built-in ``prompt.html`` file.
    """

    def __init__(
            self,
            text: Union[None, str, Markup] = None
        ):
        self.text = text

    macro = "simple"
    ready_for_response = True
    external_template = None

    @property
    def metadata(self):
        return {
            "text": self.text
        }

    @property
    def media(self):
        return MediaSpec()

class AudioPrompt(Prompt):
    def __init__(self, url: str, text: Union[str, Markup]):
        super().__init__(text=text)
        self.url = url

    macro = "audio"
    ready_for_response = False

    @property
    def metadata(self):
        return {
            "url": self.url
        }

    @property
    def media(self):
        return MediaSpec(audio={"prompt": self.url})

class Control():
    """
    The Control class provides some kind of controls for the participant,
    with which they will provide their response.

    Currently the prompt must be written as a Jinja2 macro
    in ``templates/macros.html``. In the future, we will update the API
    to allow macros to be defined in external files.

    Attributes
    ----------

    macro : str
        The name of the Jinja2 macro as defined within the respective template file.

    metadata : Object
        Metadata to save about the prompt; can take arbitrary form,
        but must be serialisable to JSON.

    media : MediaSpec
        Optional object of class :class:`~psynet.timeline.MediaSpec`
        that provisions media resources for the controls.

    external_template : Optional[str]
        Optionally specifies a custom Jinja2 template from which the
        control macro should be sourced.
        If not provided, the control macro will be assumed to be located
        in PsyNet's built-in ``control.html`` file.
    """

    external_template = None

    @property
    def macro(self):
        raise NotImplementedError

    @property
    def metadata(self):
        raise NotImplementedError

    @property
    def media(self):
        return MediaSpec()

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
    """
    Here the participant just has a single button that takes them to the next page.
    """
    macro = "null"
    metadata = {}

class NAFCButton():
    def __init__(self, button_id, *, label, min_width, own_line, start_disabled=False):
        self.id = button_id
        self.label = label
        self.min_width = min_width
        self.own_line = own_line
        self.start_disabled = start_disabled

class NAFCControl(Control):
    """
    This control interfae solicits a multiple-choice response from the participant.

    Parameters
    ----------

    choices:
        The different options the participant has to choose from.

    labels:
        An optional list of textual labels to apply to the buttons,
        which the participant will see instead of ``choices``.

    arrange_vertically:
        Whether to arrange the buttons vertically.

    min_width:
        CSS ``min_width`` parameter for the buttons.

    """

    def __init__(
            self,
            choices: List[str],
            labels: Optional[List[str]] = None,
            arrange_vertically: bool = False,
            min_width: str = "100px",
            **kwargs
    ):
        self.choices = choices
        self.labels = choices if labels is None else labels

        assert isinstance(self.labels, list)
        assert len(self.choices) == len(self.labels)

        self.buttons = [
            NAFCButton(button_id=choice, label=label, min_width=min_width, own_line=arrange_vertically)
            for choice, label in zip(self.choices, self.labels)
        ]

    macro = "nafc"

    @property
    def metadata(self):
        return {
            "choices": self.choices,
            "labels": self.labels
        }

class ModularPage(Page):
    """
    The :class:`~psynet.modular_page.ModularPage`
    class provides a way of defining pages in terms
    of two primary components: the
    :class:`~psynet.modular_page.Prompt`
    and the
    :class:`~psynet.modular_page.Control`.
    The former determines what is presented to the participant;
    the latter determines how they may respond.

    Parameters
    ----------

    label
        Internal label to give the page, used for example in results saving.

    prompt
        A :class:`~psynet.modular_page.Prompt` object that
        determines the prompt to be displayed to the participant.
        Alternatively, you can also provide text or a ``flask.Markup`` object,
        which will then be automatically wrapped in a :class:`~psynet.modular_page.Prompt` object.

    control
        A :class:`~psynet.modular_page.Control` object that
        determines the participant's response controls.

    time_estimate
        Time estimated for the page.

    media
        Optional specification of media assets to preload
        (see the documentation for :class:`psynet.timeline.MediaSpec`).
        Typically this field can be left blank, as media will be passed through the
        :class:`~psynet.modular_page.Prompt` or
        :class:`~psynet.modular_page.Control`
        objects instead.

    **kwargs
        Further arguments to be passed to :class:`psynet.timeline.Page`.
    """
    def __init__(
        self,
        label: str,
        prompt: Prompt,
        control: Control = NullControl(),
        time_estimate: Optional[float] = None,
        media: Optional[MediaSpec] = None,
        **kwargs
    ):
        if media is None:
            media = MediaSpec()

        if not isinstance(prompt, Prompt):
            prompt = Prompt(prompt)

        self.prompt = prompt
        self.control = control

        template_str = f"""
        {{% extends "timeline-page.html" %}}

        {self.import_templates}

        {{% block prompt %}}
        {{{{ super() }}}}

        {{{{ {self.prompt_macro}(prompt_config) }}}}

        {{% endblock %}}

        {{% block input %}}
        {{{{ super() }}}}

        {{{{ {self.control_macro}(control_config) }}}}

        {{% endblock %}}
        """
        all_media = MediaSpec.merge(media, prompt.media, control.media)

        super().__init__(
            label=label,
            time_estimate=time_estimate,
            template_str=template_str,
            template_arg={
                "prompt_config": prompt,
                "control_config": control
            },
            media=all_media,
            **kwargs
        )

    @property
    def prompt_macro(self):
        if self.prompt.external_template is None:
            location = "prompt"
        else:
            location = "custom_prompt"
        return f"{location}.{self.prompt.macro}"

    @property
    def control_macro(self):
        if self.control.external_template is None:
            location = "control"
        else:
            location = "custom_control"
        return f"{location}.{self.control.macro}"

    @property
    def import_templates(self):
        return self.import_internal_templates + self.import_external_templates

    @property
    def import_internal_templates(self):
        # We explicitly import these internal templates here to ensure
        # they're imported by the time we try to call them.
        return """
        {% import "macros/prompt.html" as prompt %}
        {% import "macros/control.html" as control %}
        """

    @property
    def import_external_templates(self):
        return " ".join([
            f'{{% import "{path}" as {name} with context %}}'
            for path, name in zip(
                [self.prompt.external_template, self.control.external_template],
                ["custom_prompt", "custom_control"]
            )
            if path is not None
        ])

    def format_answer(self, raw_answer, **kwargs):
        """
        By default, the ``format_answer`` method is extracted from the
        page's :class:`~psynet.page.Control` member.
        """
        return self.control.format_answer(raw_answer=raw_answer, **kwargs)

    def validate(self, response, **kwargs):
        """
        By default, the ``validate`` method is extracted from the
        page's :class:`~psynet.page.Control` member.
        """
        return self.control.validate(response=response, **kwargs)

    def metadata(self, **kwargs):
        """
        By default, the metadata attribute combines the metadata
        of the :class:`~psynet.page.Prompt` member.
        and the :class:`~psynet.page.Control` members.
        """
        return {
            "prompt": self.prompt.metadata,
            "control": self.control.metadata
        }
