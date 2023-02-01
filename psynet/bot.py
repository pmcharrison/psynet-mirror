import time
import uuid

import requests
from cached_property import cached_property
from dallinger import db
from sqlalchemy import Column, Integer

from .participant import Participant
from .timeline import EndPage, Page
from .utils import (
    NoArgumentProvided,
    get_logger,
    log_time_taken,
    time_logger,
    wait_until,
)

logger = get_logger()


class Bot(Participant):
    page_count = Column(Integer, default=1)

    def __init__(
        self,
        recruiter_id="bot_recruiter",
        worker_id=None,
        assignment_id=None,
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

        db.session.commit()

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
    def take_experiment(self, time_factor=0, render_pages: bool = False):
        """
        Parameters
        ----------

        time_factor :
            Determines how long the bot spends on each page.
            If 0, the bot spends no time on each page.
            If 1, the bot spends ``time_estimate`` time on each page.

        render_page :
            Whether to run page rendering code (default: False).
            This is generally only useful for testing.
        """
        logger.info(f"Bot {self.id} is starting the experiment.")
        self.run_to_completion(time_factor, render_pages)

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
        while True:
            page = self.get_current_page()
            if render_pages:
                with time_logger("timeline_route"):
                    req = requests.get(
                        f"http://localhost:5000/timeline?participant_id={self.id}&auth_token={self.auth_token}"
                    )
                assert req.status_code == 200
            with time_logger("take_page"):
                self.take_page(page, time_factor)
            db.session.commit()
            if not self.status == "working":
                break
        logger.info(
            f"Bot {self.id} has finished the experiment (took {self.page_count} page(s))."
        )

    def take_page(self, page=None, time_factor=0):
        from .page import WaitPage

        if page is None:
            with time_logger("get_current_page"):
                page = self.get_current_page()

        bot = self
        experiment = self.experiment
        assert isinstance(page, Page)

        time_taken = page.time_estimate * time_factor

        if time_taken == 0 and isinstance(page, WaitPage):
            time_taken = 0.5

        if time_taken > 0:
            time.sleep(time_taken)

        response = page.call__bot_response(experiment, bot)

        if "time_taken" not in response.metadata:
            response.metadata["time_taken"] = time_taken

        if not isinstance(page, EndPage):
            try:
                with time_logger("process_response"):
                    experiment.process_response(
                        participant_id=self.id,
                        raw_answer=response.raw_answer,
                        blobs=response.blobs,
                        metadata=response.metadata,
                        page_uuid=self.page_uuid,
                        client_ip_address=response.client_ip_address,
                        answer=response.answer,
                    )
            except RuntimeError as err:
                if "Working outside of request context" in str(err):
                    err.args = (
                        err.args[0]
                        + "\n\nNote: The 'working outside of request context' error can usually be ignored "
                        "during testing as it typically comes from Flask trying to construct an "
                        "error page without a valid request context. The real error probably "
                        "happened earlier though.",
                    )
                raise

        self.page_count += 1

        db.session.commit()


class BotResponse:
    """
    Defines a bot's response to a given page.

    Parameters
    ----------
        raw_answer :
            The raw_answer returned from the page.

        answer :
            The (formatted) answer, as would ordinarily be computed by ``format_answer``.

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
