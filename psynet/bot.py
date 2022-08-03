import time
import uuid

from cached_property import cached_property
from dallinger import db

from .participant import Participant
from .timeline import EndPage, Page
from .utils import NoArgumentProvided, get_experiment, get_logger, log_time_taken

logger = get_logger()


class Bot(Participant):
    def __init__(
        self,
        recruiter_id="bot_recruiter",
        worker_id=None,
        assignment_id=None,
        hit_id="",
        mode="debug",
    ):
        if worker_id is None:
            worker_id = str(uuid.uuid4())

        if assignment_id is None:
            assignment_id = str(uuid.uuid4())

        super().__init__(
            self.experiment,
            recruiter_id=recruiter_id,
            worker_id=worker_id,
            assignment_id=assignment_id,
            hit_id=hit_id,
            mode=mode,
        )

        self.experiment.initialize_bot(bot=self)
        db.session.commit()

    @cached_property
    def experiment(self):
        return get_experiment()

    @cached_property
    def timeline(self):
        return self.experiment.timeline

    @log_time_taken
    def take_experiment(self, time_factor=0):
        """
        Parameters
        ----------

        time_factor :
            Determines how long the bot spends on each page.
            If 0, the bot spends no time on each page.
            If 1, the bot spends ``time_estimate`` time on each page.
            This
        """
        logger.info(f"Bot {self.id} is starting the experiment.")
        while True:
            self.take_page(time_factor)
            db.session.refresh(self)
            if not self.status == "working":
                break

    def take_page(self, time_factor):
        bot = self
        experiment = self.experiment
        page = experiment.timeline.get_current_elt(experiment, bot)
        assert isinstance(page, Page)

        time_taken = page.time_estimate * time_factor
        if time_factor > 0:
            time.sleep(time_taken)

        response = page.call__bot_response(experiment, bot)

        if "time_taken" not in response.metadata:
            response.metadata["time_taken"] = time_taken

        if not isinstance(page, EndPage):
            experiment.process_response(
                participant_id=self.id,
                raw_answer=response.raw_answer,
                blobs=response.blobs,
                metadata=response.metadata,
                page_uuid=self.page_uuid,
                client_ip_address=response.client_ip_address,
                answer=response.answer,
            )
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
