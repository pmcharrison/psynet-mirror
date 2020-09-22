# pylint: disable=abstract-method

from datetime import datetime
import importlib_resources
import flask
import gevent
import time
import json
from statistics import median

from dominate import tags
from sqlalchemy.ext.hybrid import hybrid_property

from typing import List, Optional, Dict, Callable
from collections import Counter

from .utils import (
    call_function,
    check_function_args,
    dict_to_js_vars,
    format_datetime_string,
    get_logger,
    merge_dicts
)
from . import templates

from dallinger import db
from dallinger.models import Question
from dallinger.config import get_config

from functools import reduce

logger = get_logger()

from .field import claim_field

# pylint: disable=unused-import
import rpdb

def get_template(name):
    assert isinstance(name, str)
    return importlib_resources.read_text(templates, name)

class Event:
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

    # def get_position_in_timeline(self, timeline):
    #     for i, event in enumerate(timeline):
    #         if self == event:
    #             return i
    #     raise ValueError("Event not found in timeline.")

class NullEvent(Event):
    def consume(self, experiment, participant):
        pass

class CodeBlock(Event):
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
        call_function(self.function, {
            "self": self,
            "experiment": experiment,
            "participant": participant
        })

class FixTime(Event):
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

class GoTo(Event):
    def __init__(self, target):
        self.target = target

    def get_target(self, experiment, participant):
        # pylint: disable=unused-argument
        return self.target

    def consume(self, experiment, participant):
        # We subtract 1 because event_id will be incremented again when
        # we return to the start of the advance page loop.
        target_event = self.get_target(experiment, participant)
        target_event_id = target_event.id
        participant.event_id = target_event_id - 1

class ReactiveGoTo(GoTo):
    def __init__(
        self,
        function, # function taking experiment, participant and returning a key
        targets # dict of possible target elements
    ):
        # pylint: disable=super-init-not-called
        self.function = function
        self.targets = targets
        self.check_args()

    def check_args(self):
        self.check_function()
        self.check_targets()

    def check_function(self):
        check_function_args(self.function, ("self", "experiment", "participant"), need_all=False)

    def check_targets(self):
        try:
            assert isinstance(self.targets, dict)
            for target in self.targets.values():
                assert isinstance(target, Event)
        except:
            raise TypeError("<targets> must be a dictionary of Event objects.")

    def get_target(self, experiment, participant):
        val = call_function(
            self.function,
            {
                "self": self,
                "experiment": experiment,
                "participant": participant
            }
        )
        try:
            return self.targets[val]
        except KeyError:
            raise ValueError(
                f"ReactiveGoTo returned {val}, which is not present among the target keys: " +
                f"{list(self.targets)}."
        )

class MediaSpec():
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

    video: dict
        An analogously structured dictionary of video stimuli.
    """
    modalities = ["audio", "video"]

    def __init__(
            self,
            audio: Optional[dict] = None,
            video: Optional[dict] = None
            ):
        if audio is None:
            audio = {}

        if video is None:
            video = {}

        self.data = {
            "audio": audio,
            "video": video
        }

        assert list(self.data) == self.modalities

    @property
    def audio(self):
        return self.data["audio"]

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
            new_args[modality] = merge_dicts(*[x.data[modality] for x in args], overwrite=overwrite)

        return MediaSpec(**new_args)

    def check(self):
        assert isinstance(self.data, dict)
        for key, value in self.data.items():
            assert key in self.modalities
            ids = set()
            for file_id, file in value.items():
                if file_id in ids:
                    raise ValueError(f"{file_id} occurred more than once in page's {key} specification.")
                ids.add(file_id)
                if not isinstance(file, str):
                    if not isinstance(file, dict):
                        raise TypeError(f"Media entry must either be a string URL or a dict (got {file}).")
                    if not ("url" in file and "ids" in file):
                        raise ValueError("Batch specifications must contain both 'url' and 'ids' keys.")
                    ids = file["ids"]
                    if not isinstance(ids, list):
                        raise TypeError(f"The ids component of the batch specification must be a list (got {ids}).")
                    for _id in ids:
                        if not isinstance(_id, str):
                            raise TypeError(f"Each id in the batch specification must be a string (got {_id}).")

    def to_json(self):
        return json.dumps(self.data)

class Page(Event):
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

    """

    returns_time_credit = True

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
        css: Optional[List] = None
    ):
        if template_arg is None:
            template_arg = {}
        if js_vars is None:
            js_vars = {}

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

    def process_response(self, raw_answer, blobs, metadata, experiment, participant):
        answer = self.format_answer(
            raw_answer,
            blobs=blobs,
            metadata=metadata,
            experiment=experiment,
            participant=participant
        )
        extra_metadata = self.metadata(
            metadata=metadata,
            raw_answer=raw_answer,
            answer=answer,
            experiment=experiment,
            participant=participant
        )
        combined_metadata = {**metadata, **extra_metadata}
        resp = Response(
            participant=participant,
            label=self.label,
            answer=answer,
            page_type=type(self).__name__,
            metadata=combined_metadata
        )
        db.session.add(resp)
        db.session.commit()

        participant.answer = resp.answer
        participant.last_response_id = resp.id

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

    def render(self, experiment, participant):
        internal_js_vars = {
            "page_uuid": participant.page_uuid
        }
        all_template_arg = {
            **self.template_arg,
            "init_js_vars": flask.Markup(dict_to_js_vars({**self.js_vars, **internal_js_vars})),
            "define_media_requests": flask.Markup(self.define_media_requests),
            "initial_download_progress": self.initial_download_progress,
            "experiment_progress_bar": self.create_experiment_progress_bar(participant),
            "footer": self.create_footer(experiment, participant),
            "contact_email_on_error": get_config().get("contact_email_on_error"),
            "app_id": experiment.app_id,
            "participant_id": participant.id,
            "worker_id": participant.worker_id,
            "scripts": self.scripts,
            "css": self.css
        }
        return flask.render_template_string(self.template_str, **all_template_arg)

    @property
    def define_media_requests(self):
        return f"psynet.media.requests = JSON.parse('{self.media.to_json()}');"

    def create_experiment_progress_bar(self, participant):
        return ExperimentProgressBar(participant.progress)

    def create_footer(self, experiment, participant):
        # pylint: disable=unused-argument
        return Footer([
                f"Estimated bonus: <strong>&#36;{participant.time_credit.estimate_bonus():.2f}</strong>"
            ],
            escape=False)

    def multiply_expected_repetitions(self, factor: float):
        self.expected_repetitions = self.expected_repetitions * factor
        return self

class PageMaker(Event):
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
        # self.pos_in_reactive_seq = None

    def consume(self, experiment, participant):
        participant.page_uuid = experiment.make_uuid()

    def resolve(self, experiment, participant):
        page = call_function(
            self.function,
            {
                "self": self,
                "experiment": experiment,
                "participant": participant
            }
        )
        # page = self.function(experiment=experiment, participant=participant)
        if self.time_estimate != page.time_estimate and page.time_estimate is not None:
            logger.warning(
                f"Observed a mismatch between a page maker's time_estimate slot ({self.time_estimate}) " +
                f"and the time_estimate slot of the generated page ({page.time_estimate}). " +
                f"The former will take precedent."
            )
        if not isinstance(page, Page):
            raise TypeError("The PageMaker function must return an object of class Page.")
        return page

    def multiply_expected_repetitions(self, factor: float):
        self.expected_repetitions = self.expected_repetitions * factor
        return self

    # def set_pos_in_reactive_seq(self, val):
    #     assert isinstance(val, int)
    #     self.pos_in_reactive_seq = val
    #     return self


def reactive_seq(
    label,
    function,
    num_pages: int,
    time_estimate: int
):
    """Function must return a list of pages when evaluated."""
    def with_namespace(x=None):
        prefix = f"__reactive_seq__{label}"
        if x is None:
            return prefix
        return f"{prefix}__{x}"

    def new_function(self, experiment, participant):
        pos = participant.var.get(with_namespace("pos"))
        events = call_function(
            function,
            {
                "self": self,
                "experiment": experiment,
                "participant": participant
            }
        )
        if isinstance(events, Event):
            events = [events]
        assert len(events) == num_pages
        res = events[pos]
        assert isinstance(res, Page)
        return res

    prepare_logic = CodeBlock(lambda participant: (
        participant.var
            .set(with_namespace("complete"), False)
            .set(with_namespace("pos"), 0)
            .set(with_namespace("seq_length"), num_pages)
    ))

    update_logic = CodeBlock(
        lambda participant: (
            participant.var
                .set(
                    with_namespace("complete"),
                    participant.var.get(with_namespace("pos")) >= num_pages - 1
                )
                .inc(with_namespace("pos"))
        )
    )

    show_events = PageMaker(
        new_function,
        time_estimate=time_estimate / num_pages
    )

    condition = lambda participant: not participant.var.get(with_namespace("complete"))

    return join(
        prepare_logic,
        while_loop(
            label=with_namespace(label),
            condition=condition,
            logic=[show_events, update_logic],
            expected_repetitions=num_pages,
            fix_time_credit=False
        )
    )

class EndPage(PageMaker):
    def __init__(self):
        def f(participant):
            return Page(
                time_estimate=0,
                template_str=get_template("final-page.html"),
                template_arg={
                    "content": self.get_content(participant)
                }
            )

        super().__init__(f, time_estimate=3)

    def get_content(self, participant):
        return flask.Markup(
            "That's the end of the experiment! "
            + self.get_time_bonus_message(participant)
            + self.get_performance_bonus_message(participant)
            + " Thank you for taking part."
        )

    def get_time_bonus_message(self, participant):
        time_bonus = participant.time_credit.get_bonus()
        return f"""
            In addition to your base payment of <strong>&#36;{participant.base_payment:.2f}</strong>,
            you will receive a bonus of <strong>&#36;{time_bonus:.2f}</strong> for the
            time you spent on the experiment.
        """

    def get_performance_bonus_message(self, participant):
        bonus = participant.performance_bonus
        if bonus > 0.0:
            return f"You have also been awarded a performance bonus of <strong>&#36;{bonus:.2f}</strong>!"
        else:
            return ""

    def consume(self, experiment, participant):
        super().consume(experiment, participant)
        self.finalise_participant(experiment, participant)

    def finalise_participant(self, experiment, participant):
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

class Timeline():
    def __init__(self, *args):
        events = join(*args)
        self.events = events
        self.check_events()
        self.add_event_ids()
        self.estimated_time_credit = self.estimate_time_credit()

    def check_events(self):
        assert isinstance(self.events, list)
        assert len(self.events) > 0
        if not isinstance(self.events[-1], EndPage):
            raise ValueError("The final element in the timeline must be an EndPage.")
        self.check_for_time_estimate()
        self.check_start_fix_times()
        self.check_modules()

    def check_for_time_estimate(self):
        for i, event in enumerate(self.events):
            if (isinstance(event, Page) or isinstance(event, PageMaker)) and event.time_estimate is None:
                raise ValueError(f"Element {i} of the timeline was missing a time_estimate value.")

    def check_start_fix_times(self):
        try:
            _fix_time = False
            for i, event in enumerate(self.events):
                if isinstance(event, StartFixTime):
                    assert not _fix_time
                    _fix_time = True
                elif isinstance(event, EndFixTime):
                    assert _fix_time
                    _fix_time = False
        except AssertionError:
            raise ValueError(
                "Nested 'fix-time' constructs detected. This typically means you have "
                "nested conditionals or while loops with fix_time_credit=True. "
                "Such constructs cannot be nested; instead you should choose one level "
                "at which to set fix_time_credit=True."
            )

    def check_modules(self):
        modules = [x.label for x in self.events if isinstance(x, StartModule)]
        counts = Counter(modules)
        duplicated = [key for key, value in counts.items() if value > 1]
        if len(duplicated) > 0:
            raise ValueError("duplicated module ID(s): " + ", ".join(duplicated))

    def modules(self):
        from .participant import Participant
        participants = Participant.query.all()
        return {"modules": [{"id": event.module.id} for event in self.events
            if isinstance(event, StartModule)]}

    def get_trial_maker(self, trial_maker_id):
        events = self.events
        try:
            start = [e for e in events if isinstance(e, StartModule) and e.label == trial_maker_id][0]
        except IndexError:
            raise RuntimeError(f"Couldn't find trial maker with id = {trial_maker_id}.")
        trial_maker = start.module
        return trial_maker

    def add_event_ids(self):
        for i, event in enumerate(self.events):
            event.id = i
        for i, event in enumerate(self.events):
            if event.id != i:
                raise ValueError(
                    f"Failed to set unique IDs for each element in the timeline " +
                    f"(the element at 0-indexed position {i} ended up with the ID {event.id}). " +
                    "This usually means that the same Python object instantiation is reused multiple times " +
                    "in the same timeline. This kind of reusing is not permitted, instead you should " +
                    "create a fresh instantiation of each element."
            )

    class Branch():
        def __init__(self, label: str, children: dict):
            self.label = label
            self.children = children

        def summarise(self, mode, wage_per_hour=None):
            return [
                self.label,
                {key: child.summarise(mode, wage_per_hour) for key, child in self.children.items()}
            ]

        def get_max(self, mode, wage_per_hour=None):
            if mode == "all":
                raise ValueError("Can't call get_max with mode == 'all'.")
            return max([
                child.get_max(mode, wage_per_hour) for child in self.children.values()
            ])

    class Leaf():
        def __init__(self, value: float):
            self.value = value

        def summarise(self, mode, wage_per_hour=None):
            if mode == "time":
                return self.value
            elif mode == "bonus":
                assert wage_per_hour is not None
                return self.value * wage_per_hour / (60 * 60)
            elif mode == "all":
                return {
                    "time_seconds": self.summarise(mode="time"),
                    "time_minutes": self.summarise(mode="time") / 60,
                    "time_hours": self.summarise(mode="time") / (60 * 60),
                    "bonus": self.summarise(mode="bonus", wage_per_hour=wage_per_hour)
                }

        def get_max(self, mode, wage_per_hour=None):
            return self.summarise(mode, wage_per_hour)

    def estimate_time_credit(self, starting_event_id=0, starting_credit=0.0, starting_counter=0):
        event_id = starting_event_id
        time_credit = starting_credit
        counter = starting_counter

        while True:
            counter += 1
            if counter > 1e6:
                raise Exception("Got stuck in the estimate_time_credit() while loop, this shouldn't happen.")

            event = self.events[event_id]

            # logger.info(f"event_id = {event_id}, event = {event}")

            if event.returns_time_credit:
                time_credit += event.time_estimate * event.expected_repetitions

            if isinstance(event, StartFixTime):
                event_id = event.end_fix_time.id

            elif isinstance(event, EndFixTime):
                time_credit += event.time_estimate * event.expected_repetitions
                event_id += 1

            elif isinstance(event, StartSwitch):
                return self.Branch(
                    label=event.label,
                    children={
                        key: self.estimate_time_credit(
                            starting_event_id=branch_start_event.id,
                            starting_credit=time_credit,
                            starting_counter=counter
                        )
                        for key, branch_start_event in event.branch_start_events.items()
                    }
                )

            elif isinstance(event, EndSwitchBranch):
                event_id = event.target.id

            elif isinstance(event, EndPage):
                return self.Leaf(time_credit)

            else:
                event_id += 1

    def __len__(self):
        return len(self.events)

    def __getitem__(self, key):
        return self.events[key]

    def get_current_event(self, experiment, participant, resolve=True):
        n = participant.event_id
        N = len(self)
        if n >= N:
            raise ValueError(f"Tried to get element {n + 1} of a timeline with only {N} element(s).")
        else:
            res = self[n]
            if isinstance(res, PageMaker) and resolve:
                return res.resolve(experiment, participant)
            else:
                return res

    def advance_page(self, experiment, participant):
        finished = False
        while not finished:
            old_event = self.get_current_event(experiment, participant, resolve=False)
            if old_event.returns_time_credit:
                participant.time_credit.increment(old_event.time_estimate)

            participant.event_id += 1

            new_event = self.get_current_event(experiment, participant, resolve=False)
            new_event.consume(experiment, participant)

            if isinstance(new_event, Page) or isinstance(new_event, PageMaker):
                finished = True

def estimate_time_credit(events):
    return sum([
        event.time_estimate * event.expected_repetitions
        for event in events
        if event.returns_time_credit
    ])

class FailedValidation:
    def __init__(self, message="Invalid response, please try again."):
        self.message = message

class Response(Question):
    """
    A database-backed object that stores the participant's response to a
    :class:`~psynet.timeline.Page`.
    By default, one such object is created each time the participant
    tries to advance to a new page.

    This class subclasses the Dallinger :class:`~dallinger.models.Question` class,
    and hence can be found in the ``question`` table of the database.

    Attributes
    ----------

    answer
        The participant's answer, after formatting.
        Stored in ``response`` in the database.

    page_type: str
        The type of page administered.
        Stored in ``property1`` in the database.

    successful_validation: bool
        Whether the response validation was successful,
        allowing the participant to advance to the next page.
        Stored in ``property2`` in the database.
        (Not yet implemented)
    """

    __mapper_args__ = {"polymorphic_identity": "response"}
    __extra_vars__ = {}

    page_type = claim_field(1, "page_type", __extra_vars__, str)
    successful_validation = claim_field(2, "successful_validation", __extra_vars__, bool)

    @hybrid_property
    def answer(self):
        if self.response is None:
            return None
        else:
            return json.loads(self.response)

    @answer.setter
    def answer(self, answer):
        # Ideally we'd want to save NULL if the answer is None,
        # but the response field is non-nullable.
        self.response = json.dumps(answer)

    def __init__(self, participant, label, answer, page_type, metadata):
        super().__init__(
            participant=participant,
            question=label,
            response="",
            number=-1
        )
        self.answer = answer
        self.metadata = metadata
        self.page_type = page_type
        self.metadata = metadata

    @property
    def metadata(self):
        """
        A dictionary of metadata associated with the Response object.
        Stored in the ``details`` field in the database.
        """
        return self.details

    @metadata.setter
    def metadata(self, metadata):
        self.details = metadata

def is_list_of(x: list, what):
    for val in x:
        if not isinstance(val, what):
            return False
    return True

def join(*args):
    for i, arg in enumerate(args):
        if not ((arg is None) or (isinstance(arg, (Event, Module)) or is_list_of(arg, (Event, Module)))):
            raise TypeError(f"Element {i + 1} of the input to join() was neither an Event nor a list of Events nor a Module ({arg}).")

    if len(args) == 0:
        return []
    elif len(args) == 1:
        if isinstance(args[0], Event):
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
            elif isinstance(x, Event) and isinstance(y, Event):
                return [x, y]
            elif isinstance(x, Event) and isinstance(y, list):
                return [x] + y
            elif isinstance(x, list) and isinstance(y, Event):
                return x + [y]
            elif isinstance(x, list) and isinstance(y, list):
                return x + y
            else:
                return Exception("An unexpected error occurred.")

        return reduce(f, args)

class StartWhile(NullEvent):
    def __init__(self, label):
        # targets = {
        #     True: self,
        #     False: end_while
        # }
        # super().__init__(condition, targets)
        super().__init__()
        self.label = label

class EndWhile(NullEvent):
    def __init__(self, label):
        super().__init__()
        self.label = label

def while_loop(label: str, condition: Callable, logic, expected_repetitions: int, fix_time_credit=True):
    """
    Loops a series of events while a given criterion is satisfied.
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
        An event (or list of events) to display while ``condition`` returns ``True``.

    expected_repetitions:
        The number of times the loop is expected to be seen by a given participant.
        This doesn't have to be completely accurate, but it is used for estimating the length
        of the total experiment.

    fix_time_credit:
        Whether participants should receive the same time credit irrespective of whether
        ``condition`` returns ``True`` or not; defaults to ``True``, so that all participants
        receive the same credit.

    Returns
    -------

    list
        A list of events that can be embedded in a timeline using :func:`psynet.timeline.join`.
    """

    start_while = StartWhile(label)
    end_while = EndWhile(label)

    logic = join(logic)
    logic = multiply_expected_repetitions(logic, expected_repetitions)

    conditional_logic = join(logic, GoTo(start_while))

    events = join(
        start_while,
        conditional(
            label,
            condition,
            conditional_logic,
            fix_time_credit=False,
            log_chosen_branch=False
        ),
        end_while
    )

    if fix_time_credit:
        time_estimate = estimate_time_credit(logic)
        return fix_time(events, time_estimate)
    else:
        return events

def check_branches(branches):
    try:
        assert isinstance(branches, dict)
        for branch_name, branch_events in branches.items():
            assert isinstance(branch_events, Event) or is_list_of(branch_events, Event)
            if isinstance(branch_events, Event):
                branches[branch_name] = [branch_events]
        return branches
    except AssertionError:
        raise TypeError("<branches> must be a dict of (lists of) Event objects.")

def switch(
        label: str,
        function: Callable,
        branches: dict,
        fix_time_credit: bool = True,
        log_chosen_branch: bool = True
    ):
    """
    Selects a series of events to display to the participant according to a
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
        to an event (or list of events) that can be selected by ``function``.

    fix_time_credit:
        Whether participants should receive the same time credit irrespective of whether
        ``condition`` returns ``True`` or not; defaults to ``True``, so that all participants
        receive the same credit.

    log_chosen_branch:
        Whether to keep a log of which participants took each branch; defaults to ``True``.

    Returns
    -------

    list
        A list of events that can be embedded in a timeline using :func:`psynet.timeline.join`.
    """

    check_function_args(function, ("self", "experiment", "participant"), need_all=False)
    branches = check_branches(branches)

    all_branch_starts = dict()
    all_events = []
    final_event = EndSwitch(label)

    for branch_name, branch_events in branches.items():
        branch_start = StartSwitchBranch(branch_name)
        branch_end = EndSwitchBranch(branch_name, final_event)
        all_branch_starts[branch_name] = branch_start
        all_events = all_events + [branch_start] + branch_events + [branch_end]

    start_switch = StartSwitch(label, function, branch_start_events=all_branch_starts, log_chosen_branch=log_chosen_branch)
    combined_events = [start_switch] + all_events + [final_event]

    if fix_time_credit:
        time_estimate = max([
            estimate_time_credit(branch_events)
            for branch_events in branches.values()
        ])
        return fix_time(combined_events, time_estimate)
    else:
        return combined_events

class StartSwitch(ReactiveGoTo):
    def __init__(self, label, function, branch_start_events, log_chosen_branch=True):
        if log_chosen_branch:
            def function_2(experiment, participant):
                val = function(experiment, participant)
                log_entry = [label, val]
                participant.append_branch_log(log_entry)
                return val
            super().__init__(function_2, targets=branch_start_events)
        else:
            super().__init__(function, targets=branch_start_events)
        self.label = label
        self.branch_start_events = branch_start_events
        self.log_chosen_branch = log_chosen_branch

class EndSwitch(NullEvent):
    def __init__(self, label):
        self.label = label

class StartSwitchBranch(NullEvent):
    def __init__(self, name):
        super().__init__()
        self.name = name

class EndSwitchBranch(GoTo):
    def __init__(self, name, final_event):
        super().__init__(target=final_event)
        self.name = name

def conditional(
    label: str,
    condition: Callable,
    logic_if_true,
    logic_if_false=None,
    fix_time_credit: bool = True,
    log_chosen_branch: bool = True
    ):
    """
    Executes a series of events if and only if a certain condition is satisfied.

    Parameters
    ----------

    label:
        Internal label to assign to the construct.

    condition:
        A function with up to two arguments named ``participant`` and ``experiment``,
        that is executed once the participant reaches the corresponding part of the timeline,
        returning a Boolean.

    logic_if_true:
        An event (or list of events) to display if ``condition`` returns ``True``.

    logic_if_false:
        An optional event (or list of events) to display if ``condition`` returns ``False``.

    fix_time_credit:
        Whether participants should receive the same time credit irrespective of whether
        ``condition`` returns ``True`` or not; defaults to ``True``, so that all participants
        receive the same credit.

    log_chosen_branch:
        Whether to keep a log of which participants took each branch; defaults to ``True``.

    Returns
    -------

    list
        A list of events that can be embedded in a timeline using :func:`psynet.timeline.join`.
    """
    return switch(
        label,
        function=condition,
        branches={
            True: logic_if_true,
            False: NullEvent() if logic_if_false is None else logic_if_false
        },
        fix_time_credit=fix_time_credit,
        log_chosen_branch=log_chosen_branch
    )

class ConditionalEvent(Event):
    def __init__(self, label: str):
        self.label = label

class StartConditional(ConditionalEvent):
    pass

class EndConditional(ConditionalEvent):
    pass

def fix_time(events, time_estimate):
    end_fix_time = EndFixTime(time_estimate)
    start_fix_time = StartFixTime(time_estimate, end_fix_time)
    return join(start_fix_time, events, end_fix_time)

def multiply_expected_repetitions(logic, factor: float):
    assert isinstance(logic, Event) or is_list_of(logic, Event)
    if isinstance(logic, Event):
        logic.multiply_expected_repetitions(factor)
    else:
        for event in logic:
            event.multiply_expected_repetitions(factor)
    return logic

class ExperimentProgressBar():
    def __init__(self, progress: float, show=True, min_pct=5, max_pct=99):
        self.show = show
        self.percentage = round(progress * 100)
        if self.percentage > max_pct:
            self.percentage = max_pct
        elif self.percentage < min_pct:
            self.percentage = min_pct

class Footer():
    def __init__(self, text_to_show: List[str], escape=True, show=True):
        self.show = show
        self.text_to_show = [x if escape else flask.Markup(x) for x in text_to_show]

class Module():
    default_id = None
    default_events = None

    def __init__(self, id_: str = None, *args):
        events = join(*args)

        if self.default_id is None and id_ is None:
            raise ValueError("Either one of <default_id> or <id_> must not be none.")
        if self.default_events is None and events is None:
            raise ValueError("Either one of <default_events> or <events> must not be none.")

        self.id = id_ if id_ is not None else self.default_id
        self.events = events if events is not None else self.default_events

    @classmethod
    def started_and_finished_times(cls, participants, module_id):
        return [{"time_started": participant.modules[module_id]["time_started"][0],
                 "time_finished": participant.modules[module_id]["time_finished"][0]}
                for participant in participants if module_id in participant.finished_modules]

    @classmethod
    def median_finish_time_in_min(cls, participants, module_id):
        started_and_finished_times = cls.started_and_finished_times(participants, module_id)

        if not started_and_finished_times:
            return None

        durations_in_min = []
        for start_end_times in started_and_finished_times:
            if not (start_end_times["time_started"] and start_end_times["time_finished"]):
                continue
            datetime_format = '%Y-%m-%dT%H:%M:%S.%f'
            t1 = datetime.strptime(start_end_times["time_started"], datetime_format)
            t2 = datetime.strptime(start_end_times["time_finished"], datetime_format)
            durations_in_min.append((t2 - t1).total_seconds() / 60)

        if not durations_in_min:
            return None

        return median(sorted(durations_in_min))

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
        finished_participants = [p for p in participants if self.id in p.finished_modules]
        finished_participants.sort(key=lambda p: p.modules[self.id]["time_finished"][0])
        return finished_participants

    def resolve(self):
        return join(
            StartModule(self.id, module=self),
            self.events,
            EndModule(self.id)
        )

    def visualize(self):
        phase = self.phase if hasattr(self, "phase") else None

        if self.started_participants:
            time_started_last = self.started_participants[-1].modules[self.id]["time_started"][0]
        if self.finished_participants:
            time_finished_last = self.finished_participants[-1].modules[self.id]["time_finished"][0]
            median_finish_time_in_min = round(Module.median_finish_time_in_min(self.finished_participants, self.id), 1)

        div = tags.div()
        with div:
            with tags.h4("Module"):
                tags.i(self.id)
            with tags.ul(cls="details"):
                if phase is not None:
                    tags.li(f"Phase: {phase}")
                tags.li(f"Participants started: {len(self.started_participants)}")
                tags.li(f"Participants finished: {len(self.finished_participants)}")
                if self.started_participants:
                    tags.li(f"Participant started last: {format_datetime_string(time_started_last)}")
                if self.finished_participants:
                    tags.li(f"Participant finished last: {format_datetime_string(time_finished_last)}")
                    tags.li(f"Median time spent: {median_finish_time_in_min} min.")

        return div.render()

    def visualize_tooltip(self):
        if self.finished_participants:
            median_finish_time_in_min = Module.median_finish_time_in_min(self.finished_participants, self.id)

        span = tags.span()
        with span:
            tags.b(self.id)
            tags.br()
            tags.span(f"{len(self.started_participants)} started, {len(self.finished_participants)} finished,")
            if self.finished_participants:
                tags.br()
                tags.span(f"{round(median_finish_time_in_min, 1)} min. (median)")

        return span.render()

    def get_progress_info(self):
        target_num_participants = (self.target_num_participants
                                   if hasattr(self, "target_num_participants")
                                   else None)
        # TODO a more sophisticated calculation of progress
        progress = (len(self.finished_participants) / target_num_participants
                    if target_num_participants is not None and target_num_participants > 0
                    else 1)

        return { self.id: { "started_num_participants": len(self.started_participants),
                            "finished_num_participants": len(self.finished_participants),
                            "target_num_participants": target_num_participants,
                            "progress": progress } }

class StartModule(NullEvent):
    def __init__(self, label, module):
        super().__init__()
        self.label = label
        self.module = module

    def consume(self, experiment, participant):
        participant.start_module(self.label)

class EndModule(NullEvent):
    def __init__(self, label):
        super().__init__()
        self.label = label

    def consume(self, experiment, participant):
        participant.end_module(self.label)

class ExperimentSetupRoutine(NullEvent):
    def __init__(self, function):
        self.check_function(function)
        self.function = function

    def check_function(self, function):
        if not self._is_function(function) and check_function_args(function, ["experiment"]):
            raise TypeError("<function> must be a function or method of the form f(experiment).")

    @staticmethod
    def _is_function(x):
        return callable(x)

class BackgroundTask(NullEvent):
    def __init__(self, label, function, interval_sec, run_on_launch=False):
        check_function_args(function, args=[])
        self.label = label
        self.function = function
        self.interval_sec = interval_sec
        self.run_on_launch = run_on_launch

    def safe_function(self):
        start_time = time.monotonic()
        logger.info("Executing the background task '%s'...", self.label)
        try:
            self.function()
            end_time = time.monotonic()
            time_taken = end_time - start_time
            logger.info("The background task '%s' completed in %s seconds.", self.label, f"{time_taken:.3f}")
        except Exception:
            logger.info("An exception was thrown in the background task '%s'.", self.label, exc_info=True)

    def daemon(self):
        if self.run_on_launch:
            self.safe_function()
        while True:
            gevent.sleep(self.interval_sec)
            self.safe_function()

class ParticipantFailRoutine(NullEvent):
    def __init__(self, label, function):
        check_function_args(function, args=["participant", "experiment"], need_all=False)
        self.label = label
        self.function = function

class RecruitmentCriterion(NullEvent):
    def __init__(self, label, function):
        check_function_args(function, args=["experiment"], need_all=False)
        self.label = label
        self.function = function

