from flask import Markup, escape

from typing import (
    Union,
    Optional,
    List
)

from math import ceil

from .timeline import (
    get_template,
    Page,
    PageMaker,
    MediaSpec,
    EndPage,
    FailedValidation,
    while_loop
)
import itertools

import json


class InfoPage(Page):
    """
    This page displays some content to the user alongside a button
    with which to advance to the next page.

    Parameters
    ----------

    content:
        The content to display to the user. Use :class:`flask.Markup`
        to display raw HTML.

    time_estimate:
        Time estimated for the page.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
            self,
            content: Union[str, Markup],
            time_estimate: Optional[float] = None,
            **kwargs
    ):
        self.content = content
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("info-page.html"),
            template_arg={
                "content": "" if content is None else content
            },
            **kwargs
        )

    def metadata(self, **kwargs):
        return {
            "content": self.content
        }

class WaitPage(Page):
    """
    This page makes the user wait for a specified amount of time
    before automatically continuing to the next page.

    Parameters
    ----------

    wait_time:
        Time that the user should wait.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    content = "Please wait, the experiment should continue shortly..."

    def __init__(
            self,
            wait_time: float,
            **kwargs
    ):
        assert wait_time >= 0
        self.wait_time = wait_time
        super().__init__(
            time_estimate=wait_time,
            template_str=get_template("wait-page.html"),
            template_arg={
                "content": self.content,
                "wait_time": self.wait_time
            },
            **kwargs
        )

    def metadata(self, **kwargs):
        return {
            "content": self.content,
            "wait_time": self.wait_time
        }

def wait_while(
        condition,
        expected_wait: float,
        check_interval: float = 1.0,
        wait_page=WaitPage
    ):
    """
    Displays the participant a waiting page while a given condition
    remains satisfied.

    Parameter
    ---------

    condition
        The condition to be checked;
        the participant will keep waiting while this condition returns True.
        This argument should be a function receiving the following arguments:
        ``participant`` (corresponding to the current participant)
        and ``experiment`` (corresponding to the current experiments).
        If one of this arguments is not needed, it can be omitted from the
        argument list.

    expected_wait
        How long the participant is likely to wait, in seconds.

    check_interval
        How often should the browser check the condition, in seconds.

    wait_page
        The wait page that should be displayed to the participant;
        defaults to :class:`~psynet.page.WaitPage`.

    Returns
    -------

    list :
        A list of test events suitable for inclusion in a PsyNet timeline.
    """
    assert expected_wait > 0
    assert check_interval > 0
    expected_repetitions = ceil(expected_wait / check_interval)

    return while_loop(
        "wait_while",
        condition,
        logic=wait_page(wait_time=check_interval),
        expected_repetitions=expected_repetitions
    )

class SuccessfulEndPage(EndPage):
    """
    Indicates a successful end to the experiment.
    """

    def finalise_participant(self, experiment, participant):
        participant.complete = True


class UnsuccessfulEndPage(EndPage):
    """
    Indicates an unsuccessful end to the experiment.
    """

    def __init__(self, content="default", failure_tags: Optional[List] = None):
        if content == "default":
            content = (
                "Unfortunately you did not meet the criteria to continue in the experiment. "
                "You will still be paid for the time you spent already. "
                "Thank you for taking part!"
            )
        super().__init__(content=content)
        self.failure_tags = failure_tags

    def finalise_participant(self, experiment, participant):
        if self.failure_tags:
            assert isinstance(self.failure_tags, list)
            participant.append_failure_tags(*self.failure_tags)
        experiment.fail_participant(participant)


class NAFCPage(Page):
    """
    This page solicits a multiple-choice response from the participant.
    By default this response is saved in the database as a
    :class:`psynet.timeline.Response` object,
    which can be found in the ``Questions`` table.

    Parameters
    ----------

    label:
        Internal label for the page (used to store results).

    prompt:
        Prompt to display to the user. Use :class:`flask.Markup`
        to display raw HTML.

    choices:
        The different options the participant has to choose from.

    time_estimate:
        Time estimated for the page.

    labels:
        An optional list of textual labels to apply to the buttons,
        which the participant will see instead of ``choices``.

    arrange_vertically:
        Whether to arrange the buttons vertically.

    min_width:
        CSS ``min_width`` parameter for the buttons.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
            self,
            label: str,
            prompt: Union[str, Markup],
            choices: List[str],
            time_estimate: Optional[float] = None,
            labels: Optional[List[str]] = None,
            arrange_vertically: bool = False,
            min_width: str = "100px",
            **kwargs
    ):
        self.prompt = prompt
        self.choices = choices
        self.labels = choices if labels is None else labels

        assert isinstance(self.labels, List)
        assert len(self.choices) == len(self.labels)

        if arrange_vertically:
            raise NotImplementedError

        buttons = [
            Button(button_id=choice, label=label, min_width=min_width)
            for choice, label in zip(self.choices, self.labels)
        ]
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("nafc-page.html"),
            label=label,
            template_arg={
                "prompt": prompt,
                "buttons": buttons
            },
            **kwargs
        )

    def metadata(self, **kwargs):
        # pylint: disable=unused-argument
        return {
            "prompt": self.prompt,
            "choices": self.choices,
            "labels": self.labels
        }


class TextInputPage(Page):
    """
    This page solicits a text response from the user.
    By default this response is saved in the database as a
    :class:`psynet.timeline.Response` object,
    which can be found in the ``Questions`` table.

    Parameters
    ----------

    label:
        Internal label for the page (used to store results).

    prompt:
        Prompt to display to the user. Use :class:`flask.Markup`
        to display raw HTML.

    time_estimate:
        Time estimated for the page.

    one_line:
        Whether the text box should comprise solely one line.

    width:
        Optional CSS width property for the text box.

    height:
        Optional CSS height property for the text box.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
            self,
            label: str,
            prompt: Union[str, Markup],
            time_estimate: Optional[float] = None,
            one_line: bool = True,
            width: Optional[str] = None,  # e.g. "100px"
            height: Optional[str] = None,
            **kwargs
    ):
        self.prompt = prompt

        if one_line and height is not None:
            raise ValueError("If <one_line> is True, then <height> must be None.")

        style = (
            "" if width is None else f"width:{width}"
                                     " "
                                     "" if height is None else f"height:{height}"
        )

        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("text-input-page.html"),
            label=label,
            template_arg={
                "prompt": prompt,
                "one_line": one_line,
                "style": style
            },
            **kwargs
        )

    def metadata(self, **kwargs):
        # pylint: disable=unused-argument
        return {
            "prompt": self.prompt
        }


SLIDER_DEFAULT_NUM_TICKS = 1000


class SliderPage(Page):
    """
    This page solicits a slider response from the user.

    The page logs all interactions from the participants including:
    - initial location of the slider
    - subsequent release points along with time stamps

    By default this response is saved in the database as a
    :class:`psynet.timeline.Response` object,
    which can be found in the ``Questions`` table.

    Currently the slider does not display any numbers describing the
    slider's current position. We anticipate adding this feature in
    a future release, if there is interest.

    Parameters
    ----------

    label:
        Internal label for the page (used to store results).

    prompt:
        Prompt to display to the user. Use :class:`flask.Markup`
        to display raw HTML.

    start_value:
        Position of slider at start.

    min_value:
        Minimum value of the slider.

    max_value:
        Maximum value of the slider.

    allowed_values: default: SLIDER_DEFAULT_NUM_TICKS
        <int>: indicating number of possible equidistant steps between `min_value` and `max_value`,
        by default we use SLIDER_DEFAULT_NUM_TICKS
        <list>: list of numbers enumerating all possible values, need to be within `min_value` and `max_value`.

    input_type: default: "HTML5_range_slider"
        By default we use the HTML5 slider, however future implementations might also use different slider
        formats, like 2D sliders or circular sliders.

    snap_slider: default: True

    minimal_interactions: default: 0
        Minimal interactions with the slider before the user can go to next trial.

    reverse_scale: default: False
        Flip the scale.

    width:
        Optional CSS width property for the text box.

    height:
        Optional CSS height property for the text box.

    time_estimate:
        Time estimated for the page.

    template_str:
        Optional different template.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
            self,
            label: str,
            prompt: Union[str, Markup],
            start_value: float,
            min_value: float,
            max_value: float,
            allowed_values: Optional[Union[int, list]] = SLIDER_DEFAULT_NUM_TICKS,
            input_type: Optional[str] = "HTML5_range_slider",
            snap_slider: Optional[bool] = True,
            minimal_interactions: Optional[int] = 0,
            reverse_scale: Optional[bool] = False,
            slider_id: Optional[str] = 'sliderpage_slider',
            width: Optional[str] = None,  # e.g. "100px"
            height: Optional[str] = None,
            time_estimate: Optional[float] = None,
            template_str: Optional[str] = get_template("slider-page.html"),
            **kwargs
    ):
        self.max_value = max_value
        self.min_value = min_value
        self.start_value = start_value
        self.input_type = input_type
        self.minimal_interactions = minimal_interactions

        self._validate()

        if not 'js_vars' in kwargs:
            kwargs['js_vars'] = {}

        if 'template_arg' in kwargs:
            template_arg = kwargs['template_arg']
        else:
            template_arg = {}

        ticks, step_size, diff = self._get_ticks_step_size_and_diff(allowed_values, max_value, min_value)

        self.ticks = ticks
        style = (
            "" if width is None else f"width:{width}"
                                     " "
                                     "" if height is None else f"height:{height}"
        )

        if not snap_slider:
            step_size = diff / (SLIDER_DEFAULT_NUM_TICKS - 1)

        new_template_args = {
            "prompt": prompt,
            "start_value": start_value,
            "min_value": min_value,
            "max_value": max_value,
            "step_size": step_size,
            "snap_slider": snap_slider,
            "reverse_scale": reverse_scale,
            "style": style,
            "slider_id": slider_id
        }

        if not 'template_arg' in kwargs:
            kwargs['template_arg'] = {}

        for key, value in new_template_args.items():
            kwargs['template_arg'][key] = value

        kwargs['js_vars']["ticks"] = ticks
        kwargs['js_vars']["start_value"] = start_value
        kwargs['js_vars']['minimal_interactions'] = minimal_interactions
        kwargs['js_vars']["reverse_scale"] = reverse_scale
        kwargs['js_vars']["snap_slider"] = snap_slider

        super().__init__(
            time_estimate=time_estimate,
            template_str=template_str,
            label=label,
            **kwargs
        )

    def _validate(self):
        if self.input_type != "HTML5_range_slider":
            raise NotImplementedError('Currently "HTML5_range_slider" is the only supported `input_type`')

        if self.max_value <= self.min_value:
            raise ValueError("`max_value` must be larger than `min_value`")

        if self.start_value > self.max_value or self.start_value < self.min_value:
            raise ValueError("`start_value` (= %f) must be between `min_value` (=%f) and `max_value` (=%f)" % (
                self.start_value, self.min_value, self.max_value))

        if self.minimal_interactions < 0:
            raise ValueError('`minimal_interactions` cannot be negative!')

    def _check_allowed_values_list(self, allowed_values, max_value, min_value):
        # Must be a list
        if not isinstance(allowed_values, list):
            return False
        for i in allowed_values:
            # Check if it's numeric
            if not isinstance(i, (float, int)):
                return False
            # Check if it doesn't exceed min and max
            if i > max_value or i < min_value:
                return False
        return True

    def _get_ticks_step_size_and_diff(self, allowed_values, max_value, min_value):
        if isinstance(allowed_values, int):
            num_ticks = allowed_values
        else:
            num_ticks = SLIDER_DEFAULT_NUM_TICKS
        diff = max_value - min_value
        step_size = diff / (num_ticks - 1)
        if isinstance(allowed_values, int):
            # In both cases the left of the slider is the minimum and the right the maximum
            ticks = [step_size * i for i in range(num_ticks)]
        elif self._check_allowed_values_list(allowed_values, max_value, min_value):
            ticks = allowed_values
        else:
            raise ValueError('`allowed_values` must either be a list of values or an integer')

        return (ticks, step_size, diff)

    def metadata(self, **kwargs):
        return {
            **super().metadata(),
            'ticks': self.ticks,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'start_value': self.start_value,
            'input_type': self.input_type,
            'minimal_interactions': self.minimal_interactions
        }


class AudioSliderPage(SliderPage):
    """
    See issue #11
    This page solicits a slider response from the user that results in playing some audio.

    By default this response is saved in the database as a
    :class:`psynet.timeline.Response` object,
    which can be found in the ``Questions`` table.

    Parameters
    ----------

    label:
        Internal label for the page (used to store results).

    prompt:
        Prompt to display to the user. Use :class:`flask.Markup`
        to display raw HTML.

    sound_locations:
        Dictionary with IDs as keys and locations on the slider as values.

    start_value:
        Position of slider at start.

    min_value:
        Minimal value of the slider.

    max_value:
        Maximum value of the slider.

    allowed_values:
        <int>: indicating number of possible equidistant steps between `min_value` and `max_value`,
        by default we use SLIDER_DEFAULT_NUM_TICKS
        <list>: list of numbers enumerating all possible values, need to be within `min_value` and `max_value`.

    autoplay:
        Default: False. The sound closest to the current slider position is played once the page is loaded.

    template_arg:
        By default empty dictionary. Optional template arguments.

    template_str: default: the page template slider-audio-page.html
        Can be overwritten in classes inheriting from this class.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.SliderPage`.
    """

    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],
        sound_locations: dict,
        start_value: float,
        min_value: float,
        max_value: float,
        allowed_values: Optional[Union[int, list]] = SLIDER_DEFAULT_NUM_TICKS,
        autoplay: Optional[bool] = False,
        time_estimate: Optional[float] = None,
        template_str: Optional[str] = get_template("slider-audio-page.html"),
        **kwargs
    ):
        if not 'media' in kwargs:
            raise ValueError('You must specify sounds in `media` you later want to play with the slider')

        if not 'audio' in kwargs['media']:
            raise ValueError('The `media` dictionary must contain the key `audio`')

        # Check if all stimuli specified in `sound_locations` are
        # also preloaded before the participant can start the trial
        audio = kwargs['media'].audio
        IDs_sound_locations = [ID for ID, _ in sound_locations.items()]
        IDs_media = []
        for key, value in audio.items():
            if isinstance(audio[key], dict) and 'ids' in audio[key]:
                IDs_media.append(audio[key]['ids'])
            elif isinstance(audio[key], str):
                IDs_media.append(key)
            else:
                raise NotImplementedError('Currently we only support batch files or single files')
        IDs_media = list(itertools.chain.from_iterable(IDs_media))

        if not any([i in IDs_media for i in IDs_sound_locations]):
            raise ValueError('All stimulus IDs you specify in `sound_locations` need to be defined in `media` too.')

        # Check if all audio files are also really playable
        # ticks, step_size, diff = self._get_ticks_step_size_and_diff(allowed_values, max_value, min_value)
        # if not all([location in ticks for _, location in sound_locations.items()]):
        #     raise ValueError('The slider does not contain all locations for the audio')

        if not 'js_vars' in kwargs:
            kwargs['js_vars'] = {}
        kwargs['js_vars']['autoplay'] = autoplay
        kwargs['js_vars']['sound_locations'] = sound_locations

        self.sound_locations = sound_locations
        # All range checking is done in the parent class
        super().__init__(
            prompt=prompt,
            start_value=start_value,
            min_value=min_value,
            max_value=max_value,
            allowed_values=allowed_values,
            time_estimate=time_estimate,
            template_str=template_str,
            label=label,
            **kwargs
        )

    def metadata(self, **kwargs):
        # pylint: disable=unused-argument
        return {
            **super().metadata(),
            'sound_locations': self.sound_locations
        }


class NumberInputPage(TextInputPage):
    """
    This page is like :class:`psynet.timeline.TextInputPage`,
    except it forces the user to input a number.
    See :class:`psynet.timeline.TextInputPage` for argument documentation.
    """

    def format_answer(self, raw_answer, **kwargs):
        try:
            return float(raw_answer)
        except ValueError:
            return "INVALID_RESPONSE"

    def validate(self, response, **kwargs):
        if response.answer == "INVALID_RESPONSE":
            return FailedValidation("Please enter a number.")
        return None


class Button():
    def __init__(self, button_id, label, min_width, start_disabled=False):
        self.id = button_id
        self.label = label
        self.min_width = min_width
        self.start_disabled = start_disabled


class DebugResponsePage(PageMaker):
    """
    Implements a debugging page for responses.
    Displays a page to the user with information about the
    last response received from the participant.
    """

    def __init__(self):
        super().__init__(self.summarise_last_response, time_estimate=0)

    @staticmethod
    def summarise_last_response(participant):
        response = participant.response
        if response is None:
            return InfoPage("No response found to display.")
        page_type = escape(response.page_type)
        answer = escape(response.answer)
        metadata = escape(json.dumps(response.metadata, indent=4))
        return InfoPage(Markup(
            f"""
            <h3>Page type</h3>
            {page_type}
            <h3>Answer</h3>
            {answer}
            <h3>Metadata</h3>
            <pre>{metadata}</pre>
            """
        ))

class ResponsePage(Page):
    def __init__(
        self,
        label: str,
        prompt,
        input,
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

        {{{{ {input.macro}(input) }}}}

        {{% endblock %}}
        """

        if media is None:
            media = MediaSpec()

        self.prompt = prompt
        self.input = input

        if isinstance(prompt, AudioPrompt):
            media.add("audio", {"prompt": prompt.url})

        super().__init__(
            time_estimate=time_estimate,
            template_str=template_str,
            template_arg={
                "prompt": prompt,
                "input": input
            },
            media=media,
            **kwargs
        )

    def metadata(self, **kwargs):
        return {
            "prompt": self.prompt.metadata,
            "input": self.input.metadata
        }

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

class Input():
    @property
    def macro(self):
        raise NotImplementedError

    @property
    def metadata(self):
        raise NotImplementedError

class NullInput():
    macro = "null_input"
    metadata = {}