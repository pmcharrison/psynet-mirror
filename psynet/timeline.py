# pylint: disable=abstract-method

import json
import time
from collections import Counter
from datetime import datetime
from functools import reduce
from statistics import median
from typing import Callable, Dict, List, Optional, Union

import flask
import importlib_resources
from dallinger import db
from dallinger.config import get_config
from dominate import tags
from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from . import templates
from .data import SQLBase, SQLMixin
from .field import claim_field
from .participant import Participant
from .utils import (
    call_function,
    check_function_args,
    dict_to_js_vars,
    format_datetime_string,
    get_logger,
    merge_dicts,
    serialise,
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
        call_function(
            self.function,
            {"self": self, "experiment": experiment, "participant": participant},
        )


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
        # We subtract 1 because elt_id will be incremented again when
        # we return to the start of the advance page loop.
        target_elt = self.get_target(experiment, participant)
        target_elt_id = target_elt.id
        participant.elt_id = target_elt_id - 1


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
        val = call_function(
            self.function,
            {"self": self, "experiment": experiment, "participant": participant},
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
        if audio is None:
            audio = {}

        if image is None:
            image = {}

        if video is None:
            video = {}

        self.data = {"audio": audio, "image": image, "video": video}

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

    def process_response(
        self, raw_answer, blobs, metadata, experiment, participant, client_ip_address
    ):
        answer = self.format_answer(
            raw_answer,
            blobs=blobs,
            metadata=metadata,
            experiment=experiment,
            participant=participant,
        )
        extra_metadata = self.metadata(
            metadata=metadata,
            raw_answer=raw_answer,
            answer=answer,
            experiment=experiment,
            participant=participant,
        )
        combined_metadata = {**metadata, **extra_metadata}
        resp = Response(
            participant=participant,
            label=self.label,
            answer=answer,
            page_type=type(self).__name__,
            metadata=combined_metadata,
            client_ip_address=client_ip_address,
        )

        db.session.add(resp)
        db.session.commit()

        if self.save_answer:
            participant.answer = resp.answer
            participant.last_response_id = resp.id
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
        all_template_arg = {
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
        }
        return flask.render_template_string(self.template_str, **all_template_arg)

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
        The function should return an instance of (or a subclass of)
        :class:`psynet.timeline.Page`.

    time_estimate:
        Time estimated to complete the page.
    """

    returns_time_credit = True

    def __init__(self, function, time_estimate: float):
        self.function = function
        self.time_estimate = time_estimate
        self.expected_repetitions = 1

    def consume(self, experiment, participant):
        participant.page_uuid = experiment.make_uuid()

    def resolve(self, experiment, participant):
        page = call_function(
            self.function,
            {"self": self, "experiment": experiment, "participant": participant},
        )
        if not isinstance(page, Page):
            raise TypeError(
                "The PageMaker function must return an object of class Page."
            )
        if page.time_estimate is None:
            page.time_estimate = self.time_estimate
        if page.time_estimate != self.time_estimate:
            logger.info(
                f"Warning: Generated page had a different time estimate ({page.time_estimate}) "
                + f"to that specified by the page maker ({self.time_estimate})."
            )
        return page

    def multiply_expected_repetitions(self, factor: float):
        self.expected_repetitions = self.expected_repetitions * factor
        return self


def multi_page_maker(
    label: str,
    function,
    expected_num_pages: int,
    total_time_estimate: int,
    accumulate_answers: bool = False,
    check_num_pages: bool = True,
):
    """
    Generalises the notion of PageMaker to multiple pages at a time.

    Parameters
    ----------

    label
        Label for the multi-page-maker.

    function
        Function to generate the pages, taking the arguments ``experiment`` and ``participant``.

    expected_num_pages
        Expected number of pages to be returned in the output of ``function``.

    total_time_estimate
        Overall time estimate for the sequence of pages.

    accumulate_answers
        If ``False`` (default), then the final ``answer`` is simply the answer delivered by the final
        page. If ``True``, then the answers to all the pages are accumulated in a list.

    check_num_pages
        If ``True`` (default), then ``expected_num_pages`` will be checked against the actual number
        of pages generated by ``function``. If there is a discrepancy, a warning message will be logged.

    Returns
    -------

    A list of test elements that can be incorporated into a timeline using ``join``.

    """

    def with_namespace(x=None):
        prefix = f"__multi_page_maker__{label}"
        if x is None:
            return prefix
        return f"{prefix}__{x}"

    def get_page_list(experiment, participant):
        res = call_function(
            function, {"experiment": experiment, "participant": participant}
        )
        if isinstance(res, Elt):
            return [res]
        return res

    def check_pages(pages):
        if check_num_pages and len(pages) != expected_num_pages:
            logger.info(
                f"The multi-page maker '{label}' returned a list of {len(pages)} pages, "
                + f"which differs from the expected number {expected_num_pages}. "
                + f"If this multi-page maker was created directly, consider setting expected_num_pages to {len(pages)}. "
                + "If this message is occurring in the context of a multi-page trial, consider setting "
                + f"the num_pages class attribute of the `Trial` class to {len(pages)}. "
                + "To suppress this message, pass `check_num_pages=False` to `multi_page_maker` "
                + "if creating the multi-page maker directly, or set `check_num_pages = False` "
                + "as a class attribute for the `Trial` class."
            )

    def new_function(experiment, participant):
        pos = participant.var.get(with_namespace("pos"))
        pages = get_page_list(experiment, participant)
        check_pages(pages)
        page = pages[pos]
        if not isinstance(page, Page):
            raise RuntimeError(
                "The function in multi_page_maker must return a list of Page objects."
            )
        return page

    def prepare_participant(participant):
        (
            participant.var.set(with_namespace("complete"), False)
            .set(with_namespace("pos"), 0)
            .set(with_namespace("seq_length"), expected_num_pages)
            .set(with_namespace("answer"), [])
        )
        if accumulate_answers:
            participant.var.set(with_namespace("accumulated_answers"), [])

    prepare_logic = CodeBlock(prepare_participant)

    def get_actual_num_pages(experiment, participant):
        return len(get_page_list(experiment, participant))

    def get_updated_answer(participant):
        if participant.answer_is_fresh:
            if accumulate_answers:
                return participant.var.get(with_namespace("answer")) + [
                    participant.answer
                ]
            else:
                return participant.answer
        else:
            return participant.var.get(with_namespace("answer"))

    def update(participant, experiment):
        if accumulate_answers:
            if participant.answer_is_fresh:
                prev_answers = participant.var.get(
                    with_namespace("accumulated_answers")
                )
                participant.var.set(
                    with_namespace("accumulated_answers"),
                    prev_answers + [participant.answer],
                )

        participant.var.set(
            with_namespace("complete"),
            participant.var.get(with_namespace("pos"))
            >= get_actual_num_pages(experiment, participant) - 1,
        )
        participant.var.inc(with_namespace("pos"))

    update_logic = CodeBlock(update)

    show_event = PageMaker(
        new_function, time_estimate=total_time_estimate / expected_num_pages
    )

    def condition(participant):
        return not participant.var.get(with_namespace("complete"))

    def wrapup(participant):
        if accumulate_answers:
            participant.answer = participant.var.get(
                with_namespace("accumulated_answers")
            )

    wrapup_logic = CodeBlock(wrapup)

    return join(
        prepare_logic,
        while_loop(
            label=with_namespace(label),
            condition=condition,
            logic=[show_event, update_logic],
            expected_repetitions=expected_num_pages,
            fix_time_credit=False,
        ),
        wrapup_logic,
    )


class EndPage(PageMaker):
    def __init__(self, template_filename):
        def f(participant):
            return Page(
                time_estimate=0,
                template_str=get_template(template_filename),
                template_arg={"participant": participant},
            )

        super().__init__(
            f, time_estimate=0
        )  # Temporary hotfix for time/bonus estimation bug introduced in d64c1ee505f6

    def consume(self, experiment, participant):
        super().consume(experiment, participant)
        self.finalize_participant(experiment, participant)

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
        self.check_elts()
        self.add_elt_ids()
        self.estimated_time_credit = CreditEstimate(self.elts)

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

    def modules(self):
        return {
            "modules": [
                {"id": elt.module.id}
                for elt in self.elts
                if isinstance(elt, StartModule)
            ]
        }

    def get_trial_maker(self, trial_maker_id):
        elts = self.elts
        try:
            start = [
                e
                for e in elts
                if isinstance(e, StartModule) and e.label == trial_maker_id
            ][0]
        except IndexError:
            raise RuntimeError(f"Couldn't find trial maker with id = {trial_maker_id}.")
        trial_maker = start.module
        return trial_maker

    def add_elt_ids(self):
        for i, elt in enumerate(self.elts):
            elt.id = i
        for i, elt in enumerate(self.elts):
            if elt.id != i:
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

    def get_current_elt(self, experiment, participant, resolve=True):
        n = participant.elt_id
        N = len(self)
        if n >= N:
            raise ValueError(
                f"Tried to get element {n + 1} of a timeline with only {N} element(s)."
            )
        else:
            res = self[n]
            if isinstance(res, PageMaker) and resolve:
                return res.resolve(experiment, participant)
            else:
                return res

    def advance_page(self, experiment, participant):
        finished = False
        while not finished:
            participant.elt_id += 1

            new_elt = self.get_current_elt(experiment, participant, resolve=False)
            new_elt.consume(experiment, participant)

            if isinstance(new_elt, Page) or isinstance(new_elt, PageMaker):
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

    participant = relationship(Participant, backref="all_responses")
    participant_id = Column(Integer, ForeignKey("participant.id"))

    question = claim_field("question", __extra_vars__, str)
    answer = claim_field("answer", __extra_vars__)
    page_type = claim_field("page_type", __extra_vars__, str)
    successful_validation = claim_field("successful_validation", __extra_vars__, bool)
    client_ip_address = claim_field("client_ip_address", __extra_vars__, str)

    # metadata is a protected attribute in SQLAlchemy, hence the underscore
    # and the functional setter/getter.
    metadata_ = claim_field("metadata", __extra_vars__)

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

    def __init__(
        self, participant, label, answer, page_type, metadata, client_ip_address
    ):
        self.participant_id = participant.id
        self.question = label
        self.answer = answer
        self.metadata = metadata
        self.page_type = page_type
        self.metadata = metadata
        self.client_ip_address = client_ip_address


def is_list_of(x: list, what):
    for val in x:
        if not isinstance(val, what):
            return False
    return True


def join(*args):
    for i, arg in enumerate(args):
        if not (
            (arg is None)
            or (isinstance(arg, (Elt, Module)) or is_list_of(arg, (Elt, Module)))
        ):
            raise TypeError(
                f"Element {i + 1} of the input to join() was neither an Elt nor a list of Elts nor a Module ({arg})."
            )

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
                return Exception("An unexpected error occurred.")

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
            lambda participant, experiment: call_function(
                max_loop_time_condition,
                {"participant": participant, "experiment": experiment},
            ),
            after_timeout_logic,
            fix_time_credit=False,
            log_chosen_branch=False,
        ),
        conditional(
            label,
            condition,
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
                val = call_function(
                    function,
                    {"experiment": experiment, "participant": participant},
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


class Module:
    default_id = None
    default_elts = None

    def __init__(self, id_: str = None, *args):
        elts = join(*args)

        if self.default_id is None and id_ is None:
            raise ValueError("Either one of <default_id> or <id_> must not be None.")
        if self.default_elts is None and elts is None:
            raise ValueError("Either one of <default_elts> or <elts> must not be None.")

        self.id = id_ if id_ is not None else self.default_id
        self.elts = elts if elts is not None else self.default_elts

    @classmethod
    def started_and_finished_times(cls, participants, module_id):
        return [
            {
                "time_started": participant.modules[module_id]["time_started"][0],
                "time_finished": participant.modules[module_id]["time_finished"][0],
                "time_aborted": participant.modules[module_id]["time_finished"][0],
            }
            for participant in participants
            if module_id in participant.finished_modules
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

        participants = Participant.query.all()
        aborted_participants = [p for p in participants if self.id in p.aborted_modules]
        aborted_participants.sort(key=lambda p: p.modules[self.id]["time_aborted"][0])
        return aborted_participants

    @property
    def started_participants(self):
        from .participant import Participant

        participants = Participant.query.all()
        started_participants = [p for p in participants if self.id in p.started_modules]
        started_participants.sort(key=lambda p: p.modules[self.id]["time_started"][0])
        return started_participants

    @property
    def finished_participants(self):
        from .participant import Participant

        participants = Participant.query.all()
        finished_participants = [
            p for p in participants if self.id in p.finished_modules
        ]
        finished_participants.sort(key=lambda p: p.modules[self.id]["time_finished"][0])
        return finished_participants

    def resolve(self):
        return join(StartModule(self.id, module=self), self.elts, EndModule(self.id))

    def visualize(self):
        phase = self.phase if hasattr(self, "phase") else None

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
                if phase is not None:
                    tags.li(f"Phase: {phase}")
                    tags.br()
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
        target_num_participants = (
            self.target_num_participants
            if hasattr(self, "target_num_participants")
            else None
        )
        # TODO a more sophisticated calculation of progress
        progress = (
            len(self.finished_participants) / target_num_participants
            if target_num_participants is not None and target_num_participants > 0
            else 1
        )

        return {
            self.id: {
                "started_num_participants": len(self.started_participants),
                "finished_num_participants": len(self.finished_participants),
                "aborted_num_participants": len(self.aborted_participants),
                "target_num_participants": target_num_participants,
                "progress": progress,
            }
        }


class StartModule(NullElt):
    def __init__(self, label, module):
        super().__init__()
        self.label = label
        self.module = module

    def consume(self, experiment, participant):
        participant.start_module(self.label)


class EndModule(NullElt):
    def __init__(self, label):
        super().__init__()
        self.label = label

    def consume(self, experiment, participant):
        participant.end_module(self.label)


class ExperimentSetupRoutine(NullElt):
    def __init__(self, function):
        self.check_function(function)
        self.function = function

    def check_function(self, function):
        if not self._is_function(function) and check_function_args(
            function, ["experiment"]
        ):
            raise TypeError(
                "<function> must be a function or method of the form f(experiment)."
            )

    @staticmethod
    def _is_function(x):
        return callable(x)


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
    before deployment. :class:`PreDeployRoutine`s are thought to be added to the
    beginning of a timeline of an experiment.

    Parameters
    ----------

    label
        A label describing the pre-deployment task.

    function
        The name of a function to be executed.

    args
        The arguments for the function to be executed.
    """

    def __init__(self, label, function, args):
        check_function_args(function, args=args.keys(), need_all=False)
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
