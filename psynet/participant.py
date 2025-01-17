# pylint: disable=attribute-defined-outside-init

import json
from smtplib import SMTPAuthenticationError
from typing import TYPE_CHECKING, Dict

import dallinger.models
from dallinger import db
from dallinger.notifications import admin_notifier
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    desc,
)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import attribute_mapped_collection

from .asset import AssetParticipant
from .data import SQLMixinDallinger
from .field import PythonList, PythonObject, VarStore, extra_var
from .utils import call_function_with_context, get_config, get_logger, organize_by_key

logger = get_logger()

if TYPE_CHECKING:
    from .sync import SyncGroup
    from .timeline import Module

# pylint: disable=unused-import

UniqueConstraint(dallinger.models.Participant.worker_id)
UniqueConstraint(dallinger.models.Participant.unique_id)


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

    client_ip_address : str
        The participant's IP address as reported by Flask.

    answer_is_fresh : bool
        ``True`` if the current value of ``participant.answer`` (and similarly ``participant.last_response_id`` and
        ``participant.last_response``) comes from the last page that the participant saw, ``False`` otherwise.

    browser_platform : str
        Information about the participant's browser version and OS platform.

    all_trials : list
        A list of all trials for that participant.

    alive_trials : list
        A list of all non-failed trials for that participant.

    failed_trials : list
        A list of all failed trials for that participant.
    """

    # We set the polymorphic_identity manually to differentiate the class
    # from the Dallinger Participant class.
    __extra_vars__ = {}

    elt_id = Column(PythonList)
    elt_id_max = Column(PythonList)

    time_credit = Column(Float)
    estimated_max_time_credit = Column(Float)
    progress = Column(Float)

    # If time_credit_fixes is non-empty, then the last element of time_credit_fixes
    # is used as the currently active time credit 'fix'. While this fix is active,
    # the participant's time credit will not be allowed to increase above this number.
    # Once the fix expires, the participant's time credit will be set to that number exactly.
    # See ``psynet.timeline.with_fixed_time_credit`` for an explanation.
    time_credit_fixes = Column(PythonList)
    # progress_fixes is analogous to time_credit_fixes, but for progress.
    progress_fixes = Column(PythonList)

    page_uuid = Column(String)
    aborted = Column(Boolean, default=False)
    complete = Column(Boolean, default=False)
    answer = Column(PythonObject)
    answer_accumulators = Column(PythonList)
    sequences = Column(PythonList)
    branch_log = Column(PythonObject)
    for_loops = Column(PythonObject, default=lambda: {})
    failure_tags = Column(PythonList, default=lambda: [])

    base_payment = Column(Float)
    performance_reward = Column(Float)
    unpaid_bonus = Column(Float)
    total_wait_page_time = Column(Float)
    client_ip_address = Column(String, default=lambda: "")
    answer_is_fresh = Column(Boolean, default=False)
    browser_platform = Column(String, default="")
    module_state_id = Column(Integer, ForeignKey("module_state.id"))
    module_state = relationship(
        "ModuleState", foreign_keys=[module_state_id], post_update=True, lazy="selectin"
    )
    current_trial_id = Column(Integer, ForeignKey("info.id"))
    current_trial = relationship(
        "psynet.trial.main.Trial", foreign_keys=[current_trial_id], lazy="joined"
    )
    trial_status = Column(String)

    all_responses = relationship("psynet.timeline.Response")

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
        return self.response

    # all_trials = relationship("psynet.trial.main.Trial")

    @property
    def alive_trials(self):
        return [t for t in self.all_trials if not t.failed]

    @property
    def failed_trials(self):
        return [t for t in self.all_trials if t.failed]

    @property
    def trials(self):
        raise RuntimeError(
            "The .trials attribute has been removed, please use .all_trials, .alive_trials, or .failed_trials instead."
        )

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

    asset_links = relationship(
        "AssetParticipant",
        collection_class=attribute_mapped_collection("local_key"),
        cascade="all, delete-orphan",
    )

    assets = association_proxy(
        "asset_links",
        "asset",
        creator=lambda k, v: AssetParticipant(local_key=k, asset=v),
    )

    # sync_group_links and sync_groups are defined in sync.py
    # because of import-order necessities

    # sync_groups is a relationship that gives a list of all SyncGroups for that participnat

    @property
    def active_sync_groups(self) -> Dict[str, "SyncGroup"]:
        return {group.group_type: group for group in self.sync_groups if group.active}

    @property
    def sync_group(self) -> "SyncGroup":
        candidates = self.active_sync_groups
        if len(candidates) == 1:
            return list(candidates.values())[0]
        elif len(candidates) == 0:
            return None
        elif len(candidates) > 1:
            raise RuntimeError(
                f"Participant {self.id} is in more than one SyncGroup: "
                f"{list(self.active_sync_groups)}. "
                "Use participant.active_sync_groups[group_type] to access the SyncGroup you need."
            )

    active_barriers = relationship(
        "ParticipantLinkBarrier",
        collection_class=attribute_mapped_collection("barrier_id"),
        cascade="all, delete-orphan",
        primaryjoin=(
            "and_(psynet.participant.Participant.id==remote(ParticipantLinkBarrier.participant_id), "
            "ParticipantLinkBarrier.released==False)"
        ),
        lazy="selectin",
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

    def start_module(self, module: "Module"):
        self.check_module_not_already_started(module)
        state = module.state_class(module, self)
        state.start()
        self.module_state = state

    def check_module_not_already_started(self, module: "Module"):
        if module.id not in self.module_states:
            return
        else:
            states = self.module_states[module.id]
            for state in states:
                if not state.finished:
                    raise RuntimeError(
                        f"Participant already has an unfinished module state for '{module.id}'..."
                    )

    def end_module(self, module):
        # This should only fail (delivering multiple logs) if the experimenter has perversely
        # defined a recursive module (or is reusing module ID)
        state = [
            _state for _state in self.module_states[module.id] if not _state.finished
        ]

        if len(state) == 0:
            raise RuntimeError(
                f"Participant had no unfinished module states with id = '{module.id}'."
            )
        elif len(state) > 1:
            raise RuntimeError(
                (
                    f"Participant had multiple unfinished module states with id = '{module.id}': "
                    f"{[s.__json__() for s in state]}, participant: {self.__json__()}"
                )
            )

        state = state[0]
        state.finish()
        self.refresh_module_state()

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
        self.time_credit = 0.0
        self.estimated_max_time_credit = (
            experiment.timeline.estimated_time_credit.get_max("time")
        )
        self.progress = 0.0
        self.time_credit_fixes = []
        self.progress_fixes = []
        self.elt_id = [-1]
        self.elt_id_max = [len(experiment.timeline) - 1]
        self.answer_accumulators = []
        self.sequences = []
        self.complete = False
        self.performance_reward = 0.0
        self.unpaid_bonus = 0.0
        self.base_payment = experiment.base_payment
        self.client_ip_address = None
        self.branch_log = []
        self.total_wait_page_time = 0.0

        db.session.add(self)

        self.initialize(
            experiment
        )  # Hook for custom subclasses to provide further initialization

    def initialize(self, experiment):
        pass

    @property
    def locale(self):
        return self.var.get("locale", default=None)

    @property
    def failure_cascade(self):
        return [lambda: self.alive_trials]

    @property
    def gettext(self):
        return self.translator[0]

    @property
    def pgettext(self):
        return self.translator[1]

    @property
    def time_reward(self):
        wage_per_hour = get_config().get("wage_per_hour")
        seconds = self.time_credit
        hours = seconds / 3600
        return hours * wage_per_hour

    def calculate_reward(self):
        """
        Calculates and returns the currently accumulated reward for the given participant.

        :returns:
            The reward as a ``float``.
        """
        return round(
            self.time_reward + self.performance_reward,
            ndigits=2,
        )

    def inc_time_credit(self, time_credit: float):
        new_value = self.time_credit + time_credit
        new_value = min([new_value, *self.time_credit_fixes])
        self.time_credit = new_value

    def inc_progress(self, time_credit: float):
        if self.estimated_max_time_credit == 0.0:
            new_value = 1.0
        else:
            new_value = self.progress + time_credit / self.estimated_max_time_credit
            new_value = min([new_value, *self.progress_fixes])
        self.progress = new_value

    def inc_performance_reward(self, value):
        self.performance_reward += value

    def amount_paid(self):
        return (0.0 if self.base_payment is None else self.base_payment) + (
            0.0 if self.bonus is None else self.bonus
        )

    def send_email_max_payment_reached(
        self, experiment_class, requested_reward, reduced_reward
    ):
        config = get_config()
        template = """Dear experimenter,

            This is an automated email from PsyNet. You are receiving this email because
            the total amount paid to the participant with assignment_id '{assignment_id}'
            has reached the maximum of {max_participant_payment}$. The reward paid was {reduced_reward}$
            instead of a requested reward of {requested_reward}$.

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
                requested_reward=requested_reward,
                reduced_reward=reduced_reward,
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
            "accumulated_reward": "$" + "{:.2f}".format(self.calculate_reward()),
        }

    def fail(self, reason=None):
        if self.failed:
            logger.info("Participant %i already failed, not failing again.", self.id)
            return

        if reason is not None:
            self.append_failure_tags(reason)
        reason = ", ".join(self.failure_tags)

        logger.info(
            "Failing participant %i (reason: %s)",
            self.id,
            reason,
        )

        from psynet.experiment import get_experiment

        exp = get_experiment()

        for i, routine in enumerate(exp.participant_fail_routines):
            logger.info(
                "Executing fail routine %i/%i ('%s')...",
                i + 1,
                len(exp.participant_fail_routines),
                routine.label,
            )
            call_function_with_context(
                routine.function,
                participant=self,
                experiment=self,
            )

        super().fail(reason=reason)
        for group in self.active_sync_groups.values():
            from .sync import SimpleSyncGroup

            if isinstance(group, SimpleSyncGroup):
                group.check_numbers()


def get_participant(participant_id: int, for_update: bool = False) -> Participant:
    """
    Returns the participant with a given ID.
    Warning: we recommend just using SQLAlchemy directly instead of using this function.
    When doing so, use ``with_for_update().populate_existing()`` if you plan to update
    this Participant object, that way the database row will be locked appropriately.

    Parameters
    ----------

    participant_id
        ID of the participant to get.

    for_update
        Set to ``True`` if you plan to update this Participant object.
        The Participant object will be locked for update in the database
        and only released at the end of the transaction.

    Returns
    -------

    :class:`psynet.participant.Participant`
        The requested participant.
    """
    query = Participant.query.filter_by(id=participant_id)
    if for_update:
        query = query.with_for_update(of=Participant).populate_existing()
    return query.one()
