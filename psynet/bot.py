import json
import time
import uuid
from datetime import datetime
from statistics import mean
from typing import List, Optional

from cached_property import cached_property
from dallinger import db

from psynet.db import transaction

from .participant import Participant, ParticipantDriver
from .utils import NoArgumentProvided, get_logger, log_time_taken, wait_until

logger = get_logger()


class Bot(Participant):
    def __init__(
        self,
        recruiter_id="bot_recruiter",
        worker_id=None,
        assignment_id=None,
        unique_id=None,
        hit_id="",
        mode="debug",
    ):
        self.wait_until_experiment_launch_is_complete()

        if worker_id is None:
            worker_id = str(uuid.uuid4())

        if assignment_id is None:
            assignment_id = str(uuid.uuid4())

        logger.info("Initializing bot with worker ID %s.", worker_id)

        super().__init__(
            self.experiment,
            recruiter_id=recruiter_id,
            worker_id=worker_id,
            assignment_id=assignment_id,
            hit_id=hit_id,
            mode=mode,
        )

        self._advance_to_first_page()

        db.session.add(self)
        db.session.commit()

    def _advance_to_first_page(self):
        assert self.elt_id == [-1]
        self.experiment.timeline.advance_page(self.experiment, self)

    def initialize(self, experiment):
        self.experiment.initialize_bot(bot=self)
        super().initialize(experiment)

    def wait_until_experiment_launch_is_complete(self):
        from .experiment import is_experiment_launched

        def f():
            logger.info("Waiting for experiment launch to complete....")
            return is_experiment_launched()

        wait_until(
            f, max_wait=60, error_message="Experiment launch didn't finish in time"
        )

    @cached_property
    def experiment(self):
        from .experiment import get_experiment

        return get_experiment()

    @cached_property
    def timeline(self):
        return self.experiment.timeline

    def get_current_page(self):
        return self.experiment.get_current_page(self.experiment, self)

    @log_time_taken
    def take_experiment(self, *args, **kwargs):
        raise NotImplementedError(
            "Bot.take_experiment has now been removed. "
            "Please use Experiment.run_bot instead."
        )

    def run_to_completion(self, time_factor=0, render_pages: bool = False):
        # We tried the following code to simulate the Flask server and thereby
        # run Page.render() functions directly. However the approach fails
        # when we try to run multiple tests in succession, because Flask
        # doesn't let us deregister the old apps.
        #
        # from gunicorn import util
        # from .utils import working_directory
        # with working_directory(self.experiment.var.server_working_directory):
        # app = util.import_app("dallinger.experiment_server.sockets:app")
        # with app.app_context(), app.test_request_context():
        n_pages = 0

        page_processing_times = []
        page_total_times = []

        while True:
            page_time_started = time.monotonic()

            # This commit is necessary because get_current_page can make changes to the participant
            # (e.g. advancing them to the next page in the timeline). We need to commit so that the
            # server (as accessed via the HTTP request) has access to this information too.

            sleep_time = self.take_page(
                time_factor=time_factor, render_page=render_pages
            )["sleep_time"]

            page_time_finished = time.monotonic()
            page_total_time = page_time_finished - page_time_started

            page_total_times.append(page_total_time)

            page_processing_time = page_total_time - sleep_time
            page_processing_times.append(page_processing_time)

            n_pages += 1

            if not self.status == "working":
                break

        if n_pages > 0:
            mean_page_processing_time = mean(page_processing_times)
        else:
            mean_page_processing_time = None

        total_experiment_time = (datetime.now() - self.creation_time).total_seconds()

        # Todo - migrate these metrics to generic Participants (not just bots) so that we can report them
        # everywhere
        stats = {
            "page_count": self.page_count,
            "progress": self.progress,
            "mean_page_processing_time": mean_page_processing_time,
            "total_wait_page_time": self.total_wait_page_time,
            "total_experiment_time": total_experiment_time,
        }

        logger.info(
            f"Bot {self.id} has finished the experiment (took {stats['page_count']} page(s), "
            f"progress = {100 * stats['progress']:.0f}%, "
            f"mean processing time per page = {stats['mean_page_processing_time']:.3f} seconds, "
            f"total WaitPage time = {stats['total_wait_page_time']:.3f} seconds, "
            f"total experiment time = {stats['total_experiment_time']:.3f} seconds)."
        )

        return stats

    def take_page(self, *args, **kwargs):
        raise NotImplementedError(
            "Bot.take_page has now been removed. "
            "Please use Experiment.take_page instead."
        )

    def submit_response(self, response=NoArgumentProvided):
        page = self.get_current_page()
        self.take_page(page, response=response)

    def run_until(self, condition, render_pages=False):
        while True:
            current_page = self.get_current_page()
            if condition(current_page):
                break
            self.take_page(current_page, render_page=render_pages)
            if not self.status == "working":
                raise RuntimeError(
                    "Bot finished the experiment before condition was met."
                )


class BotResponse:
    """
    Defines a bot's response to a given page.

    Parameters
    ----------
        raw_answer :
            The raw_answer returned from the page.

        metadata :
            A dictionary of metadata.

        blobs :
            A dictionary of blobs returned from the front-end.

        client_ip_address :
            The client's IP address.
    """

    def __init__(
        self,
        *,
        raw_answer=NoArgumentProvided,
        answer=NoArgumentProvided,
        metadata=NoArgumentProvided,
        blobs=NoArgumentProvided,
        client_ip_address=NoArgumentProvided,
    ):
        if raw_answer != NoArgumentProvided and answer != NoArgumentProvided:
            raise ValueError(
                "raw_answer and answer cannot both be provided; you should probably just provide raw_answer."
            )

        if raw_answer == NoArgumentProvided and answer == NoArgumentProvided:
            raise ValueError("At least one of raw_answer and answer must be provided.")

        if answer != NoArgumentProvided:
            raise ValueError(
                "BotResponse no longer supports the answer parameter. Please use the raw_answer parameter instead, "
                "and note that it will be passed through .format_answer."
            )

        if blobs == NoArgumentProvided:
            blobs = {}

        if metadata == NoArgumentProvided:
            metadata = {}

        if client_ip_address == NoArgumentProvided:
            client_ip_address = None

        self.raw_answer = raw_answer
        self.answer = answer
        self.metadata = metadata
        self.blobs = blobs
        self.client_ip_address = client_ip_address

    def __json__(self):
        data = {}

        if self.raw_answer != NoArgumentProvided:
            data["raw_answer"] = self.raw_answer

        if self.answer != NoArgumentProvided:
            data["answer"] = self.answer

        if self.metadata != NoArgumentProvided:
            data["metadata"] = self.metadata

        if self.blobs != NoArgumentProvided:
            data["blobs"] = {key: value.__json__() for key, value in self.blobs.items()}

        return data

    def to_json(self):
        return json.dumps(self.__json__())


def advance_past_wait_pages(bots: List["BotDriver"], max_iterations=10):
    from .page import WaitPage

    iteration = 0
    while True:
        iteration += 1
        any_waiting = False
        for bot in bots:
            current_page = bot.get_current_page()
            if isinstance(current_page, WaitPage):
                any_waiting = True
                bot.take_page()
        if not any_waiting:
            break
        if iteration >= max_iterations:
            raise RuntimeError("Not all bots finished waiting in time.")


class BotDriver(ParticipantDriver):
    """
    Driver class for automating bot participants in an experiment.

    The :class:`~psynet.participant.BotDriver` class is a convenience subclass of :class:`~psynet.participant.ParticipantDriver`
    specifically focused on creating and controlling bot participants.

    If no ``id_`` is specified, a new :class:`~psynet.bot.Bot` instance is created automatically.
    Otherwise, behaves like :class:`~psynet.participant.ParticipantDriver`.

    This class is primarily used for automated testing, simulation studies, and experiments where human participants
    interact with virtual (bot) participants. Like its parent, it interacts with the experiment server via HTTP requests,
    ensuring that the simulation closely matches real participant behavior.

    Parameters
    ----------
    id_ : int, optional
        The ID of the participant to automate
        (i.e. corresponding to the ``id`` column in the Participant table).
        If not provided, a new bot participant is created.
    render_pages : bool, optional
        Whether to render pages during automation (default is True).
    time_factor : float, optional
        Factor to multiply the simulated page time by (default is 0.0).
    """

    def __init__(
        self,
        id_: Optional[int] = None,
    ):
        from psynet.bot import Bot

        if id_ is None:
            with transaction():
                bot = Bot()
                db.session.add(bot)
                db.session.flush()
                id_ = bot.id

        super().__init__(id_)
