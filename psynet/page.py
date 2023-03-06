import json
import warnings
from math import ceil
from typing import List, Optional, Union

from dominate.dom_tag import dom_tag
from flask import Markup, escape
from pkg_resources import resource_filename

from .asset import CachedAsset, ExternalAsset
from .modular_page import AudioPrompt, ModularPage
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
from .utils import get_logger

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
