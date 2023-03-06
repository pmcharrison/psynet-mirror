# pylint: disable=attribute-defined-outside-init

import json
from smtplib import SMTPAuthenticationError

import dallinger.models
from dallinger import db
from dallinger.config import get_config
from dallinger.notifications import admin_notifier
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, desc, select
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import column_property, relationship
from sqlalchemy.orm.collections import attribute_mapped_collection

from .asset import AssetParticipant
from .data import SQLMixinDallinger
from .field import PythonList, PythonObject, VarStore, extra_var, register_extra_var
from .process import AsyncProcess
from .utils import get_logger, organize_by_key

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

    elt_bounds : list
        Represents the number of elements at each level of the current
        ``elt_id`` hierarchy; used to work out when to leave a page maker
        and go up to the next level.
        Should not be modified directly.

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

    elt_id = Column(PythonList)
    elt_id_max = Column(PythonList)
    page_uuid = Column(String)
    aborted = Column(Boolean, default=False)
    complete = Column(Boolean, default=False)
    answer = Column(PythonObject)
    answer_accumulators = Column(PythonList)
    branch_log = Column(PythonObject)
    for_loops = Column(PythonObject, default=lambda: {})
    failure_tags = Column(PythonList, default=lambda: [])

    # Ideally we wold make this a foreign key but this creates a circular dependency
    # when importing CSVs
    last_response_id = Column(Integer)

    base_payment = Column(Float)
    performance_bonus = Column(Float)
    unpaid_bonus = Column(Float)
    client_ip_address = Column(String, default=lambda: "")
    auth_token = Column(String)
    answer_is_fresh = Column(Boolean, default=False)
    browser_platform = Column(String, default="")
    module_state_id = Column(Integer, ForeignKey("module_state.id"))
    module_state = relationship(
        "ModuleState", foreign_keys=[module_state_id], post_update=True, lazy="joined"
    )
    current_trial_id = Column(Integer, ForeignKey("info.id"))
    current_trial = relationship(
        "psynet.trial.main.Trial", foreign_keys=[current_trial_id], lazy="joined"
    )
    trial_status = Column(String)

    # @property
    # def current_trial(self):
    #     if self.in_module and hasattr(self.module_state, "current_trial"):
    #         return self.module_state.current_trial
    #
    # @current_trial.setter
    # def current_trial(self, value):
    #     self.module_state.current_trial = value

    @property
    def last_response(self):
        from psynet.timeline import Response

        return Response.query.filter_by(id=self.last_response_id).one()

    # all_trials = relationship("psynet.trial.main.Trial")

    @property
    def alive_trials(self):
        return [t for t in self.all_trials if not t.failed]

    @property
    def failed_trials(self):
        return [t for t in self.all_trials if t.failed]

    # This would be better, but we end up with a circular import problem
    # if we try and read csv files using this foreign key...
    #
    # last_response = relationship(
    #     "psynet.timeline.Response", foreign_keys=[last_response_id]
    # )

    # current_trial_id = Column(
    #     Integer, ForeignKey("info.id")
    # )  # 'info.id' because trials are stored in the info table

    # This should work but it's buggy, don't know why.
    # current_trial = relationship(
    #     "psynet.trial.main.Trial",
    #     foreign_keys="[psynet.participant.Participant.current_trial_id]",
    # )
    #
    # Instead we resort to the below...

    # @property
    # def current_trial(self):
    #     from dallinger.models import Info
    #
    #     # from .trial.main import Trial
    #
    #     if self.current_trial_id is None:
    #         return None
    #     else:
    #         # We should just be able to use Trial for the query, but using Info seems
    #         # to avoid an annoying SQLAlchemy bug that comes when we run multiple demos
    #         # in one session. When this happens, what we see is that Trial.query.all()
    #         # sees all trials appropriately, but Trial.query.filter_by(id=1).all() fails.
    #         #
    #         # return Trial.query.filter_by(id=self.current_trial_id).one()
    #         return Info.query.filter_by(id=self.current_trial_id).one()
    #
    # @current_trial.setter
    # def current_trial(self, trial):
    #     from psynet.trial.main import Trial
    #     self.current_trial_id = trial.id if isinstance(trial, Trial) else None

    awaiting_async_process = column_property(
        select(AsyncProcess.participant_id, AsyncProcess.pending)
        .where(
            AsyncProcess.participant_id == dallinger.models.Participant.id,
            AsyncProcess.pending,
        )
        .exists()
    )
    register_extra_var(__extra_vars__, "awaiting_async_process")

    asset_links = relationship(
        "AssetParticipant",
        collection_class=attribute_mapped_collection("label"),
        cascade="all, delete-orphan",
    )

    assets = association_proxy(
        "asset_links", "asset", creator=lambda k, v: AssetParticipant(label=k, asset=v)
    )

    errors = relationship("ErrorRecord")
    # _module_states = relationship("ModuleState", foreign_keys=[dallinger.models.Participant.id], lazy="selectin")

    @property
    def module_states(self):
        return organize_by_key(
            self._module_states,
            key=lambda x: x.module_id,
            sort_key=lambda x: x.time_started,
        )

    def select_module(self, module_id: str):
        candidates = [
            state
            for state in self._module_states
            if not state.finished and state.module_id == module_id
        ]
        assert len(candidates) == 1
        self.module_state = candidates[0]

    @property
    def var(self):
        return self.globals

    @property
    def globals(self):
        return VarStore(self)

    @property
    def locals(self):
        return self.module_state.var

    def to_dict(self):
        x = SQLMixinDallinger.to_dict(self)
        x.update(self.locals_to_dict())
        return x

    def locals_to_dict(self):
        output = {}
        for module_id, module_states in self.module_states.items():
            module_states.sort(key=lambda x: x.time_started)
            for i, module_state in enumerate(module_states):
                if i == 0:
                    prefix = f"{module_id}__"
                else:
                    prefix = f"{module_id}__{i}__"
                for key, value in module_state.var.items():
                    output[prefix + key] = value
        return output

    @property
    @extra_var(__extra_vars__)
    def aborted_modules(self):
        return [
            log.module_id
            for log in sorted(self._module_states, key=lambda x: x.time_started)
            if log.aborted
        ]

    @property
    @extra_var(__extra_vars__)
    def started_modules(self):
        return [
            log.module_id
            for log in sorted(self._module_states, key=lambda x: x.time_started)
            if log.started
        ]

    @property
    @extra_var(__extra_vars__)
    def finished_modules(self):
        return [
            log.module_id
            for log in sorted(self._module_states, key=lambda x: x.time_started)
            if log.finished
        ]

    def refresh_module_state(self):
        if len(self._module_states) == 0:
            self.module_state = None
        else:
            unfinished = [x for x in self._module_states if not x.finished]
            unfinished.sort(key=lambda x: x.time_started)
            if len(unfinished) == 0:
                self.module_state = None
            else:
                self.module_state = unfinished[-1]

    @property
    def in_module(self):
        return self.module_state is not None

    @property
    @extra_var(__extra_vars__)
    def module_id(self):
        if self.module_state:
            return self.module_state.module_id

    def set_answer(self, value):
        self.answer = value
        return self

    def __init__(self, experiment, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vars = {}
        self.elt_id = [-1]
        self.elt_id_max = [len(experiment.timeline) - 1]
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

        self.initialize(
            experiment
        )  # Hook for custom subclasses to provide further initialization
        db.session.commit()

    def initialize(self, experiment):
        pass

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

    def get_locale(self, experiment):
        if self.var.has("locale"):
            return self.var.locale
        else:
            locale = experiment.var.current_locale
            self.var.set("locale", locale)
            logger.warning(
                f"Participant {self.id} locale was not set, setting to default locale of the experiment: {locale}"
            )
            return locale

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
