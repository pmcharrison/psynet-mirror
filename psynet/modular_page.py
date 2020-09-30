import json, os, tempfile
from urllib.parse import splitquery, urlparse
from dominate import tags
from dominate.util import raw

from flask import Markup
from typing import Union, Optional, List
from uuid import uuid4
from scipy.io import wavfile

from .timeline import (
    Page,
    MediaSpec,
    is_list_of
)
from .media import (
    get_s3_url,
    generate_presigned_url,
    prepare_s3_bucket_for_presigned_urls
)

from .utils import get_logger

logger = get_logger()

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

    text_align
        CSS alignment of the text.

    Attributes
    ----------

    macro : str
        The name of the Jinja2 macro as defined within the respective template file.

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
            text: Union[None, str, Markup] = None,
            text_align: str = "left"
        ):
        self.text = text
        self.text_align = text_align

    macro = "simple"
    external_template = None

    @property
    def metadata(self):
        return {
            "text": self.text
        }

    @property
    def media(self):
        return MediaSpec()

    def visualize(self, trial):
        if self.text is None:
            return ""
        elif isinstance(self.text, Markup):
            return str(self.text)
        else:
            return tags.p(self.text).render()

    def pre_render(self):
        pass

class AudioPrompt(Prompt):
    """
    Plays an audio file to the participant.

    Parameters
    ----------

    url
        URL of the audio file to play.

    text
        Text to display to the participant. This can either be a string
        for plain text, or an HTML specification from ``flask.Markup``.

    loop
        Whether the audio should loop back to the beginning after finishing.

    prevent_response
        Whether the participant should be prevented from interacting with the
        response controls until the audio is finished.

    prevent_submit
        Whether the participant should be prevented from submitting their final
        response until the audio is finished.

    enable_submit_after
        If not ``None``, sets a time interval in seconds after which the response
        options will be enabled.

    start_delay
        Delay in seconds before the sound should start playing, counting from
        the media load event.

    text_align
        CSS alignment of the text.
    """
    def __init__(
            self,
            url: str,
            text: Union[str, Markup],
            loop: bool = False,
            prevent_response: bool = True,
            prevent_submit: bool = True,
            enable_submit_after: Optional[float] = None,
            start_delay = 0.0,
            text_align = "left"
        ):
        super().__init__(text=text, text_align=text_align)
        self.url = url
        self.prevent_response = prevent_response
        self.prevent_submit = prevent_submit
        self.enable_submit_after = enable_submit_after
        self.loop = loop
        self.start_delay = start_delay

    macro = "audio"

    @property
    def metadata(self):
        return {
            "text": self.text,
            "url": self.url
        }

    @property
    def media(self):
        return MediaSpec(audio={"prompt": self.url})

    def visualize(self, trial):
        html = (
            super().visualize(trial) +
            "\n" +
            tags.audio(
                tags.source(src=self.url),
                id="visualize-audio-prompt",
                controls=True
            ).render()
        )
        return html

class ImagePrompt(Prompt):
    """
    Displays an image to the participant.

    Parameters
    ----------

    url
        URL of the image to show.

    text
        Text to display to the participant. This can either be a string
        for plain text, or an HTML specification from ``flask.Markup``.

    width
        CSS width specification for the image (e.g. ``'50%'``).

    height
        CSS height specification for the image (e.g. ``'50%'``).
        ``'auto'`` will choose the height automatically to match the width;
        the disadvantage of this is that other page content may move
        once the image loads.

    hide_after
        If not ``None``, specifies a time in seconds after which the image should be hidden.

    margin_top
        CSS specification of the image's top margin.

    margin_bottom
        CSS specification of the image's bottom margin.

    text_align
        CSS alignment of the text.

    """
    def __init__(
            self,
            url: str,
            text: Union[str, Markup],
            width: str,
            height: str,
            hide_after: Optional[float] = None,
            margin_top: str = "0px",
            margin_bottom: str = "0px",
            text_align: str = "left"
        ):
        super().__init__(text=text, text_align=text_align)
        self.url = url
        self.width = width
        self.height = height
        self.hide_after = hide_after
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom

    macro = "image"

    @property
    def metadata(self):
        return {
            "text": self.text,
            "url": self.url,
            "hide_after": self.hide_after
        }

class ColourPrompt(Prompt):
    """
    Displays a colour to the participant.

    Parameters
    ----------

    colour
        Colour to show, specified as a list of HSL values.

    text
        Text to display to the participant. This can either be a string
        for plain text, or an HTML specification from ``flask.Markup``.

    width
        CSS width specification for the colour box (default ``'200px'``).

    height
        CSS height specification for the colour box (default ``'200px'``).

    text_align
        CSS alignment of the text.

    """
    def __init__(
            self,
            colour: List[float],
            text: Union[str, Markup],
            width: str = "200px",
            height: str = "200px",
            text_align: str = "left"
        ):
        assert isinstance(colour, list)
        super().__init__(text=text, text_align=text_align)
        self.hsl = colour
        self.width = width
        self.height = height

    macro = "colour"

    @property
    def metadata(self):
        return {
            "text": self.text,
            "hsl": self.hsl
        }

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

    def visualize_response(self, answer, response, trial):
        return ""

    def pre_render(self):
        pass

class NullControl(Control):
    """
    Here the participant just has a single button that takes them to the next page.
    """
    macro = "null"
    metadata = {}

class NAFCButton():
    def __init__(self, button_id, *, label, min_width, own_line, start_disabled=False, margin="10px"):
        self.id = button_id
        self.label = label
        self.min_width = min_width
        self.own_line = own_line
        self.start_disabled = start_disabled
        self.margin = margin
        self.display = "block" if own_line else "inline"

class NAFCControl(Control):
    """
    This control interface solicits a multiple-choice response from the participant.

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

    margin:
        CSS margin parameter for the buttons.

    """

    def __init__(
            self,
            choices: List[str],
            labels: Optional[List[str]] = None,
            arrange_vertically: bool = False,
            min_width: str = "100px",
            margin: str = "10px"
    ):
        self.choices = choices
        self.labels = choices if labels is None else labels
        self.arrange_vertically = arrange_vertically

        assert isinstance(self.labels, list)
        assert len(self.choices) == len(self.labels)

        self.buttons = [
            NAFCButton(
                button_id=choice,
                label=label,
                min_width=min_width,
                own_line=arrange_vertically,
                margin=margin
            )
            for choice, label in zip(self.choices, self.labels)
        ]

    macro = "nafc"

    @property
    def metadata(self):
        return {
            "choices": self.choices,
            "labels": self.labels
        }

    def visualize_response(self, answer, response, trial):
        html = tags.div(id="response-options")
        with html:
            for choice, label in zip(self.choices, self.labels):
                tags.input(
                    type="radio",
                    id=choice,
                    name="response-options",
                    value=choice,
                    checked=(answer is not None and choice == answer),
                    disabled=True
                )
                tags.span(label)
                tags.br()
        return html.render()


class TextControl(Control):
    """
    This control interface solicits free text from the participant.

    Parameters
    ----------

    one_line:
        Whether the text box should comprise solely one line.

    width:
        Optional CSS width property for the text box.

    height:
        Optional CSS height property for the text box.

    align:
        Alignment for the text.

    """

    def __init__(
            self,
            one_line: bool = True,
            width: Optional[str] = None,  # e.g. "100px"
            height: Optional[str] = None,
            text_align: str = "left"
    ):
        if one_line and height is not None:
            raise ValueError("If <one_line> is True, then <height> must be None.")

        self.one_line = one_line
        self.width = width
        self.height = height
        self.text_align = text_align

    macro = "text"

    @property
    def metadata(self):
        return {
            "one_line": self.one_line,
            "width": self.width,
            "height": self.height,
            "text_align": self.text_align
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

        {{% block main_body %}}
        {{{{ super() }}}}

        {{{{ {self.prompt_macro}(prompt_config) }}}}

        <p class="vspace"></p>

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
            location = "psynet_prompts"
        else:
            location = "custom_prompt"
        return f"{location}.{self.prompt.macro}"

    @property
    def control_macro(self):
        if self.control.external_template is None:
            location = "psynet_controls"
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
        {% import "macros/prompt.html" as psynet_prompts %}
        {% import "macros/control.html" as psynet_controls %}
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

    def visualize(self, trial):
        prompt = self.prompt.visualize(trial)
        response = self.control.visualize_response(
            answer=trial.answer,
            response=trial.response,
            trial=trial
        )
        div = tags.div(id="trial-visualization")
        div_style = (
            "background-color: white; padding: 10px; "
            "margin-top: 10px; margin-bottom: 10px; "
            "border-style: solid; border-width: 1px;"
        )
        with div:
            if prompt != "":
                tags.h3("Prompt"),
                tags.div(
                    raw(prompt),
                    id="prompt-visualization",
                    style=div_style
                )
            if prompt != "" and response != "":
                tags.br()
            if response != "":
                tags.h3("Response"),
                tags.div(
                    raw(response),
                    id="response-visualization",
                    style=div_style
                )
        return div.render()

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

    def pre_render(self):
        """
            This method is called immediately prior to rendering the page for
            the participant. It will be called again each time the participant
            refreshes the page.
        """
        self.prompt.pre_render()
        self.control.pre_render()


class AudioMeterControl(Control):
    macro = "audio_meter"

    def __init__(
            self,
            min_time: float = 2.5,
            calibrate: bool = False,
            submit_button: bool = True
        ):
        assert min_time >= 0
        self.min_time = min_time
        self.calibrate = calibrate
        self.submit_button = submit_button
        if calibrate:
            self.sliders = SliderControl([
                Slider("decay_display", "Decay (display)", self.decay["display"], 0, 3, 0.001),
                Slider("decay_high", "Decay (too high)", self.decay["high"], 0, 3, 0.001),
                Slider("decay_low", "Decay (too low)", self.decay["low"], 0, 3, 0.001),
                Slider("threshold_high", "Threshold (high)", self.threshold["high"], -60, 0, 0.01),
                Slider("threshold_low", "Threshold (low)", self.threshold["low"], -60, 0, 0.01),
                Slider("grace_high", "Grace period (too high)", self.grace["high"], 0, 5, 0.001),
                Slider("grace_low", "Grace period (too low)", self.grace["low"], 0, 5, 0.001),
                Slider("warn_on_clip", "Warn on clip?", int(self.warn_on_clip), 0, 1, 1),
                Slider("msg_duration_high", "Message duration (high)", self.msg_duration["high"], 0, 10, 0.1),
                Slider("msg_duration_low", "Message duration (low)", self.msg_duration["low"], 0, 10, 0.1)
            ])
        else:
            self.slider = None

    display_range = {
        "min": -60,
        "max": 0
    }

    decay = {
        "display": 0.1,
        "high": 0.1,
        "low": 0.1
    }

    threshold = {
        "high": -2,
        "low": -20
    }

    grace = {
        "high": 0.0,
        "low": 1.5
    }

    warn_on_clip = True

    msg_duration = {
        "high": 0.25,
        "low": 0.25
    }

    def to_json(self):
        return Markup(json.dumps({
            "display_range": self.display_range,
            "decay": self.decay,
            "threshold": self.threshold,
            "grace": self.grace,
            "warn_on_clip": self.warn_on_clip,
            "msg_duration": self.msg_duration
        }))

    @property
    def metadata(self):
        return {
            "min_time": self.min_time
        }

class TappingAudioMeterControl(AudioMeterControl):
    decay = {
        "display": 0.01,
        "high": 0,
        "low": 0.01
    }

    threshold = {
        "high": -2,
        "low": -20
    }

    grace = {
        "high": 0.2,
        "low": 1.5
    }

    warn_on_clip = False

    msg_duration = {
        "high": 0.25,
        "low": 0.25
    }

class SliderControl(Control):
    def __init__(
            self,
            sliders,
            next_button=True,
        ):
        assert is_list_of(sliders, Slider)
        self.sliders = sliders
        self.next_button = next_button

    # WIP

class Slider():
    def __init__(
            self,
            slider_id,
            label,
            start_value,
            min_value,
            max_value,
            step_size
        ):
        self.label = label
        self.start_value = start_value
        self.min_value = min_value
        self.max_value = max_value
        self.step_size = step_size
        self.slider_id = slider_id

class AudioRecordControl(Control):
    macro = "audio_record"

    def __init__(
            self,
            *,
            duration: float,
            s3_bucket: str,
            show_meter: bool = False,
            public_read: bool = False
        ):
        self.duration = duration
        self.s3_bucket = s3_bucket
        self.show_meter = show_meter
        self.public_read = public_read

        if show_meter:
            self.meter = AudioMeterControl(submit_button=False)
        else:
            self.meter = None

    @property
    def metadata(self):
        return {}

    def format_answer(self, raw_answer, **kwargs):
        filename = os.path.basename(urlparse(raw_answer).path)
        return {
            "s3_bucket": self.s3_bucket,
            "key": filename, # Leave key for backward compatibility
            "url": splitquery(raw_answer)[0],
            "duration_sec": self.duration
        }

    def visualize_response(self, answer, response, trial):
        if answer is None:
            return tags.p("No audio recorded yet.").render()
        else:
            return tags.audio(
                tags.source(src=answer["url"]),
                id="visualize-audio-response",
                controls=True
            ).render()

    def pre_render(self):
        prepare_s3_bucket_for_presigned_urls(self.s3_bucket,
                                             self.public_read,
                                             create_new_bucket=True)
        self.presigned_url = generate_presigned_url(self.s3_bucket, "wav")
        logger.info(f"Generated presigned url: {self.presigned_url}")

class VideoSliderControl(Control):
    macro = "video_slider"

    def __init__(
            self,
            *,
            url: str,
            file_type: str,
            width: str,
            height: str,
            starting_value: float = 0.5,
            minimal_time: float = 2.0,
            reverse_scale: bool = False,
            hide_slider: bool = False
        ):
        assert 0 <= starting_value and starting_value <= 1

        self.url = url
        self.file_type = file_type
        self.width = width
        self.height = height
        self.starting_value = starting_value
        self.minimal_time = minimal_time
        self.reverse_scale = reverse_scale
        self.hide_slider = hide_slider

    @property
    def metadata(self):
        return {
            "url": self.url,
            "starting_value": self.starting_value,
            "minimal_time": self.minimal_time,
            "reverse_scale": self.reverse_scale,
            "hide_slider": self.hide_slider
        }

    @property
    def media(self):
        return MediaSpec(video={"slider_video": self.url})

    def visualize_response(self, answer, response, trial):
        html = (
            super().visualize_response(answer, response, trial) +
            "\n" +
            tags.div(
                tags.p(f"Answer = {answer}"),
                tags.video(
                    tags.source(src=self.url),
                    id="visualize-video-slider",
                    controls=True,
                    style="max-width: 400px;"
                )
            ).render()
        )
        return html
