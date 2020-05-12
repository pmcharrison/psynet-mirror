# pylint: disable=attribute-defined-outside-init

from sqlalchemy import desc

import dallinger.models
from . import field
from .field import VarStore, claim_var
from .timeline import Response
import json
import os

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

# pylint: disable=unused-import
import rpdb

class Participant(dallinger.models.Participant):
    """
    Represents an individual participant taking the experiment.
    The object is linked to the database - when you make changes to the
    object, it should be mirrored in the database.

    Users should not have to instantiate these objects directly.

    The class extends the ``Participant`` class from base Dallinger
    (:class:`dallinger.models.Participant`) to add some useful features,
    in particular the ability to store arbitrary variables.

    The following attributes are recommended for external use:

    * :attr:`~psynet.participant.Participant.answer`
    * :attr:`~psynet.participant.Participant.var`
    * :attr:`~psynet.participant.Participant.failure_tags`

    The following method is recommended for external use:

    * :meth:`~psynet.participant.Participant.append_failure_tags`

    See below for more details.

    Attributes
    ----------

    id : int
        The participant's unique ID.

    event_id : int
        Represents the participant's position in the timeline.
        Should not be modified directly.
        Stored in the database as ``property1``.

    page_uuid : str
        A long unique string that is randomly generated when the participant advances
        to a new page, used as a passphrase to guarantee the security of
        data transmission from front-end to back-end.
        Should not be modified directly.
        Stored in the database as ``property2``.

    complete : bool
        Whether the participant has successfully completed the experiment.
        A participant is considered to have successfully completed the experiment
        once they hit a :class:`~psynet.timeline.SuccessfulEndPage`.
        Should not be modified directly.
        Stored in the database as ``property3``.

    answer : object
        The most recent answer submitted by the participant.
        Can take any form that can be automatically serialized to JSON.
        Should not be modified directly.
        Stored in the database as ``property4``.

    response : Response
        An object of class :class:`~psynet.timeline.Response`
        providing detailed information about the last response submitted
        by the participant. This is a more detailed version of ``answer``.

    branch_log : list
        Stores the conditional branches that the participant has taken
        through the experiment.
        Should not be modified directly.
        Stored in the database as ``property5``.

    failure_tags : list
        Stores tags that identify the reason that the participant has failed
        the experiment (if any). For example, if a participant fails
        a microphone pre-screening test, one might add "failed_mic_test"
        to this tag list.
        Should be modified using the method :meth:`~psynet.participant.Participant.append_failure_tags`.
        Stored in the database as part of the ``details`` field.

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    progress : float [0 <= x <= 1]
        The participant's estimated progress through the experiment.
    """

    __mapper_args__ = {"polymorphic_identity": "participant"}

    event_id = field.claim_field(1, int)
    page_uuid = field.claim_field(2, str)
    complete = field.claim_field(3, bool)
    answer = field.claim_field(4, object)
    branch_log = field.claim_field(5, list)

    failure_tags = claim_var("failure_tags", use_default=True, default=lambda: [])
    last_response_id = claim_var("last_response_id")
    base_payment = claim_var("base_payment")
    performance_bonus = claim_var("performance_bonus")

    def set_answer(self, value):
        self.answer = value
        return self

    def initialise(self, experiment):
        self.event_id = -1
        self.complete = False
        self.time_credit.initialise(experiment)
        self.performance_bonus = 0.0
        self.base_payment = experiment.base_payment

    def inc_performance_bonus(self, value):
        self.performance_bonus = self.performance_bonus + value

    @property
    def response(self):
        return (
            Response
                .query
                .filter_by(participant_id=self.id)
                .order_by(desc(Response.id))
                .first()
        )

    @property
    def progress(self):
        return 1.0 if self.complete else self.time_credit.progress

    @property
    def var(self):
        return VarStore(self)

    @property
    def time_credit(self):
        return TimeCreditStore(self)

    @property
    def initialised(self):
        return self.event_id is not None

    def append_branch_log(self, entry: str):
        # We need to create a new list otherwise the change may not be recognised
        # by SQLAlchemy(?)
        if not isinstance(entry, list) or len(entry) != 2 or not isinstance(entry[0], str):
            raise ValueError(f"Log entry must be a list of length 2 where the first element is a string (received {entry}).")
        if json.loads(json.dumps(entry)) != entry:
            raise ValueError(
                f"The provided log entry cannot be accurately serialised to JSON (received {entry}). " +
                "Please simplify the log entry (this is typically determined by the output type of the user-provided function " +
                "in switch() or conditional())."
            )
        self.branch_log = self.branch_log + [entry]

    def append_failure_tags(self, *tags):
        """
        Appends tags to the participant's list of failure tags.
        Duplicate tags are ignored.
        See :attr:`~psynet.participant.Participant.failure_tags` for details.

        Parameters
        ----------

        *tags
            Tags to append.

        Returns
        -------

        :class:`psynet.participant.Participant`
            The updated ``Participant`` object.

        """
        original = self.failure_tags
        new = [*tags]
        combined = list(set(original + new))
        self.failure_tags = combined
        return self

def get_participant(participant_id: int):
    """
    Returns the participant with a given ID.

    Parameters
    ----------

    participant_id
        ID of the participant to get.

    Returns
    -------

    :class:`psynet.participant.Participant`
        The requested participant.
    """
    return Participant.query.filter_by(id=participant_id).one()

class TimeCreditStore:
    fields = [
        "confirmed_credit",
        "is_fixed",
        "pending_credit",
        "max_pending_credit",
        "wage_per_hour",
        "experiment_max_time_credit",
        "experiment_max_bonus"
    ]

    def __init__(self, participant):
        self.participant = participant

    def get_internal_name(self, name):
        if name not in self.fields:
            raise ValueError(f"{name} is not a valid field for TimeCreditStore.")
        return f"__time_credit__{name}"

    def __getattr__(self, name):
        if name == "participant":
            return self.__dict__["participant"]
        else:
            return self.participant.var.get(self.get_internal_name(name))

    def __setattr__(self, name, value):
        if name == "participant":
            self.__dict__["participant"] = value
        else:
            self.participant.var.set(self.get_internal_name(name), value)

    def initialise(self, experiment):
        self.confirmed_credit = 0.0
        self.is_fixed = False
        self.pending_credit = 0.0
        self.max_pending_credit = 0.0
        self.wage_per_hour = experiment.wage_per_hour

        experiment_estimated_time_credit = experiment.timeline.estimated_time_credit
        self.experiment_max_time_credit = experiment_estimated_time_credit.get_max(mode="time")
        self.experiment_max_bonus = experiment_estimated_time_credit.get_max(mode="bonus", wage_per_hour=experiment.wage_per_hour)
        self.export_estimated_payments(experiment_estimated_time_credit, experiment)

    def export_estimated_payments(self, experiment_estimated_time_credit, experiment, path="experiment-estimated-payments.json"):
        with open(path, "w+") as file:
            summary = experiment_estimated_time_credit.summarise(
                mode="all",
                wage_per_hour=experiment.wage_per_hour
            )
            json.dump(summary, file, indent=4)
        logger.info("Exported estimated payment summary to %s.", os.path.abspath(path))

    def increment(self, value: float):
        if self.is_fixed:
            self.pending_credit += value
            if self.pending_credit > self.max_pending_credit:
                self.pending_credit = self.max_pending_credit
        else:
            self.confirmed_credit += value

    def start_fix_time(self, time_estimate: float):
        assert not self.is_fixed
        self.is_fixed = True
        self.pending_credit = 0.0
        self.max_pending_credit = time_estimate

    def end_fix_time(self, time_estimate: float):
        assert self.is_fixed
        self.is_fixed = False
        self.pending_credit = 0.0
        self.max_pending_credit = 0.0
        self.confirmed_credit += time_estimate

    def get_bonus(self):
        return self.wage_per_hour * self.confirmed_credit / (60 * 60)

    def estimate_time_credit(self):
        return self.confirmed_credit + self.pending_credit

    def estimate_bonus(self):
        return self.wage_per_hour * self.estimate_time_credit() / (60 * 60)

    @property
    def progress(self):
        return self.estimate_time_credit() / self.experiment_max_time_credit
