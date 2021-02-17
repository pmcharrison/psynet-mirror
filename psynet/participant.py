# pylint: disable=attribute-defined-outside-init

import datetime
import json
import os

import dallinger.models
from dallinger.config import get_config
from dallinger.notifications import admin_notifier
from sqlalchemy import desc

from . import field
from .field import VarStore, claim_var, extra_var
from .timeline import Response
from .utils import get_logger, serialise_datetime, unserialise_datetime

logger = get_logger()

# pylint: disable=unused-import


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

    client_ip_address : str
        The participant's IP address as reported by Flask.

    answer_is_fresh : bool
        ``True`` if the current value of ``participant.answer`` (and similarly ``participant.last_response_id`` and
        ``participant.last_response``) comes from the last page that the participant saw, ``False`` otherwise.
    """

    __mapper_args__ = {"polymorphic_identity": "participant"}
    __extra_vars__ = {}

    event_id = field.claim_field(1, "event_id", __extra_vars__, int)
    page_uuid = field.claim_field(2, "page_uuid", __extra_vars__, str)
    complete = field.claim_field(3, "complete", __extra_vars__, bool)
    answer = field.claim_field(4, "answer", __extra_vars__, object)
    branch_log = field.claim_field(5, "branch_log", __extra_vars__, list)

    initialised = claim_var(
        "initialised", __extra_vars__, use_default=True, default=lambda: False
    )
    failure_tags = claim_var(
        "failure_tags", __extra_vars__, use_default=True, default=lambda: []
    )
    last_response_id = claim_var(
        "last_response_id", __extra_vars__, use_default=True, default=lambda: None
    )
    base_payment = claim_var("base_payment", __extra_vars__)
    performance_bonus = claim_var("performance_bonus", __extra_vars__)
    modules = claim_var("modules", __extra_vars__, use_default=True, default=lambda: {})
    client_ip_address = claim_var(
        "client_ip_address", __extra_vars__, use_default=True, default=lambda: ""
    )
    answer_is_fresh = claim_var(
        "answer_is_fresh", __extra_vars__, use_default=True, default=lambda: False
    )

    def __json__(self):
        x = super().__json__()
        field.json_clean(x, details=True)
        field.json_add_extra_vars(x, self)
        x["started_modules"] = self.started_modules
        x["finished_modules"] = self.finished_modules
        del x["modules"]
        field.json_format_vars(x)
        return x

    @property
    def last_response(self):
        if self.last_response_id is None:
            return None
        return Response.query.filter_by(id=self.last_response_id).one()

    @property
    @extra_var(__extra_vars__)
    def started_modules(self):
        modules = [
            (key, value)
            for key, value in self.modules.items()
            if len(value["time_started"]) > 0
        ]
        modules.sort(key=lambda x: unserialise_datetime(x[1]["time_started"][0]))
        return [m[0] for m in modules]

    @property
    @extra_var(__extra_vars__)
    def finished_modules(self):
        modules = [
            (key, value)
            for key, value in self.modules.items()
            if len(value["time_finished"]) > 0
        ]
        modules.sort(key=lambda x: unserialise_datetime(x[1]["time_started"][0]))
        return [m[0] for m in modules]

    def start_module(self, label):
        modules = self.modules.copy()
        try:
            log = modules[label]
        except KeyError:
            log = {"time_started": [], "time_finished": []}
        time_now = serialise_datetime(datetime.datetime.now())
        log["time_started"] = log["time_started"] + [time_now]
        modules[label] = log.copy()
        self.modules = modules.copy()

    def end_module(self, label):
        modules = self.modules.copy()
        log = modules[label]
        time_now = serialise_datetime(datetime.datetime.now())
        log["time_finished"] = log["time_finished"] + [time_now]
        modules[label] = log.copy()
        self.modules = modules.copy()

    def set_answer(self, value):
        self.answer = value
        return self

    def initialise(self, experiment, client_ip_address: str):
        self.event_id = -1
        self.complete = False
        self.time_credit.initialise(experiment)
        self.performance_bonus = 0.0
        self.base_payment = experiment.base_payment
        self.client_ip_address = client_ip_address
        self.initialised = True

    def inc_performance_bonus(self, value):
        self.performance_bonus = self.performance_bonus + value

    def amount_paid(self):
        return (0.0 if self.base_payment is None else self.base_payment) + (
            0.0 if self.bonus is None else self.bonus
        )

    def set_participant_group(self, trial_maker_id: str, participant_group: str):
        from .trial.main import set_participant_group

        return set_participant_group(trial_maker_id, self, participant_group)

    def get_participant_group(self, trial_maker_id: str):
        from .trial.main import get_participant_group

        return get_participant_group(trial_maker_id, self)

    def has_participant_group(self, trial_maker_id: str):
        from .trial.main import has_participant_group

        return has_participant_group(trial_maker_id, self)

    def send_email_max_payment_reached(
        self, experiment_class, requested_bonus, reduced_bonus
    ):
        config = get_config()
        template = """Dear experimenter,

            This is an automated email from PsyNet. You are receiving this email because
            the total amount paid to the participant with assignment_id '{assignment_id}'
            has reached the maximum of {max_participant_payment}$. The bonus paid was {reduced_bonus}$
            instead of a requested bonus of {requested_bonus}$.

            The application id is: {app_id}

            To see the logs, use the command "dallinger logs --app {app_id}"
            To pause the app, use the command "dallinger hibernate --app {app_id}"
            To destroy the app, use the command "dallinger destroy --app {app_id}"

            The PsyNet developers.
            """
        message = {
            "subject": "Maximum experiment payment reached.",
            "body": template.format(
                assignment_id=self.assignment_id,
                max_participant_payment=experiment_class.max_participant_payment,
                requested_bonus=requested_bonus,
                reduced_bonus=reduced_bonus,
                app_id=config.get("id"),
            ),
        }
        logger.info(
            f"Recruitment ended. Maximum amount paid to participant "
            f"with assignment_id '{self.assignment_id}' reached!"
        )
        admin_notifier(config).send(**message)

    @property
    def response(self):
        return (
            Response.query.filter_by(participant_id=self.id)
            .order_by(desc(Response.id))
            .first()
        )

    @property
    @extra_var(__extra_vars__)
    def progress(self):
        return 1.0 if self.complete else self.time_credit.progress

    @property
    @extra_var(__extra_vars__)
    def estimated_bonus(self):
        return self.time_credit.estimate_bonus()

    @property
    def var(self):
        return VarStore(self)

    @property
    def time_credit(self):
        return TimeCreditStore(self)

    def append_branch_log(self, entry: str):
        # We need to create a new list otherwise the change may not be recognised
        # by SQLAlchemy(?)
        if (
            not isinstance(entry, list)
            or len(entry) != 2
            or not isinstance(entry[0], str)
        ):
            raise ValueError(
                f"Log entry must be a list of length 2 where the first element is a string (received {entry})."
            )
        if json.loads(json.dumps(entry)) != entry:
            raise ValueError(
                f"The provided log entry cannot be accurately serialised to JSON (received {entry}). "
                + "Please simplify the log entry (this is typically determined by the output type of the user-provided function "
                + "in switch() or conditional())."
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
        "experiment_max_bonus",
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
        self.experiment_max_time_credit = experiment_estimated_time_credit.get_max(
            mode="time"
        )
        self.experiment_max_bonus = experiment_estimated_time_credit.get_max(
            mode="bonus", wage_per_hour=experiment.wage_per_hour
        )

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
        if self.participant.initialised:
            return self.estimate_time_credit() / self.experiment_max_time_credit
        else:
            return 0.0
