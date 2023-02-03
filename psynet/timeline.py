# pylint: disable=abstract-method

import json
import random
import time
from collections import Counter
from datetime import datetime
from functools import cached_property, reduce
from statistics import median
from typing import Callable, Dict, List, Optional, Union

import flask
import importlib_resources
from dallinger import db
from dallinger.config import get_config
from dominate import tags
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.collections import attribute_mapped_collection

from . import templates
from .data import SQLBase, SQLMixin, register_table
from .field import PythonObject, VarStore
from .utils import (
    NoArgumentProvided,
    call_function_with_context,
    check_function_args,
    dict_to_js_vars,
    format_datetime_string,
    get_args,
    get_language_dict,
    get_logger,
    log_time_taken,
    merge_dicts,
    render_string_with_translations,
    serialise,
    time_logger,
    unserialise_datetime,
)

logger = get_logger()


class Event(dict):
    """
    Defines an event that occurs on the front-end for a given page.
    This event is triggered once custom conditions are satisfied;
    it can then trigger future events to occur.
    One can define custom JS code to be run when these events execute
    in one of two ways.
    One approach is to register this custom JS code by writing something
    like this:

    ::

        psynet.trial.onEvent("myEventId", function() {
            // custom code goes here
        });

    A second approach is to add JS code directly to the ``js`` argument
    of the present function.

    The resulting object should be passed to the ``events`` parameter in
    :class:`~psynet.timeline.Page`.

    Parameters
    ----------

    is_triggered_by:
        Defines the triggers for the present event.
        A trigger can be specified either as a string corresponding to an event ID,
        for example ``"trialStart"``, or as an object of class :class:`~psynet.timeline.Trigger`.
        The latter case is more flexible because it allows a particular trigger to be delayed
        by a specified number of seconds.
        Multiple triggers can be defined by instead passing a list of these strings
        or :class:`~psynet.timeline.Trigger` objects.
        Alternatively, one can pass ``None``, in which case the event won't be triggered automatically,
        but instead will only be triggered if/when ``psynet.trial.registerEvent`` is called
        in the Javascript front-end.

    trigger_condition:
        If this is set to ``"all"`` (default), then all triggers must be satisfied before the
        event will be cued. If this is set to ``"any"``, then the event will be cued when
        any one of these triggers occurred.

    delay:
        Determines the time interval (in seconds) between the trigger condition being satisfied
        and the event being triggered (default = 0.0).

    once:
        If ``True``, then the event will only be cued once, at the point when the
        trigger condition is first satisfied. If ``False`` (default), then the event will be recued
        each time one of the triggers is hit again.

    message:
        Optional message to display when this event occurs (default = ``""``).

    message_color:
        CSS color specification for the message (default = ``"black"``).

    js:
        Optional Javascript code to execute when the event occurs (default = ``None``).

    """

    def __init__(
        self,
        is_triggered_by,
        trigger_condition: str = "all",
        delay: float = 0.0,
        once: bool = False,
        message: Optional[str] = None,
        message_color: str = "black",
        js: Optional[str] = None,
    ):
        if is_triggered_by is None:
            is_triggered_by = []
        elif not isinstance(is_triggered_by, list):
            is_triggered_by = [is_triggered_by]

        is_triggered_by = [
            x if isinstance(x, Trigger) else Trigger(x) for x in is_triggered_by
        ]

        super().__init__(
            is_triggered_by=is_triggered_by,
            trigger_condition=trigger_condition,
            delay=delay,
            once=once,
            message=message,
            message_color=message_color,
            js=js,
        )

    def add_trigger(self, trigger, **kwargs):
        if isinstance(trigger, str):
            t = Trigger(triggering_event=trigger, **kwargs)
        elif isinstance(trigger, Trigger):
            t = trigger
        else:
            raise ValueError("trigger must be an object of class str or Trigger.")
        self["is_triggered_by"].append(t)

    def add_triggers(self, *args):
        for arg in args:
            self.add_trigger(arg)


class Trigger(dict):
    def __init__(self, triggering_event, delay=0.0):
        assert isinstance(triggering_event, str)
        super().__init__(triggering_event=triggering_event, delay=float(delay))


def get_template(name):
    assert isinstance(name, str)
    path_all_templates = importlib_resources.files(templates)
    path_template = path_all_templates.joinpath(name)
    with open(path_template, "r") as file:
        return file.read()


class Elt:
    returns_time_credit = False
    time_estimate = None
    expected_repetitions = None
    id = None
    created_within_page_maker = False

    def consume(self, experiment, participant):
        raise NotImplementedError

    def render(self, experiment, participant):
        raise NotImplementedError

    def multiply_expected_repetitions(self, factor):
        # pylint: disable=unused-argument
        return self


class NullElt(Elt):
    def consume(self, experiment, participant):
        pass

    def render(self, experiment, participant):
        pass


class CodeBlock(Elt):
    """
    A timeline component that executes some back-end logic without showing
    anything to the participant.

    Parameters
    ----------

    function:
        A function with up to two arguments named ``participant`` and ``experiment``,
        that is executed once the participant reaches the corresponding part of the timeline.
    """

    def __init__(self, function):
        self.function = function

    def consume(self, experiment, participant):
        with time_logger("CodeBlock pre-commit", indent=2):
            db.session.commit()
        call_function_with_context(
            self.function,
            self=self,
            experiment=experiment,
            participant=participant,
        )
        with time_logger("CodeBlock post-commit", indent=2):
            db.session.commit()


class FixTime(Elt):
    def __init__(self, time_estimate: float):
        self.time_estimate = time_estimate
        self.expected_repetitions = 1

    def multiply_expected_repetitions(self, factor):
        self.expected_repetitions = self.expected_repetitions * factor


class StartFixTime(FixTime):
    def __init__(self, time_estimate, end_fix_time):
        super().__init__(time_estimate)
        self.end_fix_time = end_fix_time

    def consume(self, experiment, participant):
        participant.time_credit.start_fix_time(self.time_estimate)


class EndFixTime(FixTime):
    def consume(self, experiment, participant):
        participant.time_credit.end_fix_time(self.time_estimate)


class GoTo(Elt):
    def __init__(self, target):
        self.target = target

    def get_target(self, experiment, participant):
        # pylint: disable=unused-argument
        return self.target

    def consume(self, experiment, participant):
        target_elt = self.get_target(experiment, participant)
        participant.elt_id = target_elt.id
        # We subtract 1 because elt_id will be incremented again when
        # we return to the start of the advance page loop.
        # Remember that ``elt_id`` corresponds to a nested representation,
        # where each element corresponds to successively deeper and deeper
        # levels of page makers.
        # We therefore perform our subtraction to the last element
        # of the list.
        participant.elt_id[-1] -= 1


class ReactiveGoTo(GoTo):
    def __init__(
        self,
        function,  # function taking experiment, participant and returning a key
        targets,  # dict of possible target elements
    ):
        # pylint: disable=super-init-not-called
        self.function = function
        self.targets = targets
        self.check_args()

    def check_args(self):
        self.check_function()
        self.check_targets()

    def check_function(self):
        check_function_args(
            self.function, ("self", "experiment", "participant"), need_all=False
        )

    def check_targets(self):
        try:
            assert isinstance(self.targets, dict)
            for target in self.targets.values():
                assert isinstance(target, Elt)
        except AssertionError:
            raise TypeError("<targets> must be a dictionary of Elt objects.")

    def get_target(self, experiment, participant):
        val = call_function_with_context(
            self.function,
            self=self,
            experiment=experiment,
            participant=participant,
        )
        try:
            return self.targets[val]
        except KeyError:
            raise ValueError(
                f"ReactiveGoTo returned {val}, which is not present among the target keys: "
                + f"{list(self.targets)}."
            )


class MediaSpec:
    """
    This object enumerates the media assets available for a given
    :class:`~psynet.timeline.Page` object.

    Parameters
    ----------

    audio: dict
        A dictionary of audio assets.
        Each item can either be a string,
        corresponding to the URL for a single file (e.g. "/static/audio/test.wav"),
        or a dictionary, corresponding to metadata for a batch of media assets.
        A batch dictionary must contain the field "url", providing the URL to the batch file,
        and the field "ids", providing the list of IDs for the batch's constituent assets.
        A valid audio argument might look like the following:

        ::

            {
                'bier': '/static/bier.wav',
                'my_batch': {
                    'url': '/static/file_concatenated.mp3',
                    'ids': ['funk_game_loop', 'honey_bee', 'there_it_is'],
                    'type': 'batch'
                }
            }

    image: dict
        An analogously structured dictionary of image stimuli.

    video: dict
        An analogously structured dictionary of video stimuli.
    """

    modalities = ["audio", "image", "video"]

    def __init__(
        self,
        audio: Optional[dict] = None,
        image: Optional[dict] = None,
        video: Optional[dict] = None,
    ):
        from .asset import Asset

        if audio is None:
            audio = {}

        if image is None:
            image = {}

        if video is None:
            video = {}

        self.data = {"audio": audio, "image": image, "video": video}

        for modality in self.data.values():
            for key, value in modality.items():
                if isinstance(value, Asset):
                    modality[key] = value.url
                elif isinstance(value, dict):
                    for _key, _value in value.items():
                        if isinstance(_value, Asset):
                            value[_key] = _value.url

        assert list(self.data) == self.modalities

    @property
    def audio(self):
        return self.data["audio"]

    @property
    def image(self):
        return self.data["image"]

    @property
    def video(self):
        return self.data["video"]

    @property
    def ids(self):
        res = {}
        for media_type, media in self.data.items():
            res[media_type] = set()
            for key, value in media.items():
                if isinstance(value, str):
                    res[media_type].add(key)
                else:
                    assert isinstance(value, dict)
                    res[media_type].update(value["ids"])
        return res

    @property
    def num_files(self):
        counter = 0
        for modality in self.data.values():
            counter += len(modality)
        return counter

    def add(self, modality: str, entries: dict):
        if modality not in self.data:
            self.data[modality] = {}
        for key, value in entries.items():
            self.data[modality][key] = value

    @classmethod
    def merge(self, *args, overwrite: bool = False):
        if len(args) == 0:
            return MediaSpec()

        new_args = {}
        for modality in self.modalities:
            new_args[modality] = merge_dicts(
                *[x.data[modality] for x in args], overwrite=overwrite
            )

        return MediaSpec(**new_args)

    def check(self):
        assert isinstance(self.data, dict)
        for key, value in self.data.items():
            assert key in self.modalities
            ids = set()
            for file_id, file in value.items():
                if file_id in ids:
                    raise ValueError(
                        f"{file_id} occurred more than once in page's {key} specification."
                    )
                ids.add(file_id)
                if not isinstance(file, str):
                    if not isinstance(file, dict):
                        raise TypeError(
                            f"Media entry must either be a string URL or a dict (got {file})."
                        )
                    if not ("url" in file and "ids" in file):
                        raise ValueError(
                            "Batch specifications must contain both 'url' and 'ids' keys."
                        )
                    batch_ids = file["ids"]
                    if not isinstance(batch_ids, list):
                        raise TypeError(
                            f"The ids component of the batch specification must be a list (got {ids})."
                        )
                    for _id in batch_ids:
                        if not isinstance(_id, str):
                            raise TypeError(
                                f"Each id in the batch specification must be a string (got {_id})."
                            )
                        ids.add(_id)

    def to_json(self):
        return json.dumps(self.data)


class ProgressStage(dict):
    def __init__(
        self,
        time: Union[float, int, List],
        caption: str = "",
        color: str = "rgb(49, 124, 246)",
        persistent: bool = False,
    ):
        if isinstance(time, list):
            duration = time[1] - time[0]
        else:
            duration = time

        self["time"] = time
        self["duration"] = duration
        self["caption"] = caption
        self["color"] = color
        self["persistent"] = persistent


class ProgressDisplay(dict):
    def __init__(
        self,
        stages: List,
        start="trialStart",
        show_bar: bool = True,
        **kwargs,
    ):
        self.consolidate_stages(stages)

        if len(stages) == 0:
            _duration = 0.0
        else:
            last_stage = stages[-1]
            _duration = last_stage["time"][1]

        self["duration"] = _duration
        self["start"] = start
        self["show_bar"] = show_bar
        self["stages"] = stages

        self.validate()

        if "duration" in kwargs:
            logger.warning(
                "ProgressDisplay no longer takes a 'duration' argument, please remove it."
            )
            del kwargs["duration"]

        if (len(kwargs)) > 0:
            logger.warning(
                "The following unrecognized arguments were passed to ProgressDisplay: "
                + ", ".join(list(kwargs))
            )

    def consolidate_stages(self, stages):
        """
        Goes through the list of stages, and whenever the ``time`` argument
        is a single number, replaces this argument with a pair of numbers
        corresponding to the computed start time and end time for that stage.
        """
        _start_time = 0.0
        for s in stages:
            if not isinstance(s["time"], list):
                _duration = s["time"]
                _end_time = _start_time + _duration
                s["time"] = [_start_time, _end_time]
            _end_time = s["time"][1]
            _start_time = _end_time

    def validate(self):
        stages = self["stages"]
        for i, stage in enumerate(stages):
            start_time = stage["time"][0]
            if i == 0:
                if start_time != 0.0:
                    raise ValueError(
                        "The first stage in the progress bar must have a start time of 0.0."
                    )
            else:
                prev_stage = stages[i - 1]
                prev_stage_end_time = prev_stage["time"][1]
                if start_time != prev_stage_end_time:
                    raise ValueError(
                        f"The start time of stages[{i}] did not match the end time of the previous stage."
                    )
            if i == len(stages) - 1:
                end_time = stage["time"][1]
                if end_time != self["duration"]:
                    raise ValueError(
                        "The final stage must have an end time equal to the progress bar's duration."
                    )


class Page(Elt):
    """
    The base class for pages, customised by passing values to the ``__init__``
    function and by overriding the following methods:

    * :meth:`~psynet.timeline.Page.format_answer`
    * :meth:`~psynet.timeline.Page.validate`
    * :meth:`~psynet.timeline.Page.metadata`

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.

    template_path:
        Path to the jinja2 template to use for the page.

    template_str:
        Alternative way of specifying the jinja2 template as a string.

    template_arg:
        Dictionary of arguments to pass to the jinja2 template.

    label:
        Internal label to give the page, used for example in results saving.

    js_vars:
        Dictionary of arguments to instantiate as global Javascript variables.

    media: :class:`psynet.timeline.MediaSpec`
        Optional specification of media assets to preload
        (see the documentation for :class:`psynet.timeline.MediaSpec`).

    scripts:
        Optional list of scripts to include in the page.
        Each script should be represented as a string, which will be passed
        verbatim to the page's HTML.

    css:
        Optional list of CSS specification to include in the page.
        Each specification should be represented as a string, which will be passed
        verbatim to the page's HTML.
        A valid CSS specification might look like this:

        ::

            .modal-content {
                background-color: #4989C8;
                margin: auto;
                padding: 20px;
                border: 1px solid #888;
                width: 80%;
            }

            .close {
                color: #aaaaaa;
                float: right;
                font-size: 28px;
                font-weight: bold;
            }

    contents:
        Optional dictionary to store some experiment specific data. For example, in an experiment about melodies, the contents property might look something like this: {”melody”: [1, 5, 2]}.

    save_answer:
        If ``True`` (default), then the answer generated by the page is saved to ``participant.answer``,
        and a link to the corresponding ``Response`` object is saved in ``participant.last_response_id``.
        If ``False``, these slots are left unchanged.
        If a string, then then the answer is not only saved to ``particicipant.answer`` and ``participant.last_response_id``,
        but it is additionally saved as a participant variable named by that string.

    events:
        An optional dictionary of event specifications for the page.
        This determines the timing of various Javascript events that happen on the page.
        Each key of this dictionary corresponds to a particular event.
        Each value should then correspond to an object of class :class:`~psynet.timeline.Event`.
        The :class:`~psynet.timeline.Event` object specifies how the event is triggered by other events.
        For example, if I want to define an event that occurs 3 seconds after the trial starts,
        I would write ``events={"myEvent": Event(is_triggered_by="trialStart", delay=3.0)}``.
        Useful standard events to know are
        ``trialStart`` (start of the trial),
        ``promptStart`` (start of the prompt),
        ``promptEnd`` (end of the prompt),
        ``recordStart`` (beginning of a recording),
        ``recordEnd`` (end of a recording),
        ``responseEnable`` (enables the response options),
        and ``submitEnable`` (enables the user to submit their response).
        These events and their triggers are set to sensible defaults,
        but the user is welcome to modify them for greater customization.
        See also the ``update_events`` methods of
        :class:`~psynet.modular_page.Prompt`
        and
        :class:`~psynet.modular_page.Control`,
        which provide alternative ways to customize event sequences for modular pages.

    progress_display
        Optional :class:`~psynet.timeline.ProgressDisplay` object.

    start_trial_automatically
        If ``True`` (default), the trial starts automatically, e.g. by the playing
        of a queued audio file. Otherwise the trial will wait for the
        trialPrepare event to be triggered (e.g. by clicking a 'Play' button,
        or by calling `psynet.trial.registerEvent("trialPrepare")` in JS).

    bot_response
        Optional function to call when this page is consumed by a bot.
        This will override any ``bot_response`` function specified in the class's
        ``bot_response`` method.

    Attributes
    ----------

    contents : dict
        A dictionary containing experiment specific data.

    session_id : str
        If session_id is not None, then it must be a string. If two consecutive pages occur with the same session_id, then when it’s time to move to the second page, the browser will not navigate to a new page, but will instead update the Javascript variable psynet.page with metadata for the new page, and will trigger an event called pageUpdated. This event can be listened for with Javascript code like window.addEventListener(”pageUpdated”, ...).

    dynamically_update_progress_bar_and_bonus : bool
        If ``True``, then the page will regularly poll for updates to the progress bar and the bonus.
        If ``False`` (default), the progress bar and bonus are updated only on page refresh or on transition to
        the next page.
    """

    returns_time_credit = True
    dynamically_update_progress_bar_and_bonus = False

    def __init__(
        self,
        time_estimate: Optional[float] = None,
        template_path: Optional[str] = None,
        template_str: Optional[str] = None,
        template_arg: Optional[Dict] = None,
        label: str = "untitled",
        js_vars: Optional[Dict] = None,
        media: Optional[MediaSpec] = None,
        scripts: Optional[List] = None,
        css: Optional[List] = None,
        contents: Optional[Dict] = None,
        session_id: Optional[str] = None,
        save_answer: bool = True,
        events: Optional[Dict] = None,
        progress_display: Optional[ProgressDisplay] = None,
        start_trial_automatically: bool = True,
        bot_response=NoArgumentProvided,
    ):
        if template_arg is None:
            template_arg = {}
        if js_vars is None:
            js_vars = {}
        if contents is None:
            contents = {}

        if template_path is None and template_str is None:
            raise ValueError("Must provide either template_path or template_str.")
        if template_path is not None and template_str is not None:
            raise ValueError("Cannot provide both template_path and template_str.")

        if template_path is not None:
            with open(template_path, "r") as file:
                template_str = file.read()

        assert len(label) <= 250
        assert isinstance(template_arg, dict)
        assert isinstance(label, str)

        self.time_estimate = time_estimate
        self.template_str = template_str
        self.template_arg = template_arg
        self.label = label
        self.js_vars = js_vars

        self.expected_repetitions = 1

        self.media = MediaSpec() if media is None else media
        self.media.check()

        self.scripts = [] if scripts is None else [flask.Markup(x) for x in scripts]
        assert isinstance(self.scripts, list)

        self.css = [] if css is None else [flask.Markup(x) for x in css]
        assert isinstance(self.css, list)

        self._contents = contents
        self.session_id = session_id
        self.save_answer = save_answer
        self.start_trial_automatically = start_trial_automatically

        self.events = {
            **self.prepare_default_events(),
            **({} if events is None else events),
        }

        if progress_display is None:
            progress_display = ProgressDisplay(stages=[], show_bar=False)
        self.progress_display = progress_display

        self._bot_response = bot_response

    def call__bot_response(self, experiment, bot):
        from .bot import BotResponse

        if self._bot_response == NoArgumentProvided:
            res = self.get_bot_response(experiment, bot)
        elif callable(self._bot_response):
            res = call_function_with_context(
                self._bot_response,
                experiment=experiment,
                bot=bot,
                participant=bot,
                page=self,
            )
        else:
            res = self._bot_response

        if not isinstance(res, BotResponse):
            res = BotResponse(answer=res)

        return res

    def get_bot_response(self, experiment, bot):
        """
        This function is used when a bot simulates a participant responding to a given page.
        In the simplest form, the function just returns the value of the
        answer that the bot returns.
        For more sophisticated treatment, the function can return a
        ``BotResponse`` object which contains other parameters
        such as ``blobs`` and ``metadata``.
        """
        raise NotImplementedError

    def prepare_default_events(self):
        return {
            "trialConstruct": Event(is_triggered_by=None, once=True),
            "trialPrepare": Event(
                is_triggered_by="trialConstruct"
                if self.start_trial_automatically
                else None,
                once=True,
            ),
            "trialStart": Event(is_triggered_by="trialPrepare", once=True),
            "responseEnable": Event(is_triggered_by="trialStart", delay=0.0, once=True),
            "submitEnable": Event(is_triggered_by="trialStart", delay=0.0, once=True),
            "trialFinish": Event(
                is_triggered_by=None
            ),  # only called when trial comes to a natural end
            "trialFinished": Event(is_triggered_by="trialFinish"),
            "trialStop": Event(is_triggered_by=None),  # only called at premature end
            "trialStopped": Event(is_triggered_by="trialStop"),
        }

    def __json__(self, participant):
        return {
            "attributes": self.attributes(participant),
            "contents": self.contents,
        }

    def attributes(self, participant):
        """
        Returns a dictionary containing the `session_id`, the page `type`, and the `page_uuid` .
        """
        from psynet.page import UnityPage

        return {
            "session_id": self.session_id,
            "type": type(self).__name__,
            "auth_token": participant.auth_token,
            "page_uuid": participant.page_uuid,
            "is_unity_page": isinstance(self, UnityPage),
        }

    @property
    def contents(self):
        return self._contents

    @contents.setter
    def contents(self, contents):
        self._contents = contents

    @property
    def initial_download_progress(self):
        if self.media.num_files > 0:
            return 0
        else:
            return 100

    def visualize(self, trial):
        return ""

    def consume(self, experiment, participant):
        participant.page_uuid = experiment.make_uuid()

    @log_time_taken
    def process_response(
        self,
        raw_answer,
        blobs,
        metadata,
        experiment,
        participant,
        client_ip_address,
        answer=NoArgumentProvided,
    ):
        if raw_answer == NoArgumentProvided and answer == NoArgumentProvided:
            raise ValueError("At least one of raw_answer and answer must be provided.")
        if blobs is None:
            blobs = {}
        if metadata is None:
            metadata = {}

        resp = Response(
            participant=participant,
            label=self.label,
            page_type=type(self).__name__,
            client_ip_address=client_ip_address,
        )
        db.session.add(resp)
        db.session.commit()

        if answer == NoArgumentProvided:
            answer = self.format_answer(
                raw_answer,
                blobs=blobs,
                metadata=metadata,
                experiment=experiment,
                participant=participant,
                trial=participant.current_trial,
                response=resp,
            )

        extra_metadata = self.metadata(
            metadata=metadata,
            raw_answer=raw_answer,
            answer=answer,
            experiment=experiment,
            participant=participant,
        )

        combined_metadata = {**metadata, **extra_metadata}

        resp.answer = answer
        resp.metadata = combined_metadata

        db.session.commit()

        if self.save_answer:
            participant.last_response_id = resp.id
            if len(participant.answer_accumulators) > 0:
                page_label = self.label
                accumulator = participant.answer_accumulators[-1]
                answer_label = self._find_answer_label(page_label, accumulator)
                accumulator[answer_label] = resp.answer
                flag_modified(participant, "answer_accumulators")
            else:
                participant.answer = resp.answer
            participant.answer_is_fresh = True
            if isinstance(self.save_answer, str):
                participant.var.set(self.save_answer, resp.answer)
        else:
            participant.answer_is_fresh = False

        participant.browser_platform = metadata.get(
            "platform", "Browser platform info could not be retrieved."
        )

        db.session.commit()
        return resp

    def _find_answer_label(self, page_label, accumulator):
        if page_label not in accumulator:
            return page_label
        else:
            i = 0
            while i < 1e7:
                i += 1
                label = f"{page_label}_{i}"
                if label not in accumulator:
                    return label
        raise ValueError("Failed to construct an appropriate answer label")

    def metadata(self, **kwargs):
        """
        Compiles metadata about the page or its response from the participant.
        This metadata will be merged with the default metadata object returned
        from the browser, with any duplicate terms overwritten.

        Parameters
        ----------

        **kwargs
            Keyword arguments, including:

            1. ``raw_answer``:
               The raw answer returned from the participant's browser.

            2. ``answer``:
               The formatted answer.

            3. ``metadata``:
               The original metadata returned from the participant's browser.

            3. ``experiment``:
               An instantiation of :class:`psynet.experiment.Experiment`,
               corresponding to the current experiment.

            4. ``participant``:
               An instantiation of :class:`psynet.participant.Participant`,
               corresponding to the current participant.

        Returns
        -------

        dict
            A dictionary of metadata.
        """
        return {}

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

    def pre_render(self):
        """
        This method is called immediately prior to rendering the page for
        the participant. It will be called again each time the participant
        refreshes the page.
        """
        pass

    def render(self, experiment, participant):
        internal_js_vars = {
            "authToken": participant.auth_token,
            "pageUuid": participant.page_uuid,
            "dynamicallyUpdateProgressBarAndBonus": self.dynamically_update_progress_bar_and_bonus,
        }
        locale = participant.get_locale(experiment)
        language_dict = get_language_dict(locale)

        all_template_args = {
            **self.template_arg,
            "init_js_vars": flask.Markup(
                dict_to_js_vars({**self.js_vars, **internal_js_vars})
            ),
            "define_media_requests": flask.Markup(self.define_media_requests),
            "initial_download_progress": self.initial_download_progress,
            "min_accumulated_bonus_for_abort": experiment.var.min_accumulated_bonus_for_abort,
            "show_abort_button": experiment.var.show_abort_button,
            "show_footer": experiment.var.show_footer,
            "show_bonus": experiment.var.show_bonus,
            "basic_bonus": "%.2f" % participant.time_credit.get_bonus(),
            "extra_bonus": "%.2f" % participant.performance_bonus,
            "total_bonus": "%.2f"
            % (participant.performance_bonus + participant.time_credit.get_bonus()),
            "show_progress_bar": experiment.var.show_progress_bar,
            "progress_percentage": round(participant.progress * 100),
            "contact_email_on_error": get_config().get("contact_email_on_error"),
            "experiment_title": get_config().get("title"),
            "app_id": experiment.app_id,
            "participant": participant,
            "auth_token": participant.auth_token,
            "worker_id": participant.worker_id,
            "scripts": self.scripts,
            "css": self.css,
            "events": self.events,
            "trial_progress_display_config": self.progress_display,
            "attributes": self.attributes,
            "contents": self.contents,
            "supported_language_dict": {
                iso: language_dict[iso] for iso in experiment.var.supported_locales
            },
            "currency": experiment.var.currency,
            "current_locale": locale,
            "allow_switching_locale": experiment.var.allow_switching_locale,
        }
        return render_string_with_translations(
            template_string=self.template_str, locale=locale, **all_template_args
        )

    @property
    def define_media_requests(self):
        return f"psynet.media.requests = JSON.parse('{self.media.to_json()}');"

    def multiply_expected_repetitions(self, factor: float):
        self.expected_repetitions = self.expected_repetitions * factor
        return self


class PageMaker(Elt):
    """
    A page maker is defined by a function that is executed when
    the participant requests the relevant page.

    Parameters
    ----------

    function:
        A function that may take up to two arguments, named ``experiment``
        and ``participant``. These arguments correspond to instantiations
        of the class objects :class:`psynet.experiment.Experiment`
        and :class:`psynet.participant.Participant` respectively.
        The function should return either a single test element
        (e.g. :class:`psynet.timeline.Page`, :class:`psynet.timeline.PageMaker`,
        :class:`psynet.timeline.CodeBlock`) or a list of such elements.
        Note that :class:`psynet.timeline.PageMaker` objects can be nested
        arbitrarily deeply. Note also that, if the page maker returns multiple pages,
        then the function will be recomputed each time the participant progresses
        to the next page. This functionality can be used to make the latter
        pages depend on the earlier pages in the page maker.

    time_estimate:
        Time estimated to complete the segment. This time estimate is used
        for predicting the overall length of the experiment and hence
        generating the progress bar. The actual time credit given to the
        participant is determined by ``time_estimate`` parameters
        provided to the pages generated by ``function``.
        However, there is an exception provided for back-compatibility:
        if ``function`` generates a list containing solely :class:`psynet.timeline.Page`
        or :class:`psynet.timeline.PageMaker` objects, and if those objects are all missing
        ``time_estimate`` values, then these ``time_estimate`` values will be imputed by dividing
        the parent :class:`psynet.timeline.PageMaker`'s ``time_estimate``
        by the number of produced elements.
    """

    returns_time_credit = True

    def __init__(
        self,
        function,
        time_estimate,
        accumulate_answers: bool = False,
        label: str = "page_maker",
    ):
        self.function = function
        self.time_estimate = time_estimate
        self.accumulate_answers = accumulate_answers
        self.expected_repetitions = 1
        self.label = label

    def resolve(self, experiment, participant, position):
        """
        This function 'resolves' the page maker by calling its underlying
        function and hence returning its underlying timeline logic.

        Parameters
        ----------
        experiment :
            The experiment instance.

        participant :
            The participant instance.

        position :
            The position of the page maker within the timeline.
            This is used for setting the IDs of the timeline
            elements that are produced.

        Returns
        -------

        A list of ``Elt`` objects.
        """
        res = call_function_with_context(
            self.function,
            self=self,
            experiment=experiment,
            participant=participant,
        )
        res = join(res)
        self.impute_time_estimates(res)
        self.check_time_estimates(res)

        res = join(
            StartAccumulateAnswers() if self.accumulate_answers else None,
            res,
            EndAccumulateAnswers() if self.accumulate_answers else None,
        )
        for i, elt in enumerate(res):
            elt.id = position + [i]
            elt.created_within_page_maker = True
        return res

    def impute_time_estimates(self, elts):
        # This is performed for back-compatibility;
        # basically, if all the elements are pages or page makers
        # and none of them have time estimates, then we compute
        # their time estimates by equally subdividing the time estimate
        # for the parent page maker.
        if all(
            [
                isinstance(elt, (Page, PageMaker)) and elt.time_estimate is None
                for elt in elts
            ]
        ):
            n = len(elts)
            for elt in elts:
                elt.time_estimate = self.time_estimate / n

    def check_time_estimates(self, elts):
        for elt in elts:
            if elt.returns_time_credit and elt.time_estimate is None:
                raise RuntimeError(
                    f"One of the elements in the page maker was missing a time estimate ({elt})"
                )

    def multiply_expected_repetitions(self, factor: float):
        self.expected_repetitions = self.expected_repetitions * factor
        return self


class PageMakerFinishedError(Exception):
    pass


class EndPage(Page):
    def __init__(self, template_filename, label="EndPage"):
        super().__init__(
            time_estimate=0,
            template_str=get_template(template_filename),
            label=label,
        )

    def consume(self, experiment, participant):
        super().consume(experiment, participant)
        self.finalize_participant(experiment, participant)

    def get_bot_response(self, experiment, bot):
        bot.status = "approved"
        return None

    def finalize_participant(self, experiment, participant):
        """
        Executed when the participant completes the experiment.

        Parameters
        ----------

        experiment:
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant:
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """


class Timeline:
    def __init__(self, *args):
        elts = join(*args)
        self.elts = elts
        self.modules, self.module_list = self.compile_modules()
        self.check_elts()
        self.add_elt_ids()
        self.estimated_time_credit = CreditEstimate(self.elts)

    def compile_modules(self):
        modules = {}
        module_list = []
        for elt in self.elts:
            if isinstance(elt, StartModule):
                module = elt.module
                if module.id in modules:
                    raise ValueError(f"Duplicated module name detected: {module.id}")
                modules[module.id] = module
                module_list.append(module)
        return modules, module_list

    def check_elts(self):
        assert isinstance(self.elts, list)
        assert len(self.elts) > 0
        if not isinstance(self.elts[-1], EndPage):
            raise ValueError("The final element in the timeline must be an EndPage.")
        self.check_for_time_estimate()
        self.check_start_fix_times()
        self.check_for_consent()
        self.check_modules()

    def check_for_time_estimate(self):
        for i, elt in enumerate(self.elts):
            if (
                isinstance(elt, Page) or isinstance(elt, PageMaker)
            ) and elt.time_estimate is None:
                raise ValueError(
                    f"Element {i} of the timeline was missing a time_estimate value."
                )

    def check_start_fix_times(self):
        try:
            _fix_time = False
            for i, elt in enumerate(self.elts):
                if isinstance(elt, StartFixTime):
                    assert not _fix_time
                    _fix_time = True
                elif isinstance(elt, EndFixTime):
                    assert _fix_time
                    _fix_time = False
        except AssertionError:
            raise ValueError(
                "Nested 'fix-time' constructs detected. This typically means you have "
                "nested conditionals or while loops with fix_time_credit=True. "
                "Such constructs cannot be nested; instead you should choose one level "
                "at which to set fix_time_credit=True. An example where this error might "
                "occur is when you put a TrialMaker within a switch. In this case, "
                "make sure to set `fix_time_credit=False` within that switch."
            )

    def check_modules(self):
        modules = [x.label for x in self.elts if isinstance(x, StartModule)]
        counts = Counter(modules)
        duplicated = [key for key, value in counts.items() if value > 1]
        if len(duplicated) > 0:
            raise ValueError(
                "The following module ID(s) were duplicated in your timeline: "
                + ", ".join(duplicated)
                + ". PsyNet timelines may not contain duplicated module IDs. "
                + "You will need to update your timeline to fix this. "
                + "This will probably mean updating one or more `id_` arguments in your "
                + "trial makers and/or pre-screening tasks."
            )

    def check_for_consent(self):
        from psynet.consent import Consent
        from psynet.page import InfoPage

        first_elt = self.elts[0]
        # ignore unless the timeline is fully initialized
        if (
            isinstance(first_elt, InfoPage)
            and first_elt.content == "Placeholder timeline"
        ):
            return
        if all([not isinstance(elt, Consent) for elt in self.elts]):
            raise ValueError("At least one element in the timeline must be a consent.")

    # @property
    # def modules(self):
    #     return {
    #         "modules": [
    #             {"id": elt.module.id}
    #             for elt in self.elts
    #             if isinstance(elt, StartModule)
    #         ]
    #     }
    #
    # # def report_module_status(self):

    @cached_property
    def trial_makers(self):
        return {
            e.trial_maker_id: e.trial_maker
            for e in self.elts
            if isinstance(e, RegisterTrialMaker)
        }

    def get_trial_maker(self, trial_maker_id):
        try:
            return self.trial_makers[trial_maker_id]
        except IndexError:
            raise RuntimeError(f"Couldn't find trial maker with id = {trial_maker_id}.")

    def add_elt_ids(self):
        for i, elt in enumerate(self.elts):
            elt.id = [i]
        for i, elt in enumerate(self.elts):
            if elt.id[0] != i:
                raise ValueError(
                    "Failed to set unique IDs for each element in the timeline "
                    + f"(the element at 0-indexed position {i} ended up with the ID {elt.id}). "
                    + "This usually means that the same Python object instantiation is reused multiple times "
                    + "in the same timeline. This kind of reusing is not permitted, instead you should "
                    + "create a fresh instantiation of each element."
                )

    def __len__(self):
        return len(self.elts)

    def __getitem__(self, key):
        return self.elts[key]

    @log_time_taken
    def get_current_elt(self, experiment, participant):
        # Remember, ``participant.elt_id`` corresponds to a list representation
        # of the participant's position in the timeline, where the first element corresponds
        # to the index of the participant within the timeline's underlying
        # list representation, and successive elements (if any) represent
        # the participant's position within (potentially nested) page makers.
        # For example, ``[10, 3, 2]`` would mean go to
        # element 10 in the timeline (0-indexing),
        # which must be a page maker;
        # go to element 3 within that page maker, which must also be a page maker;
        # go to element 2 within that page maker.
        #
        # The current function gets the ``Elt`` corresponding to the participant's
        # current ``elt_id``. It works by iterating through the ``participant.elt_id``
        # list from first to last element, each time 'resolving' the corresponding
        # page maker (which means computing its underlying function),
        # taking the list of test elements that comes out,
        # going to the corresponding element within that list,
        # resolving it, and so on.
        #
        num_levels = len(participant.elt_id)
        for depth, index in enumerate(participant.elt_id):
            # Suppose ``participant.elt_id`` = ``[10, 3, 2]``
            # then:
            # depth: 0, 1, 2
            # index: 10, 3, 2
            try:
                # index_max tells us the maximum allowed elt_id at this level of the hierarchy.
                # The top level is the number of Elts in the timeline, minus one;
                # the next level is the number of Elts in the trialmaker minus one, and so on.
                index_max = participant.elt_id_max[depth]
            except IndexError:
                index_max = None
            if depth == 0:
                # We start just by going to the ith element in the timeline.
                selected_elt = self[index]
            else:
                assert isinstance(selected_elt, PageMaker)
                try:
                    # ``position`` corresponds to the page maker's location within the timeline.
                    # For example, suppose we are on the third level of the example above, then:
                    # depth: 2
                    # index: 2
                    # position: ``[10, 3]``
                    if index_max is not None and index > index_max:
                        raise IndexError
                    position = participant.elt_id[0:depth]
                    resolved = selected_elt.resolve(experiment, participant, position)
                    if index_max is None:
                        participant.elt_id_max.append(len(resolved) - 1)
                    selected_elt = resolved[index]
                except IndexError:
                    # This occurs if the requested index goes past the number of
                    # elements produced by the current page maker.
                    # If this occurs in the deepest level of ``participant.elt_id``,
                    # it's fine; it normally means that the participant has finished the
                    # page maker that is currently under consideration, and is ready
                    # to move to the next part of the timeline. In this case we therefore
                    # raise a ``PageMakerFinishedError``.
                    # However, if this happens at a higher level of ``participant.elt_id``,
                    # something weird has happened.
                    assert depth + 1 == num_levels

                    raise PageMakerFinishedError

        return selected_elt

    @log_time_taken
    def advance_page(self, experiment, participant):
        finished = False
        while not finished:
            with time_logger("advance_page", indent=8):
                with time_logger("advance_page update participant elt_id"):
                    participant.elt_id[-1] += 1

                try:
                    new_elt = self.get_current_elt(experiment, participant)
                except PageMakerFinishedError:
                    participant.elt_id = participant.elt_id[:-1]
                    participant.elt_id_max = participant.elt_id_max[:-1]
                    continue
                if isinstance(new_elt, PageMaker):
                    participant.elt_id.append(-1)
                    continue

                with time_logger(
                    f"consuming elt {new_elt.id} ({type(new_elt)})", indent=12
                ):
                    new_elt.consume(experiment, participant)

                # with time_logger("advance_page commit"):
                #     db.session.commit()

                if isinstance(new_elt, Page):
                    finished = True

    def estimated_max_bonus(self, wage_per_hour):
        return self.estimated_time_credit.get_max("bonus", wage_per_hour=wage_per_hour)

    def estimated_completion_time(self, wage_per_hour):
        return self.estimated_time_credit.get_max("time", wage_per_hour=wage_per_hour)


class CreditEstimate:
    def __init__(self, elts):
        self._elts = elts
        self._max_time = self._estimate_max_time(elts)

    def get_max(self, mode, wage_per_hour=None):
        if mode == "time":
            return self._max_time
        elif mode == "bonus":
            assert wage_per_hour is not None
            return self._max_time * wage_per_hour / (60 * 60)
        elif mode == "all":
            return {
                "time_seconds": self._max_time,
                "time_minutes": self._max_time / 60,
                "time_hours": self._max_time / (60 * 60),
                "bonus": self.get_max(mode="bonus", wage_per_hour=wage_per_hour),
            }

    def _estimate_max_time(self, elts):
        pos = 0
        time_credit = 0.0
        n_elts = len(elts)

        while True:
            if pos == n_elts:
                return time_credit

            elt = elts[pos]

            if elt.returns_time_credit:
                time_credit += elt.time_estimate * elt.expected_repetitions

            if isinstance(elt, StartFixTime):
                pos = elts.index(elt.end_fix_time)

            elif isinstance(elt, EndFixTime):
                time_credit += elt.time_estimate * elt.expected_repetitions
                pos += 1

            elif isinstance(elt, StartSwitch):
                time_credit += max(
                    [
                        self._estimate_max_time(
                            elts[
                                elts.index(branch_start) : (
                                    1 + elts.index(elt.end_switch)
                                )
                            ]
                        )
                        for key, branch_start in elt.branch_start_elts.items()
                    ]
                )
                pos = elts.index(elt.end_switch)

            elif isinstance(elt, EndSwitchBranch):
                pos = elts.index(elt.target)

            elif isinstance(elt, EndPage):
                return time_credit

            else:
                pos += 1


class FailedValidation:
    def __init__(self, message="Invalid response, please try again."):
        self.message = message


@register_table
class _Response(SQLBase, SQLMixin):
    """
    This virtual class is not to be used directly.
    We use it as the parent class for the ``Response`` class
    to sidestep the following SQLAlchemy error:

    sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata'
    is reserved for the MetaData instance when using a declarative base class.
    """

    __tablename__ = "response"


class Response(_Response):
    """
    A database-backed object that stores the participant's response to a
    :class:`~psynet.timeline.Page`.
    By default, one such object is created each time the participant
    tries to advance to a new page.

    Attributes
    ----------

    answer
        The participant's answer, after formatting.

    page_type: str
        The type of page administered.

    successful_validation: bool
        Whether the response validation was successful,
        allowing the participant to advance to the next page.
        Stored in ``property2`` in the database.
        (Not yet implemented)

    client_ip_address : str
        The participant's IP address as reported by Flask.
    """

    __extra_vars__ = {}

    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    participant = relationship(
        "psynet.participant.Participant",
        backref="all_responses",
        foreign_keys=[participant_id],
    )

    question = Column(String)
    answer = Column(PythonObject)
    page_type = Column(String)
    successful_validation = Column(Boolean)
    client_ip_address = Column(String)

    # metadata is a protected attribute in SQLAlchemy, hence the underscore
    # and the functional setter/getter.
    metadata_ = Column(PythonObject)

    @property
    def metadata(self):
        """
        A dictionary of metadata associated with the Response object.
        Stored in the ``details`` field in the database.
        """
        return self.metadata_

    @metadata.setter
    def metadata(self, metadata):
        self.metadata_ = metadata

    async_processes = relationship("AsyncProcess")
    # assets = relationship(
    #     "Asset", collection_class=attribute_mapped_collection("label_or_key")
    # )

    errors = relationship("ErrorRecord")

    def __init__(
        self,
        participant,
        label,
        page_type,
        client_ip_address,
        answer=None,
        metadata=None,
    ):
        self.participant_id = participant.id
        self.question = label
        self.page_type = page_type
        self.metadata = metadata
        self.client_ip_address = client_ip_address
        self.answer = answer
        self.metadata = metadata


def is_list_of(x, what):
    if not isinstance(x, list):
        return False
    for val in x:
        if not isinstance(val, what):
            return False
    return True


def join(*args):
    from .asset import AssetSpecification

    valid_classes = (AssetSpecification, Elt, Module)

    for i, arg in enumerate(args):
        if not (
            (arg is None)
            or (isinstance(arg, valid_classes) or is_list_of(arg, valid_classes))
        ):
            raise TypeError(
                f"Element {i + 1} of the input to join() was neither an Asset/Elt/Module nor a list of such objects: ({arg})."
            )

    args = [a for a in args if a is not None]

    if len(args) == 0:
        return []
    elif len(args) == 1:
        if isinstance(args[0], Elt):
            return [args[0]]
        elif isinstance(args[0], Module):
            return args[0].resolve()
        else:
            return args[0]
    else:

        def f(x, y):
            if isinstance(x, Module):
                x = x.resolve()
            if isinstance(y, Module):
                y = y.resolve()
            if x is None:
                return y
            elif y is None:
                return x
            elif isinstance(x, Elt) and isinstance(y, Elt):
                return [x, y]
            elif isinstance(x, Elt) and isinstance(y, list):
                return [x] + y
            elif isinstance(x, list) and isinstance(y, Elt):
                return x + [y]
            elif isinstance(x, list) and isinstance(y, list):
                return x + y
            else:
                raise ValueError(
                    f"Don't know how to join the following two timeline components: {x}, {y}."
                )

        return reduce(f, args)


class StartWhile(NullElt):
    def __init__(self, label):
        # targets = {
        #     True: self,
        #     False: end_while
        # }
        # super().__init__(condition, targets)
        super().__init__()
        self.label = label


class EndWhile(NullElt):
    def __init__(self, label):
        super().__init__()
        self.label = label


def while_loop(
    label: str,
    condition: Callable,
    logic,
    expected_repetitions: int,
    max_loop_time: float = None,
    fix_time_credit=True,
    fail_on_timeout=True,
):
    """
    Loops a series of elts while a given criterion is satisfied.
    The criterion function is evaluated once at the beginning of each loop.

    Parameters
    ----------

    label:
        Internal label to assign to the construct.

    condition:
        A function with up to two arguments named ``participant`` and ``experiment``,
        that is executed once the participant reaches the corresponding part of the timeline,
        returning a Boolean.

    logic:
        An elt (or list of elts) to display while ``condition`` returns ``True``.

    expected_repetitions:
        The number of times the loop is expected to be seen by a given participant.
        This doesn't have to be completely accurate, but it is used for estimating the length
        of the total experiment.

    max_loop_time:
        The maximum time in seconds for staying in the loop. Once exceeded, the participant is
        is presented the ``UnsuccessfulEndPage``. Default: None.

    fix_time_credit:
        Whether participants should receive the same time credit irrespective of whether
        ``condition`` returns ``True`` or not; defaults to ``True``, so that all participants
        receive the same credit.

    fail_on_timeout:
        Whether the participants should be failed when the ``max_loop_time`` is reached.
        Setting this to ``False`` will not return the ``UnsuccessfulEndPage`` when maximum time has elapsed
        but allow them to proceed to the next page.

    Returns
    -------

    list
        A list of elts that can be embedded in a timeline using :func:`psynet.timeline.join`.
    """

    start_while = StartWhile(label)
    end_while = EndWhile(label)

    logic = join(logic)
    logic = multiply_expected_repetitions(logic, expected_repetitions)

    def condition_wrapped(participant, experiment):
        result = call_function_with_context(
            condition, participant=participant, experiment=experiment
        )
        logger.info(f"Evaluating while_loop ({label}) condition: result = {result}")
        return result

    conditional_logic = join(logic, GoTo(start_while))

    def with_namespace(x=None):
        prefix = f"__{label}__{x}"
        if x is None:
            return prefix
        return f"{prefix}__{x}"

    if max_loop_time is not None:
        max_loop_time_condition = (
            lambda participant, experiment: (
                datetime.now()
                - unserialise_datetime(
                    participant.var.get(with_namespace("loop_start_time"))
                )
            ).seconds
            > max_loop_time
        )
    else:
        max_loop_time_condition = lambda participant, experiment: False  # noqa: E731

    from .page import UnsuccessfulEndPage

    if fail_on_timeout is True:
        after_timeout_logic = UnsuccessfulEndPage()
    else:
        after_timeout_logic = GoTo(end_while)

    elts = join(
        CodeBlock(
            lambda participant: participant.var.set(
                with_namespace("loop_start_time"), serialise(datetime.now())
            )
        ),
        start_while,
        conditional(
            "max_loop_time_condition",
            lambda participant, experiment: call_function_with_context(
                max_loop_time_condition,
                participant=participant,
                experiment=experiment,
            ),
            after_timeout_logic,
            fix_time_credit=False,
            log_chosen_branch=False,
        ),
        conditional(
            label,
            condition_wrapped,
            conditional_logic,
            fix_time_credit=False,
            log_chosen_branch=False,
        ),
        end_while,
    )

    if fix_time_credit:
        time_estimate = CreditEstimate(logic).get_max("time")
        return fix_time(elts, time_estimate)
    else:
        return elts


def check_branches(branches):
    try:
        assert isinstance(branches, dict)
        for branch_name, branch_elts in branches.items():
            assert isinstance(branch_elts, (Elt, Module)) or is_list_of(
                branch_elts, Elt
            )
            if isinstance(branch_elts, Elt):
                branches[branch_name] = [branch_elts]
            elif isinstance(branch_elts, Module):
                branches[branch_name] = branch_elts.resolve()
        return branches
    except AssertionError:
        raise TypeError(
            "<branches> must be a dict of Modules or (lists of) Elt objects."
        )


def switch(
    label: str,
    function: Callable,
    branches: dict,
    fix_time_credit: bool = True,
    log_chosen_branch: bool = True,
):
    """
    Selects a series of elts to display to the participant according to a
    certain condition.

    Parameters
    ----------

    label:
        Internal label to assign to the construct.

    function:
        A function with up to two arguments named ``participant`` and ``experiment``,
        that is executed once the participant reaches the corresponding part of the timeline,
        returning a key value with which to index ``branches``.

    branches:
        A dictionary indexed by the outputs of ``function``; each value should correspond
        to an elt (or list of elts) that can be selected by ``function``.

    fix_time_credit:
        Whether participants should receive the same time credit irrespective of the branch taken.
        Defaults to ``True``, so that all participants receive the same credit, corresponding to the
        branch with the maximum time credit.

    log_chosen_branch:
        Whether to keep a log of which participants took each branch; defaults to ``True``.

    Returns
    -------

    list
        A list of elts that can be embedded in a timeline using :func:`psynet.timeline.join`.
    """

    check_function_args(function, ("self", "experiment", "participant"), need_all=False)
    branches = check_branches(branches)

    all_branch_starts = dict()
    all_elts = []
    end_switch = EndSwitch(label)

    for branch_name, branch_elts in branches.items():
        branch_start = StartSwitchBranch(branch_name)
        branch_end = EndSwitchBranch(branch_name, end_switch)
        all_branch_starts[branch_name] = branch_start
        all_elts = all_elts + [branch_start] + branch_elts + [branch_end]

    start_switch = StartSwitch(
        label,
        function,
        branch_start_elts=all_branch_starts,
        end_switch=end_switch,
        log_chosen_branch=log_chosen_branch,
    )
    combined_elts = [start_switch] + all_elts + [end_switch]

    if fix_time_credit:
        time_estimate = max(
            [
                CreditEstimate(branch_elts).get_max("time")
                for branch_elts in branches.values()
            ]
        )
        return fix_time(combined_elts, time_estimate)
    else:
        return combined_elts


class StartSwitch(ReactiveGoTo):
    def __init__(
        self, label, function, branch_start_elts, end_switch, log_chosen_branch=True
    ):
        if log_chosen_branch:

            def function_2(experiment, participant):
                val = call_function_with_context(
                    function,
                    experiment=experiment,
                    participant=participant,
                )
                log_entry = [label, val]
                participant.append_branch_log(log_entry)
                return val

            super().__init__(function_2, targets=branch_start_elts)
        else:
            super().__init__(function, targets=branch_start_elts)
        self.label = label
        self.branch_start_elts = branch_start_elts
        self.end_switch = end_switch
        self.log_chosen_branch = log_chosen_branch


class EndSwitch(NullElt):
    def __init__(self, label):
        self.label = label


class StartSwitchBranch(NullElt):
    def __init__(self, name):
        super().__init__()
        self.name = name


class EndSwitchBranch(GoTo):
    def __init__(self, name, final_elt):
        super().__init__(target=final_elt)
        self.name = name


def conditional(
    label: str,
    condition: Callable,
    logic_if_true,
    logic_if_false=None,
    fix_time_credit: bool = True,
    log_chosen_branch: bool = True,
):
    """
    Executes a series of elts if and only if a certain condition is satisfied.

    Parameters
    ----------

    label:
        Internal label to assign to the construct.

    condition:
        A function with up to two arguments named ``participant`` and ``experiment``,
        that is executed once the participant reaches the corresponding part of the timeline,
        returning a Boolean.

    logic_if_true:
        An elt (or list of elts) to display if ``condition`` returns ``True``.

    logic_if_false:
        An optional elt (or list of elts) to display if ``condition`` returns ``False``.

    fix_time_credit:
        Whether participants should receive the same time credit irrespective of whether
        ``condition`` returns ``True`` or not; defaults to ``True``, so that all participants
        receive the same credit.

    log_chosen_branch:
        Whether to keep a log of which participants took each branch; defaults to ``True``.

    Returns
    -------

    list
        A list of elts that can be embedded in a timeline using :func:`psynet.timeline.join`.
    """
    return switch(
        label,
        function=condition,
        branches={
            True: logic_if_true,
            False: NullElt() if logic_if_false is None else logic_if_false,
        },
        fix_time_credit=fix_time_credit,
        log_chosen_branch=log_chosen_branch,
    )


class ConditionalElt(Elt):
    def __init__(self, label: str):
        self.label = label


class StartConditional(ConditionalElt):
    pass


class EndConditional(ConditionalElt):
    pass


def fix_time(elts, time_estimate):
    end_fix_time = EndFixTime(time_estimate)
    start_fix_time = StartFixTime(time_estimate, end_fix_time)
    return join(start_fix_time, elts, end_fix_time)


def multiply_expected_repetitions(logic, factor: float):
    assert isinstance(logic, Elt) or is_list_of(logic, Elt)
    if isinstance(logic, Elt):
        logic.multiply_expected_repetitions(factor)
    else:
        for elt in logic:
            elt.multiply_expected_repetitions(factor)
    return logic


@register_table
class ModuleState(SQLBase, SQLMixin):
    __tablename__ = "module_state"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, unique=True)
    module_id = Column(String)
    # parent_id = Column(Integer, ForeignKey("module_state.id"))
    # parent = relationship("ModuleState", foreign_keys=[parent_id], post_update=True)
    participant_id = Column(
        Integer,
        ForeignKey("participant.id"),
        # back_populates="_module_states",
    )
    participant = relationship(
        "psynet.participant.Participant",
        foreign_keys=[participant_id],
        backref="_module_states",
    )
    # current_trial = Column(
    #     PythonObject
    # )  # Note: this can sometimes be a trial object or alternatively a string

    @property
    def var(self):
        return VarStore(self)

    time_started = Column(DateTime)
    time_finished = Column(DateTime)
    time_aborted = Column(DateTime)
    started = Column(Boolean, default=False)
    finished = Column(Boolean, default=False)
    aborted = Column(Boolean, default=False)

    assets = relationship(
        # We see assets that belong to that module,
        # and either belong to that participant, or belong to no other participants
        "psynet.asset.Asset",
        primaryjoin=(
            "and_(foreign(ModuleState.module_id)==remote(psynet.asset.Asset.module_id), "
            "or_(ModuleState.participant_id==psynet.asset.Asset.participant_id, "
            "psynet.asset.Asset.participant_id.is_(None)))"
        ),
        uselist=True,
        collection_class=attribute_mapped_collection("local_key"),
    )

    nodes = relationship(
        # We see nodes that belong to that module,
        # and either belong to that participant, or belong to no other participants
        "psynet.trial.main.TrialNode",
        primaryjoin=(
            "and_(foreign(ModuleState.module_id)==remote(psynet.trial.main.TrialNode.module_id), "
            "or_(ModuleState.participant_id==psynet.trial.main.TrialNode.participant_id, "
            "psynet.trial.main.TrialNode.participant_id.is_(None)))"
        ),
        uselist=True,
    )

    def __init__(self, module, participant):
        self.module_id = module.id
        self.participant = participant

    def start(self):
        self.time_started = datetime.now()
        self.started = True

    def finish(self):
        self.time_finished = datetime.now()
        self.finished = True

    def abort(self):
        self.time_finished = datetime.now()
        self.aborted = True

    # def get(self, module_id: str):
    #     return self.participant.get_module_state(module_id)


class ModuleAssets:
    def __init__(self, module_id):
        self.module_id = module_id

    def __getitem__(self, item):
        from psynet.asset import Asset

        return Asset.query.filter_by(module_id=self.module_id, local_key=item).one()


class Module:
    default_id = None
    default_elts = None
    state_class = ModuleState  # type: Type[ModuleState]

    def __init__(
        self, id_: str = None, *args, assets=None, nodes=None, state_class=None
    ):
        elts = join(*args)

        if self.default_id is None and id_ is None:
            raise ValueError("Either one of <default_id> or <id_> must not be None.")
        if self.default_elts is None and elts is None:
            raise ValueError("Either one of <default_elts> or <elts> must not be None.")

        self.id = id_ if id_ is not None else self.default_id
        self.elts = elts if elts is not None else self.default_elts
        self.nodes = nodes if nodes else []

        if assets is None:
            self._staged_assets = []
        elif isinstance(assets, dict):
            self._staged_assets = []
            for _local_key, _asset in assets.items():
                _asset.local_key = _local_key
                self._staged_assets.append(_asset)
        else:
            assert isinstance(assets, list)
            self._staged_assets = assets

        self.state_class = state_class if state_class else self.__class__.state_class

        from psynet.asset import Asset

        for elt in self.elts:
            if isinstance(elt, Asset):
                self._staged_assets.append(elt)

        for asset in self._staged_assets:
            asset.module_id = self.id

    @property
    def assets(self):
        return ModuleAssets(self.id)

    def prepare_for_deployment(self, experiment):
        self.prepare_nodes_for_deployment(experiment)
        self.prepare_assets_for_deployment(experiment)

    def prepare_nodes_for_deployment(self, experiment):
        self.nodes_register_in_db()
        self.nodes_stage_assets(experiment)

    def prepare_assets_for_deployment(self, experiment):
        for asset in self._staged_assets:
            experiment.assets.stage(asset)
        db.session.commit()

    def deposit_assets_on_the_fly(self):
        assets_to_deposit = [
            asset for asset in self._staged_assets if not asset.deposited
        ]
        if len(assets_to_deposit) > 0:
            logger.info(
                "Depositing %i assets on-the-fly (i.e. while the participant waits for the "
                "experiment to continue. This is a bad idea if the number of assets is large "
                "and if they need to be uploaded to a remote server. "
                "To avoid this, avoid defining your module/trial maker within a page maker.",
                len(assets_to_deposit),
            )
            for asset in assets_to_deposit:
                # TODO - parallelize this deposit, see code in Experiment class
                asset.deposit()
            db.session.commit()

    def nodes_register_in_db(self):
        for node in self.nodes:
            db.session.add(node)
            node.module_id = self.id
            if node.network is None:
                node.add_default_network()
        db.session.commit()
        for node in self.nodes:
            node.check_on_create()
            node.check_on_deploy()
        db.session.commit()

    def nodes_stage_assets(self, experiment):
        for node in self.nodes:
            node.stage_assets(experiment)
        db.session.commit()

    def start(self, participant):
        state = self.state_class(self, participant)
        state.start()
        participant.module_state = state
        db.session.add(state)
        db.session.commit()

    def end(self, participant):
        # This should only fail (delivering multiple logs) if the experimenter has perversely
        # defined a recursive module (or is reusing module ID)
        state = self.state_class.query.filter_by(
            module_id=self.id, participant_id=participant.id, finished=False
        ).one()
        state.finish()
        db.session.commit()
        participant.refresh_module_state()
        db.session.commit()

    @classmethod
    def started_and_finished_times(cls, participants, module_id):
        logs = cls.state_class.query.filter_by(module_id=module_id, finished=True).all()
        return [
            {"time_started": log.time_started, "time_finished": log.time_finished}
            # "time_aborted": log.time_aborted,
            for log in logs
        ]

    @classmethod
    def median_finish_time_in_min(cls, participants, module_id):
        started_and_finished_times = cls.started_and_finished_times(
            participants, module_id
        )

        if not started_and_finished_times:
            return None

        durations_in_min = []
        for start_end_times in started_and_finished_times:
            if not (
                start_end_times["time_started"] and start_end_times["time_finished"]
            ):
                continue
            datetime_format = "%Y-%m-%dT%H:%M:%S.%f"
            t1 = datetime.strptime(start_end_times["time_started"], datetime_format)
            t2 = datetime.strptime(start_end_times["time_finished"], datetime_format)
            durations_in_min.append((t2 - t1).total_seconds() / 60)

        if not durations_in_min:
            return None

        return median(sorted(durations_in_min))

    @property
    def aborted_participants(self):
        from .participant import Participant

        return (
            db.session.query(Participant)
            .filter(self.state_class.module_id == self.id, self.state_class.aborted)
            .order_by(self.state_class.time_aborted)
            .all()
        )

        # participants = Participant.query.all()
        # aborted_participants = [p for p in participants if self.id in p.aborted_modules]
        # aborted_participants.sort(key=lambda p: p.modules[self.id]["time_aborted"][0])
        # return aborted_participants

    @property
    def started_participants(self):
        from .participant import Participant

        return (
            db.session.query(Participant)
            .filter(self.state_class.module_id == self.id, self.state_class.started)
            .order_by(self.state_class.time_started)
            .all()
        )

        # participants = Participant.query.all()
        # started_participants = [p for p in participants if self.id in p.started_modules]
        # started_participants.sort(key=lambda p: p.modules[self.id]["time_started"][0])
        # return started_participants

    @property
    def finished_participants(self):
        from .participant import Participant

        return (
            db.session.query(Participant)
            .filter(self.state_class.module_id == self.id, self.state_class.finished)
            .order_by(self.state_class.time_finished)
            .all()
        )

        # participants = Participant.query.all()
        # finished_participants = [
        #     p for p in participants if self.id in p.finished_modules
        # ]
        # finished_participants.sort(key=lambda p: p.modules[self.id]["time_finished"][0])
        # return finished_participants

    def resolve(self):
        return join(
            StartModule(self.id, module=self),
            self.elts,
            EndModule(self.id, module=self),
        )

    def visualize(self):
        if self.started_participants:
            time_started_last = self.started_participants[-1].modules[self.id][
                "time_started"
            ][0]
        if self.finished_participants:
            time_finished_last = self.finished_participants[-1].modules[self.id][
                "time_finished"
            ][0]
            median_finish_time_in_min = round(
                Module.median_finish_time_in_min(self.finished_participants, self.id), 1
            )
        if self.aborted_participants:
            time_aborted_last = self.aborted_participants[-1].modules[self.id][
                "time_aborted"
            ][0]

        div = tags.div()
        with div:
            with tags.h4("Module"):
                tags.i(self.id)
            with tags.ul(cls="details"):
                tags.li(f"Participants started: {len(self.started_participants)}")
                tags.li(f"Participants finished: {len(self.finished_participants)}")
                tags.li(f"Participants aborted: {len(self.aborted_participants)}")
                if self.started_participants:
                    tags.br()
                    tags.li(
                        f"Participant started last: {format_datetime_string(time_started_last)}"
                    )
                if self.finished_participants:
                    tags.li(
                        f"Participant finished last: {format_datetime_string(time_finished_last)}"
                    )
                if self.aborted_participants:
                    tags.li(
                        f"Participant aborted last: {format_datetime_string(time_aborted_last)}"
                    )

                if self.finished_participants:
                    tags.br()
                    tags.li(
                        f"Median time spent (finished): {median_finish_time_in_min} min."
                    )

        return div.render()

    def visualize_tooltip(self):
        if self.finished_participants:
            median_finish_time_in_min = Module.median_finish_time_in_min(
                self.finished_participants, self.id
            )

        span = tags.span()
        with span:
            tags.b(self.id)
            tags.br()
            tags.span(
                f"{len(self.started_participants)} started, {len(self.finished_participants)} finished,"
            )
            tags.br()
            tags.span(f"{len(self.aborted_participants)} aborted")
            if self.finished_participants:
                tags.br()
                tags.span(f"{round(median_finish_time_in_min, 1)} min. (median)")

        return span.render()

    def get_progress_info(self):
        target_n_participants = (
            self.target_n_participants
            if hasattr(self, "target_n_participants")
            else None
        )
        # TODO a more sophisticated calculation of progress
        progress = (
            len(self.finished_participants) / target_n_participants
            if target_n_participants is not None and target_n_participants > 0
            else 1
        )

        return {
            self.id: {
                "started_n_participants": len(self.started_participants),
                "finished_n_participants": len(self.finished_participants),
                "aborted_n_participants": len(self.aborted_participants),
                "target_n_participants": target_n_participants,
                "progress": progress,
            }
        }


class StartModule(NullElt):
    def __init__(self, label, module):
        super().__init__()
        self.label = label
        self.module = module

    def consume(self, experiment, participant):
        self.module.start(participant)

        if self.created_within_page_maker:
            self.module.deposit_assets_on_the_fly()


class EndModule(NullElt):
    def __init__(self, label, module):
        super().__init__()
        self.label = label
        self.module = module

    def consume(self, experiment, participant):
        self.module.end(participant)


class StartAccumulateAnswers(NullElt):
    def consume(self, experiment, participant):
        participant.answer_accumulators = participant.answer_accumulators + [{}]


class EndAccumulateAnswers(NullElt):
    def consume(self, experiment, participant):
        participant.answer = participant.answer_accumulators[-1]
        participant.answer_accumulators = participant.answer_accumulators[:-1]


class DatabaseCheck(NullElt):
    def __init__(self, label, function):
        check_function_args(function, args=[])
        self.label = label
        self.function = function

    def run(self):
        start_time = time.monotonic()
        logger.info("Executing the database check '%s'...", self.label)
        try:
            self.function()
            end_time = time.monotonic()
            time_taken = end_time - start_time
            logger.info(
                "The database check '%s' completed in %s seconds.",
                self.label,
                f"{time_taken:.3f}",
            )
        except Exception:
            logger.info(
                "An exception was thrown in the database check '%s'.",
                self.label,
                exc_info=True,
            )


class PreDeployRoutine(NullElt):
    """
    A timeline component that allows for the definition of tasks to be performed
    before deployment. It is possible to make database changes as part of these
    routines and these will be propagated to the deployed experiment.

    Parameters
    ----------

    label
        A label describing the pre-deployment task.

    function
        The name of a function to be executed.

    args
        The arguments for the function to be executed.
    """

    def __init__(self, label, function, args=None):
        if args is None:
            args = {}
        provided_args = list(args.keys())
        provided_args.append("experiment")
        check_function_args(function, args=provided_args, need_all=False)
        self.label = label
        self.function = function
        self.args = args


class ParticipantFailRoutine(NullElt):
    def __init__(self, label, function):
        check_function_args(
            function, args=["participant", "experiment"], need_all=False
        )
        self.label = label
        self.function = function


class RecruitmentCriterion(NullElt):
    def __init__(self, label, function):
        check_function_args(function, args=["experiment"], need_all=False)
        self.label = label
        self.function = function


def get_trial_maker(trial_maker_id):
    raise ImportError(
        "get_trial_maker has moved from psynet.timeline to psynet.experiment, please update your import statements."
    )


FOR_LOOP_STACK_DEPTH = -1


def for_loop(
    *,
    label,
    iterate_over,
    logic,
    time_estimate_per_iteration,
    expected_repetitions=None,
):
    assert callable(iterate_over)
    assert callable(logic)

    def estimate_num_repetitions(iterate_over):
        if len(get_args(iterate_over)) > 0:
            raise ValueError(
                "If iterate_over takes arguments then expected_repetitions cannot be inferred automatically "
                "and must be provided explicitly."
            )
        return len(iterate_over())

    def setup(experiment, participant):
        # import pydevd_pycharm
        # pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)
        nonlocal iterate_over
        nonlocal label
        if callable(iterate_over):
            lst = call_function_with_context(
                iterate_over,
                experiment=experiment,
                participant=participant,
            )
        state = {"lst": lst, "index": 0}
        # participant.for_loops.append(state)
        if label in participant.for_loops:
            raise ValueError(
                f"Duplicated for_loop label detected: {label}. "
                "This suggests that you have tried to nest two for loops with the same label, "
                "which is not permitted. Please disambiguate the labels."
            )
        participant.for_loops[label] = state
        flag_modified(participant, "for_loops")

    def wrapup(experiment, participant):
        nonlocal label
        del participant.for_loops[label]
        flag_modified(participant, "for_loops")

    def content(experiment, participant):
        # global FOR_LOOP_STACK_DEPTH
        # FOR_LOOP_STACK_DEPTH += 1
        # state = participant.for_loops[FOR_LOOP_STACK_DEPTH]
        nonlocal label
        state = participant.for_loops[label]
        lst = state["lst"]
        index = state["index"]
        input = lst[index]
        # import pydevd_pycharm
        # pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)
        return call_function_with_context(
            logic,
            input,
            experiment=experiment,
            participant=participant,
        )

    def should_stay_in_loop(participant):
        nonlocal label
        # state = participant.for_loops[-1]
        # import pydevd_pycharm
        # pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)
        state = participant.for_loops[label]
        return state["index"] < len(state["lst"])

    def increment_counter(participant):
        # state = participant.for_loops[-1]
        nonlocal label
        state = participant.for_loops[label]
        state["index"] += 1
        flag_modified(participant, "for_loops")

    return join(
        CodeBlock(setup),
        while_loop(
            "for_loop",
            should_stay_in_loop,
            join(
                PageMaker(content, time_estimate_per_iteration),
                CodeBlock(increment_counter),
            ),
            expected_repetitions=expected_repetitions
            if expected_repetitions
            else estimate_num_repetitions(iterate_over),
            fix_time_credit=False,
        ),
        CodeBlock(wrapup),
    )


def randomize(*, label, logic):
    assert isinstance(logic, list)
    n = len(logic)
    total_time = sum(elt.time_estimate for elt in logic)
    return for_loop(
        label=label,
        iterate_over=lambda: random.sample(range(n), n),
        logic=lambda i: logic[i],
        time_estimate_per_iteration=total_time / n,
    )


class RegisterTrialMaker(NullElt):
    def __init__(self, trial_maker):
        self.trial_maker_id = trial_maker.id
        self.trial_maker = trial_maker
