import itertools
import json
import warnings
from math import ceil
from typing import List, Optional, Union

from dominate.dom_tag import dom_tag
from flask import Markup, escape
from pkg_resources import resource_filename

from .asset import CachedAsset, ExternalAsset
from .modular_page import (
    AudioPrompt,
    AudioSliderControl,
    ModularPage,
    NumberControl,
    Prompt,
    PushButtonControl,
    SliderControl,
    TextControl,
)
from .timeline import (
    CodeBlock,
    EndPage,
    Event,
    Module,
    Page,
    PageMaker,
    get_template,
    join,
    while_loop,
)
from .utils import get_logger, linspace

logger = get_logger()
warnings.simplefilter("always", DeprecationWarning)


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
        content: Union[str, Markup, dom_tag],
        time_estimate: Optional[float] = None,
        **kwargs,
    ):
        self.content = content
        super().__init__(
            time_estimate=time_estimate,
            template_str=get_template("info-page.html"),
            template_arg={"content": "" if content is None else content},
            save_answer=False,
            **kwargs,
        )

    def metadata(self, **kwargs):
        return {"content": self.content}

    def get_bot_response(self, experiment, bot):
        from .bot import BotResponse

        return BotResponse(
            answer=None,
            metadata=self.metadata(),
        )


class UnityPage(Page):
    """
    This is the main page when conducting Unity experiments. Its attributes ``contents`` and ``attributes`` can be accessed through the JavaScript variable ``psynet.page`` inside the page template.

    Ín order to conclude this page call the ``psynet.nextPage`` function which has following parameters:

    * ``rawAnswer``: The main answer that the page returns.

    * ``metadata``: Additional information that might be useful for debugging or other exploration, e.g. time taken on the page.

    * ``blobs``: Use this for large binaries, e.g. audio recordings.

    Once the ``psynet.nextPage`` function is called, PsyNet will navigate to a new page if the new page has a different session_id compared to the current page, otherwise it will update the page while preserving the ongoing Unity session, specifically updating ``psynet.page`` and triggering the JavaScript event ``pageUpdated`` in the ``window`` object.

    Parameters
    ----------

    title:
        The title of the experiment to be rendered in the HTML title-tag of the page.

    game_container_width:
        The width of the game container, e.g. '960px'.

    game_container_height:
        The height of the game container, e.g. '600px'.

    resources:
        The path to the directory containing the Unity files residing inside the "static" directory. The path should start with "/static" and should comply with following basic structure:

        static/
        ├── css/
        └── scripts/

        css: Contains stylesheets
        scripts: Contains JavaScript files

    contents:
        A dictionary containing experiment specific data.

    time_estimate:
        Time estimated for the page (seconds).

    session_id:
        If session_id is not None, then it must be a string. If two consecutive pages occur with the same session_id, then when it’s time to move to the second page, the browser will not navigate to a new page, but will instead update the JavaScript variable psynet.page with metadata for the new page, and will trigger an event called pageUpdated. This event can be listened for with JavaScript code like window.addEventListener(”pageUpdated”, ...).

    debug:
        Specifies if we are in debug mode and use `unity-debug-page.html` as template instead of the standard `unity-page.html`.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    dynamically_update_progress_bar_and_bonus = True

    def __init__(
        self,
        title: str,
        resources: str,
        contents: dict,
        session_id: str,
        game_container_width: str = "960px",
        game_container_height: str = "600px",
        time_estimate: Optional[float] = None,
        debug: bool = False,
        **kwargs,
    ):
        self.title = title
        self.resources = resources
        self.contents = contents
        self.game_container_width = game_container_width
        self.game_container_height = game_container_height
        self.session_id = session_id

        template = "unity-debug-page.html" if debug else "unity-page.html"

        super().__init__(
            contents=self.contents,
            time_estimate=time_estimate,
            template_str=get_template(template),
            template_arg={
                "title": self.title,
                "resources": "" if self.resources is None else self.resources,
                "contents": {} if self.contents is None else self.contents,
                "game_container_width": self.game_container_width,
                "game_container_height": self.game_container_height,
                "session_id": self.session_id,
            },
            session_id=session_id,
            **kwargs,
        )

    def metadata(self, **kwargs):
        return {
            "resources": self.resources,
            "contents": self.contents,
            "session_id": self.session_id,
            "time_taken": None,
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

    def __init__(self, wait_time: float, **kwargs):
        assert wait_time >= 0
        self.wait_time = wait_time
        super().__init__(
            time_estimate=wait_time,
            template_str=get_template("wait-page.html"),
            template_arg={"content": self.content, "wait_time": self.wait_time},
            **kwargs,
        )

    def metadata(self, **kwargs):
        return {"content": self.content, "wait_time": self.wait_time}

    def get_bot_response(self, experiment, bot):
        return None


def wait_while(
    condition,
    expected_wait: float,
    check_interval: float = 2.0,
    max_wait_time: float = 20.0,
    wait_page=WaitPage,
    log_message: Optional[str] = None,
    fail_on_timeout=True,
):
    """
    Displays the participant a waiting page while a given condition
    remains satisfied.

    Parameters
    ----------

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

    max_wait_time
        The participant's maximum waiting time in seconds. Default: 20.0.

    wait_page
        The wait page that should be displayed to the participant;
        defaults to :class:`~psynet.page.WaitPage`.

    log_message
        Optional message to display in the log.

    fail_on_timeout
        Whether the participants should be failed when the ``max_loop_time`` is reached.
        Setting this to ``False`` will not return the ``UnsuccessfulEndPage`` when maximum time has elapsed
        but allow them to proceed to the next page.

    Returns
    -------

    list :
        A list of test elts suitable for inclusion in a PsyNet timeline.
    """
    assert expected_wait >= 0
    assert check_interval > 0
    expected_repetitions = ceil(expected_wait / check_interval)

    _wait_page = wait_page(wait_time=check_interval)

    def log(participant):
        logger.info(f"Participant {participant.id}: {log_message}")

    if log_message is None:
        logic = _wait_page
    else:
        logic = join(CodeBlock(log), _wait_page)

    return join(
        while_loop(
            "wait_while",
            condition,
            logic=logic,
            expected_repetitions=expected_repetitions,
            max_loop_time=max_wait_time,
            fail_on_timeout=fail_on_timeout,
        ),
    )


class SuccessfulEndPage(EndPage):
    """
    Indicates a successful end to the experiment.
    """

    def __init__(self, show_bonus: bool = True):
        super().__init__("final-page-successful.html", label="SuccessfulEndPage")
        self.show_bonus = show_bonus

    def finalize_participant(self, experiment, participant):
        participant.complete = True


class UnsuccessfulEndPage(EndPage):
    """
    Indicates an unsuccessful end to the experiment.
    """

    def __init__(
        self,
        show_bonus: bool = True,
        failure_tags: Optional[List] = None,
        template_filename: str = "final-page-unsuccessful.html",
    ):
        super().__init__(template_filename, label="UnsuccessfulEndPage")
        self.failure_tags = failure_tags
        self.show_bonus = show_bonus

    def finalize_participant(self, experiment, participant):
        if self.failure_tags:
            assert isinstance(self.failure_tags, list)
            participant.append_failure_tags(*self.failure_tags)
        experiment.fail_participant(participant)


class RejectedConsentPage(UnsuccessfulEndPage):
    """
    Indicates a consent that has been rejected.
    """

    def __init__(self, failure_tags: Optional[List] = None):
        super().__init__(
            failure_tags=failure_tags,
            template_filename="final-page-rejected-consent.html",
        )


class NAFCPage(ModularPage):
    """
    .. deprecated:: 1.11.0
        Use :class:`psynet.modular_page.ModularPage` in combination with :class:`psynet.modular_page.PushButtonControl` instead.

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
        **kwargs,
    ):
        warnings.warn(
            "psynet.page.NAFCPage is deprecated. Use :class:`psynet.modular_page.ModularPage` in combination with :class:`psynet.modular_page.PushButtonControl instead.",
            DeprecationWarning,
        )

        labels = choices if labels is None else labels

        assert isinstance(labels, List)
        assert len(choices) == len(labels)

        super().__init__(
            label,
            prompt=prompt,
            control=PushButtonControl(
                choices,
                labels=labels,
                arrange_vertically=arrange_vertically,
            ),
            time_estimate=time_estimate,
        )

    def metadata(self, **kwargs):
        # pylint: disable=unused-argument
        return {
            "prompt": self.prompt.metadata,
            "control": self.control.metadata,
        }


class TextInputPage(ModularPage):
    """
    .. deprecated:: 1.11.0
        Use :class:`psynet.modular_page.ModularPage` in combination with :class:`psynet.modular_page.Prompt` and :class:`psynet.modular_page.TextControl` instead.

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
        Optional CSS width property for the text box, e.g. ``"400px"``.

    height:
        Optional CSS height property for the text box, e.g. ``"100px"``.

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
        **kwargs,
    ):
        warnings.warn(
            "psynet.page.TextInputPage is deprecated. Use :class:`psynet.modular_page.ModularPage` in combination with :class:`psynet.modular_page.Prompt` and :class:`psynet.modular_page.TextControl` instead.",
            DeprecationWarning,
        )

        if one_line and height is not None:
            raise ValueError("If <one_line> is True, then <height> must be None.")

        super().__init__(
            label,
            prompt=Prompt(prompt),
            control=TextControl(
                one_line=one_line,
                width=width,
                height=height,
            ),
            time_estimate=time_estimate,
            **kwargs,
        )

    def metadata(self, **kwargs):
        # pylint: disable=unused-argument
        return {
            "prompt": self.prompt.metadata,
            "control": self.control.metadata,
        }


class SliderPage(ModularPage):
    """
    .. deprecated:: 1.11.0
        Use :class:`psynet.modular_page.ModularPage` in combination with :class:`psynet.modular_page.Prompt` and :class:`psynet.modular_page.SliderControl` instead.

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

    n_steps: default: 10000
        Determines the number of steps that the slider can be dragged through.

    snap_values: default: None
        Determines the values to which the slider will 'snap' to once it is released.
        Can take various forms:

        - <None>: no snapping is performed.

        - <int>: indicating number of equidistant steps between `min_value` and `max_value`.

        - <list>: list of numbers enumerating all possible values, need to be within `min_value` and `max_value`.

    input_type: default: "HTML5_range_slider"
        By default we use the HTML5 slider, however future implementations might also use different slider
        formats, like 2D sliders or circular sliders.

    minimal_interactions: default: 0
        Minimal interactions with the slider before the user can go to next trial.

    minimal_time: default: 0
        Minimum amount of time that the user must spend on the page before they can continue.

    reverse_scale: default: False
        Flip the scale.

    directional: default: True
        Make the slider appear in either grey/blue color (directional) or all grey color (non-directional).

    continuous_updates : default: False
        If ``True``, then the slider continuously calls slider-update events when it is dragged,
        rather than just when it is released. In this case the log is disabled.

    time_estimate:
        Time estimated for the page.

    template_filename:
        Filename of an optional additional template.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.Page`.
    """

    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],
        *,
        start_value: float,
        min_value: float,
        max_value: float,
        n_steps: int = 10000,
        snap_values: Optional[Union[int, list]] = None,
        input_type: Optional[str] = "HTML5_range_slider",
        minimal_interactions: Optional[int] = 0,
        minimal_time: float = 0.0,
        reverse_scale: Optional[bool] = False,
        directional: Optional[bool] = True,
        continuous_updates: bool = False,
        slider_id: Optional[str] = "sliderpage_slider",
        time_estimate: Optional[float] = None,
        template_filename: Optional[str] = None,
        **kwargs,
    ):
        warnings.warn(
            "psynet.page.SliderPage is deprecated. Use :class:`psynet.modular_page.ModularPage` in combination with :class:`psynet.modular_page.Prompt` and :class:`psynet.modular_page.SliderControl` instead.",
            DeprecationWarning,
        )

        self.max_value = max_value
        self.min_value = min_value
        self.prompt = prompt
        self.start_value = start_value
        self.input_type = input_type
        self.minimal_interactions = minimal_interactions
        self.minimal_time = minimal_time
        self.n_steps = n_steps
        self.reverse_scale = reverse_scale
        self.directional = directional
        self.continuous_updates = continuous_updates
        self.slider_id = slider_id
        self.time_estimate = time_estimate

        self._validate()

        self.snap_values = self._format_snap_values(
            snap_values, min_value, max_value, n_steps
        )
        self.template_filename = template_filename

        if "template_arg" not in kwargs:
            self.template_args = {}
        else:
            self.template_args = kwargs["template_arg"]

        super().__init__(
            label,
            prompt=Prompt(self.prompt),
            control=SliderControl(
                label=label,
                start_value=self.start_value,
                min_value=self.min_value,
                max_value=self.max_value,
                n_steps=self.n_steps,
                reverse_scale=self.reverse_scale,
                directional=self.directional,
                slider_id=self.slider_id,
                snap_values=self.snap_values,
                minimal_interactions=self.minimal_interactions,
                minimal_time=self.minimal_time,
                continuous_updates=self.continuous_updates,
                template_filename=self.template_filename,
                template_args=self.template_args,
            ),
            time_estimate=self.time_estimate,
        )

    def _validate(self):
        if self.input_type != "HTML5_range_slider":
            raise NotImplementedError(
                'Currently "HTML5_range_slider" is the only supported `input_type`'
            )

        if self.max_value <= self.min_value:
            raise ValueError("`max_value` must be larger than `min_value`")

        if self.start_value > self.max_value or self.start_value < self.min_value:
            raise ValueError(
                "`start_value` (= %f) must be between `min_value` (=%f) and `max_value` (=%f)"
                % (self.start_value, self.min_value, self.max_value)
            )

        if self.minimal_interactions < 0:
            raise ValueError("`minimal_interactions` cannot be negative!")

    def _format_snap_values(self, snap_values, min_value, max_value, n_steps):
        if snap_values is None:
            return linspace(min_value, max_value, n_steps)
        elif isinstance(snap_values, int):
            return linspace(min_value, max_value, snap_values)
        else:
            for x in snap_values:
                assert isinstance(x, (float, int))
                assert x >= min_value
                assert x <= max_value
            return sorted(snap_values)

    def metadata(self, **kwargs):
        return {
            **super().metadata(),
            "prompt": self.prompt.metadata,
            "control": self.control.metadata,
            "n_steps": self.n_steps,
            "snap_values": self.snap_values,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "start_value": self.start_value,
            "input_type": self.input_type,
            "minimal_interactions": self.minimal_interactions,
            "minimal_time": self.minimal_time,
        }


class AudioSliderPage(ModularPage):
    """
    .. deprecated:: 1.11.0
        Use :class:`psynet.modular_page.ModularPage` in combination with :class:`psynet.modular_page.Prompt` and :class:`psynet.modular_page.SliderControl` instead.

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

    n_steps:
        - <int> (default = 10000): number of equidistant steps between `min_value` and `max_value` that the slider
          can be dragged through. This is before any snapping occurs.

        - ``"n_sounds"``: sets the number of steps to the number of sounds. This only makes sense
          if the sound locations are distributed equidistant between the `min_value` and `max_value` of the slider.

    snap_values:
        - ``"sound_locations"`` (default): slider snaps to nearest sound location.

        - <int>: indicates number of possible equidistant steps between `min_value` and `max_value`

        - <list>: enumerates all possible values, need to be within `min_value` and `max_value`.

        - ``None``: don't snap slider.

    autoplay:
        Default: False. The sound closest to the current slider position is played once the page is loaded.

    template_arg:
        By default empty dictionary. Optional template arguments.

    **kwargs:
        Further arguments to pass to :class:`psynet.timeline.SliderPage`.
    """

    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],
        *,
        sound_locations: dict,
        start_value: float,
        min_value: float,
        max_value: float,
        n_steps: Union[str, int] = 10000,
        snap_values: Optional[Union[int, list]] = "sound_locations",
        autoplay: Optional[bool] = False,
        slider_id: Optional[str] = "sliderpage_slider",
        minimal_interactions: Optional[int] = 0,
        minimal_time: Optional[float] = None,
        continuous_updates: bool = False,
        **kwargs,
    ):
        warnings.warn(
            "psynet.page.AudioSliderPage is deprecated. Use :class:`psynet.modular_page.ModularPage` in combination with :class:`psynet.modular_page.Prompt` and :class:`psynet.modular_page.AudioSliderControl` instead.",
            DeprecationWarning,
        )

        if "media" not in kwargs:
            raise ValueError(
                "You must specify sounds in `media` you later want to play with the slider"
            )

        if isinstance(n_steps, str):
            if n_steps == "n_sounds":
                n_steps = len(sound_locations)
            else:
                raise ValueError(f"Invalid value of n_steps: {n_steps}")

        if isinstance(snap_values, str):
            if snap_values == "sound_locations":
                snap_values = list(sound_locations.values())
            else:
                raise ValueError(f"Invalid value of snap_values: {snap_values}")

        # Check if all stimuli specified in `sound_locations` are
        # also preloaded before the participant can start the trial
        audio = kwargs["media"].audio
        IDs_sound_locations = [ID for ID, _ in sound_locations.items()]
        IDs_media = []
        for key, value in audio.items():
            if isinstance(audio[key], dict) and "ids" in audio[key]:
                IDs_media.append(audio[key]["ids"])
            elif isinstance(audio[key], str):
                IDs_media.append(key)
            else:
                raise NotImplementedError(
                    "Currently we only support batch files or single files"
                )
        IDs_media = list(itertools.chain.from_iterable(IDs_media))

        if not any([i in IDs_media for i in IDs_sound_locations]):
            raise ValueError(
                "All stimulus IDs you specify in `sound_locations` need to be defined in `media` too."
            )

        # Check if all audio files are also really playable
        # ticks, step_size, diff = self._get_ticks_step_size_and_diff(snap_values, max_value, min_value)
        # if not all([location in ticks for _, location in sound_locations.items()]):
        #     raise ValueError('The slider does not contain all locations for the audio')

        self.sound_locations = sound_locations
        # All range checking is done in the parent class

        super().__init__(
            label,
            prompt=Prompt(prompt),
            control=AudioSliderControl(
                label=label,
                start_value=start_value,
                min_value=min_value,
                max_value=max_value,
                audio=audio,
                sound_locations=self.sound_locations,
                autoplay=autoplay,
                n_steps=n_steps,
                slider_id=slider_id,
                reverse_scale=kwargs.get("reverse_scale"),
                directional=kwargs.get("directional"),
                snap_values=snap_values,
                minimal_interactions=minimal_interactions,
                minimal_time=minimal_time,
            ),
            media=kwargs.get("media"),
            time_estimate=kwargs.get("time_estimate"),
        )

    def metadata(self, **kwargs):
        # pylint: disable=unused-argument
        return {
            **super().metadata(),
            "prompt": self.prompt.metadata,
            "control": self.control.metadata,
        }


class NumberInputPage(ModularPage):
    """
    .. deprecated:: 1.11.0
        Use :class:`psynet.modular_page.ModularPage` in combination with :class:`psynet.modular_page.Prompt` and :class:`psynet.modular_page.NumberControl` instead.

    This page is like :class:`psynet.timeline.TextInputPage`,
    except it forces the user to input a number.
    See :class:`psynet.timeline.TextInputPage` for argument documentation.
    """

    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],
        width: Optional[str] = None,  # e.g. "100px"
        time_estimate: Optional[float] = None,
        **kwargs,
    ):
        warnings.warn(
            "psynet.page.NumberInputPage is deprecated. Use :class:`psynet.modular_page.ModularPage` in combination with :class:`psynet.modular_page.Prompt` and :class:`psynet.modular_page.NumberControl` instead.",
            DeprecationWarning,
        )

        super().__init__(
            label,
            prompt=Prompt(self.prompt),
            control=NumberControl(width=self.width),
            time_estimate=self.time_estimate,
        )

    def metadata(self, **kwargs):
        # pylint: disable=unused-argument
        return {
            "prompt": self.prompt.metadata,
            "control": self.control.metadata,
        }


class Button:
    def __init__(self, button_id, *, label, min_width, own_line, start_disabled=False):
        self.id = button_id
        self.label = label
        self.min_width = min_width
        self.own_line = own_line
        self.start_disabled = start_disabled


class DebugResponsePage(PageMaker):
    """
    Implements a debugging page for responses.
    Displays a page to the user with information about the
    last response received from the participant.
    """

    def __init__(self):
        super().__init__(self.summarize_last_response, time_estimate=0)

    @staticmethod
    def summarize_last_response(participant):
        response = participant.response
        if response is None:
            return InfoPage("No response found to display.")
        page_type = escape(response.page_type)
        answer = escape(response.answer)
        metadata = escape(json.dumps(response.metadata, indent=4))
        return InfoPage(
            Markup(
                f"""
            <h3>Page type</h3>
            {page_type}
            <p class="vspace"></p>
            <h3>Answer</h3>
            {answer}
            <p class="vspace"></p>
            <h3>Metadata</h3>
            <pre style="max-height: 200px; overflow: scroll;">{metadata}</pre>
            """
            )
        )


class VolumeCalibration(Module):
    def __init__(
        self,
        url=resource_filename("psynet", "resources/audio/brown_noise.wav"),
        min_time=2.5,
        time_estimate=5.0,
        id_="volume_calibration",
    ):

        super().__init__(
            id_,
            self.page(min_time, time_estimate, id_),
            assets={
                "volume_calibration_audio": self.asset(url),
            },
        )

    def asset(self, url):
        if url.startswith("http"):
            return ExternalAsset(url=url)
        else:
            return CachedAsset(input_path=url)

    def page(self, min_time, time_estimate, id_):
        return PageMaker(
            lambda assets: ModularPage(
                id_,
                AudioPrompt(assets["volume_calibration_audio"], self.text(), loop=True),
                events={
                    "submitEnable": Event(is_triggered_by="trialStart", delay=min_time)
                },
            ),
            time_estimate=time_estimate,
        )

    def text(self):
        return Markup(
            """
            <p>
                Please listen to the following sound and adjust your
                computer's output volume until it is at a comfortable level.
            </p>
            <p>
                If you can't hear anything, there may be a problem with your
                playback configuration or your internet connection.
                You can refresh the page to try loading the audio again.
            </p>
            """
        )
