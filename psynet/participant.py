# pylint: disable=attribute-defined-outside-init

import datetime
import json
from smtplib import SMTPAuthenticationError

import dallinger.models
from dallinger import db
from dallinger.config import get_config
from dallinger.notifications import admin_notifier
from sqlalchemy import desc

from . import field
from .data import SQLMixinDallinger
from .field import claim_var, extra_var
from .utils import get_logger, serialise_datetime, unserialise_datetime

logger = get_logger()

# pylint: disable=unused-import


class Participant(SQLMixinDallinger, dallinger.models.Participant):
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

    elt_id : list
        Represents the participant's position in the timeline.
        Should not be modified directly.
        The position is represented as a list, where the first element corresponds
        to the index of the participant within the timeline's underlying
        list representation, and successive elements (if any) represent
        the participant's position within (potentially nested) page makers.
        For example, ``[10, 3, 2]`` would mean go to
        element 10 in the timeline (0-indexing),
        which must be a page maker;
        go to element 3 within that page maker, which must also be a page maker;
        go to element 2 within that page maker.

    page_uuid : str
        A long unique string that is randomly generated when the participant advances
        to a new page, used as a passphrase to guarantee the security of
        data transmission from front-end to back-end.
        Should not be modified directly.

    complete : bool
        Whether the participant has successfully completed the experiment.
        A participant is considered to have successfully completed the experiment
        once they hit a :class:`~psynet.timeline.SuccessfulEndPage`.
        Should not be modified directly.

    aborted : bool
        Whether the participant has aborted the experiment.
        A participant is considered to have aborted the experiment
        once they have hit the "Abort experiment" button on the "Abort experiment" confirmation page.

    answer : object
        The most recent answer submitted by the participant.
        Can take any form that can be automatically serialized to JSON.
        Should not be modified directly.

    answer_accumulators: list
        This is an internal PsyNet variable that most users don't need to worry about.
        See below for implementation details:

        This list begins empty.
        Each time the participant enters a page maker with ``accumulate_answers = True``,
        an empty list is appended to ``answer_accumulators``.
        Whenever a new answer is generated, this answer is appended to the last list in ``answer_accumulators``.
        If the participant enters another page maker with ``accumulate_answers = True`` (i.e. nested page makers),
        then another empty list is appended to ``answer_accumulators``.
        Whenever the participant leaves a page maker with ``accumulate_answers = True``,
        the last list in ``answer_accumulators`` is removed and is placed in the ``answer`` variable.
        The net result is that all answers within a given page maker with ``accumulate_answers = True``
        end up being stored as a single list in the ``answer`` variable once the participant leaves
        the trial maker.

    response : Response
        An object of class :class:`~psynet.timeline.Response`
        providing detailed information about the last response submitted
        by the participant. This is a more detailed version of ``answer``.

    branch_log : list
        Stores the conditional branches that the participant has taken
        through the experiment.
        Should not be modified directly.

    failure_tags : list
        Stores tags that identify the reason that the participant has failed
        the experiment (if any). For example, if a participant fails
        a microphone pre-screening test, one might add "failed_mic_test"
        to this tag list.
        Should be modified using the method :meth:`~psynet.participant.Participant.append_failure_tags`.

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    progress : float [0 <= x <= 1]
        The participant's estimated progress through the experiment.

    auth_token : str
        The participant's randomly generated authentication token.

    client_ip_address : str
        The participant's IP address as reported by Flask.

    answer_is_fresh : bool
        ``True`` if the current value of ``participant.answer`` (and similarly ``participant.last_response_id`` and
        ``participant.last_response``) comes from the last page that the participant saw, ``False`` otherwise.

    browser_platform : str
        Information about the participant's browser version and OS platform.
    """

    # We set the polymorphic_identity manually to differentiate the class
    # from the Dallinger Participant class.
    polymorphic_identity = "PsyNetParticipant"
    __extra_vars__ = {}

    elt_id = field.claim_field("elt_id", __extra_vars__, list)
    page_uuid = field.claim_field("page_uuid", __extra_vars__, str)
    aborted = claim_var(
        "aborted", __extra_vars__, use_default=True, default=lambda: False
    )
    complete = field.claim_field("complete", __extra_vars__, bool)
    answer = field.claim_field("answer", __extra_vars__, object)
    answer_accumulators = field.claim_field("answer_accumulators", __extra_vars__, list)
    branch_log = field.claim_field("branch_log", __extra_vars__)

    failure_tags = claim_var(
        "failure_tags", __extra_vars__, use_default=True, default=lambda: []
    )
    last_response_id = claim_var(
        "last_response_id", __extra_vars__, use_default=True, default=lambda: None
    )
    base_payment = claim_var("base_payment", __extra_vars__)
    performance_bonus = claim_var("performance_bonus", __extra_vars__)
    unpaid_bonus = claim_var("unpaid_bonus", __extra_vars__)
    modules = claim_var("modules", __extra_vars__, use_default=True, default=lambda: {})
    client_ip_address = claim_var(
        "client_ip_address", __extra_vars__, use_default=True, default=lambda: ""
    )
    auth_token = claim_var("auth_token", __extra_vars__)
    answer_is_fresh = claim_var(
        "answer_is_fresh", __extra_vars__, use_default=True, default=lambda: False
    )
    browser_platform = claim_var(
        "browser_platform", __extra_vars__, use_default=True, default=lambda: ""
    )

    def __json__(self):
        x = SQLMixinDallinger.__json__(self)
        del x["modules"]
        return x

    def trials(self, failed=False, complete=True, is_repeat_trial=False):
        from .trial.main import Trial

        return Trial.query.filter_by(
            participant_id=self.id,
            failed=failed,
            complete=complete,
            is_repeat_trial=is_repeat_trial,
        ).all()

    @property
    def last_response(self):
        if self.last_response_id is None:
            return None
        from .timeline import Response

        return Response.query.filter_by(id=self.last_response_id).one()

    @property
    @extra_var(__extra_vars__)
    def aborted_modules(self):
        modules = [
            (key, value)
            for key, value in self.modules.items()
            if value.get("time_aborted") is not None
            and len(value.get("time_aborted")) > 0
        ]
        modules.sort(key=lambda x: unserialise_datetime(x[1]["time_started"][0]))
        return [m[0] for m in modules]

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

    @property
    @extra_var(__extra_vars__)
    def current_module(self):
        return None if not self.started_modules else self.started_modules[-1]

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

    def __init__(self, experiment, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.elt_id = [-1]
        self.answer_accumulators = []
        self.complete = False
        self.time_credit.initialize(experiment)
        self.performance_bonus = 0.0
        self.unpaid_bonus = 0.0
        self.base_payment = experiment.base_payment
        self.client_ip_address = None
        self.auth_token = None
        self.branch_log = []

        db.session.add(self)
        db.session.commit()

        experiment.timeline.advance_page(experiment, participant=self)

    def calculate_bonus(self):
        """
        Calculates and returns the currently accumulated bonus for the given participant.

        :returns:
            The bonus as a ``float``.
        """
        return round(
            self.time_credit.get_bonus() + self.performance_bonus,
            ndigits=2,
        )

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
                max_participant_payment=experiment_class.var.max_participant_payment,
                requested_bonus=requested_bonus,
                reduced_bonus=reduced_bonus,
                app_id=config.get("id"),
            ),
        }
        logger.info(
            f"Recruitment ended. Maximum amount paid to participant "
            f"with assignment_id '{self.assignment_id}' reached!"
        )
        try:
            admin_notifier(config).send(**message)
        except SMTPAuthenticationError as e:
            logger.error(
                f"SMTPAuthenticationError sending 'max_participant_payment' reached email: {e}"
            )
        except Exception as e:
            logger.error(
                f"Unknown error sending 'max_participant_payment' reached email: {e}"
            )

    @property
    def response(self):
        from .timeline import Response

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
    def time_credit(self):
        return TimeCreditStore(self)

    def append_branch_log(self, entry: str):
        # We need to create a new list otherwise the change may not be recognized
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

    def abort_info(self):
        """
            Information that will be shown to a participant if they click the abort button,
            e.g. in the case of an error where the participant is unable to finish the experiment.

        :returns: ``dict`` which may be rendered to the worker as an HTML table
            when they abort the experiment.
        """
        return {
            "assignment_id": self.assignment_id,
            "hit_id": self.hit_id,
            "accumulated_bonus": "$" + "{:.2f}".format(self.calculate_bonus()),
        }


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

    def initialize(self, experiment):
        self.confirmed_credit = 0.0
        self.is_fixed = False
        self.pending_credit = 0.0
        self.max_pending_credit = 0.0
        self.wage_per_hour = experiment.var.wage_per_hour

        experiment_estimated_time_credit = experiment.timeline.estimated_time_credit
        self.experiment_max_time_credit = experiment_estimated_time_credit.get_max(
            mode="time"
        )
        self.experiment_max_bonus = experiment_estimated_time_credit.get_max(
            mode="bonus", wage_per_hour=experiment.var.wage_per_hour
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
        return self.estimate_time_credit() / self.experiment_max_time_credit
