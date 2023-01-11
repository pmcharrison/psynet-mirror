# pylint: disable=unused-argument

import datetime
import random
from math import isnan
from typing import Optional, Union
from uuid import uuid4

import dallinger.experiment
import dallinger.models
import dallinger.nodes
from dallinger import db
from dallinger.db import redis_conn
from dallinger.models import Info, Network, Node
from dominate import tags
from flask import Markup
from rq import Queue
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

from ..data import SQLMixinDallinger
from ..field import (
    UndefinedVariableError,
    VarStore,
    claim_field,
    extra_var,
    register_extra_var,
)
from ..page import InfoPage, UnsuccessfulEndPage, wait_while
from ..participant import Participant
from ..timeline import (
    CodeBlock,
    DatabaseCheck,
    ExperimentSetupRoutine,
    Module,
    PageMaker,
    ParticipantFailRoutine,
    RecruitmentCriterion,
    Response,
    conditional,
    join,
    switch,
    while_loop,
)
from ..utils import (
    call_function,
    corr,
    get_logger,
    import_local_experiment,
    serialise_datetime,
    unserialise_datetime,
)

logger = get_logger()


def with_trial_maker_namespace(trial_maker_id: str, x: Optional[str] = None):
    if x is None:
        return trial_maker_id
    return f"{trial_maker_id}__{x}"


def set_participant_group(trial_maker_id, participant, participant_group):
    participant.var.new(
        with_trial_maker_namespace(trial_maker_id, "participant_group"),
        participant_group,
    )


def get_participant_group(trial_maker_id, participant):
    return participant.var.get(
        with_trial_maker_namespace(trial_maker_id, "participant_group")
    )


def has_participant_group(trial_maker_id, participant):
    return participant.var.has(
        with_trial_maker_namespace(trial_maker_id, "participant_group")
    )


class HasDefinition:
    # Mixin class that provides a 'definition' slot.
    # See https://docs.sqlalchemy.org/en/14/orm/inheritance.html#resolving-column-conflicts
    @declared_attr
    def definition(cls):
        return cls.__table__.c.get(
            "definition", Column(JSONB, server_default="{}", default=lambda: {})
        )

    __extra_vars__ = {}
    register_extra_var(__extra_vars__, "definition", field_type=dict)


class AsyncProcessOwner:
    __extra_vars__ = {}

    awaiting_async_process = claim_field("awaiting_async_process", __extra_vars__, bool)
    pending_async_processes = claim_field("pending_async_processes", __extra_vars__)
    failed_async_processes = claim_field("failed_async_processes", __extra_vars__)

    def __init__(self):
        self.awaiting_async_process = False
        self.pending_async_processes = {}
        self.failed_async_processes = {}

    @property
    def earliest_async_process_start_time(self):
        return min(
            [
                unserialise_datetime(x["start_time"])
                for x in self.pending_async_processes.values()
            ]
        )

    def queue_async_method(self, method_name: str, *args, **kwargs):
        """
        Queues an object's method to be run asynchronously in a worker process.
        This is useful for scheduling long-running processes without blocking
        the main server thread.

        Parameters
        ----------

        method_name:
            The name of the method to call. Typically this method will have been
            custom-implemented for the particular experiment.
            For example, suppose we have implemented a method called ``do_heavy_computation``.
            We would ordinarily call this synchronously as follows: ``obj.do_heavy_computation()``.
            To call this method asynchronously, we write ``method_name="do_heavy_computation"``.
            The outputs of this heavy computation typically need to be saved somehow in the database;
            for example, within the ``do_heavy_computation`` function one might write
            ``self.var.computation_output = result``.

        args, kwargs:
            Optional arguments which will be pickled under-the-hood using ``pickle.dumps``.
            Be careful passing complex objects here (e.g. SQLAlchemy objects),
            as they might not be serialized properly. Better instead to pass object IDs
            and recreate the SQLAlchemy objects within the asynchronous function.

        Returns
        -------

        ``None``, as the asynchronous function call is non-blocking.

        """
        process_id = str(uuid4())
        self.push_async_process(process_id)
        db.session.commit()
        q = Queue("default", connection=redis_conn)
        q.enqueue_call(
            func=self._run_async_method,
            args=tuple(args),
            kwargs=dict(
                object_id=self.id,
                process_id=process_id,
                method_name=method_name,
                **kwargs,
            ),
            timeout=1e10,  # PsyNet deals with timeouts itself (it's useful to log them in the database)
        )  # pylint: disable=no-member

    @classmethod
    def _run_async_method(cls, object_id, process_id, method_name, *args, **kwargs):
        import_local_experiment()
        obj = cls.query.filter_by(id=object_id).one()
        try:
            if process_id in obj.pending_async_processes:
                method = getattr(obj, method_name)
                method(*args, **kwargs)
                obj.pop_async_process(process_id)
            else:
                logger.info(
                    "Skipping async method %s (%s) as it is no longer queued.",
                    method_name,
                    process_id,
                )
        except BaseException:
            obj.fail_async_processes(
                reason=f"exception in async method '{method_name}'"
            )
            raise
        finally:
            db.session.commit()  # pylint: disable=no-member

    def push_async_process(self, process_id):
        pending_processes = self.pending_async_processes.copy()
        pending_processes[process_id] = {
            "start_time": serialise_datetime(datetime.datetime.now())
        }
        self.pending_async_processes = pending_processes
        self.awaiting_async_process = True

    def pop_async_process(self, process_id):
        pending_processes = self.pending_async_processes.copy()
        if process_id not in pending_processes:
            raise ValueError(
                f"process_id {process_id} not found in pending async processes"
                + f" for {self.__class__.__name__} {self.id}."
            )
        del pending_processes[process_id]
        self.pending_async_processes = pending_processes
        self.awaiting_async_process = len(pending_processes) > 0

    def fail_async_processes(self, reason):
        pending_processes = self.pending_async_processes
        for process_id, _ in pending_processes.items():
            self.register_failed_process(process_id, reason)
            self.pop_async_process(process_id)

    def register_failed_process(self, process_id, reason):
        failed_async_processes = self.failed_async_processes.copy()
        failed_async_processes[process_id] = {
            "time": serialise_datetime(datetime.datetime.now()),
            "reason": reason,
        }
        self.failed_async_processes = failed_async_processes


class Trial(SQLMixinDallinger, Info, AsyncProcessOwner, HasDefinition):
    """
    Represents a trial in the experiment.
    The user is expected to override the following methods:

    * :meth:`~psynet.trial.main.Trial.make_definition`,
      responsible for deciding on the content of the trial.
    * :meth:`~psynet.trial.main.Trial.show_trial`,
      determines how the trial is turned into a webpage for presentation to the participant.
    * :meth:`~psynet.trial.main.Trial.show_feedback`,
      defines an optional feedback page to be displayed after the trial.

    The user must also override the ``time_estimate`` class attribute,
    providing the estimated duration of the trial in seconds.
    This is used for predicting the participant's bonus payment
    and for constructing the progress bar.

    The user may also wish to override the
    :meth:`~psynet.trial.main.Trial.async_post_trial` method
    if they wish to implement asynchronous trial processing.

    They may also override the
    :meth:`~psynet.trial.main.Trial.score_answer` method
    if they wish to implement trial-level scoring;
    for scoring methods that work by analyzing multiple trials at the same time
    (e.g., test-retest correlations), see the trial maker method
    :meth:`~psynet.trial.main.TrialMaker.performance_check`.

    This class subclasses the :class:`~dallinger.models.Info` class from Dallinger,
    hence can be found in the ``Info`` table in the database.
    It inherits this class's methods, which the user is welcome to use
    if they seem relevant.

    Instances can be retrieved using *SQLAlchemy*; for example, the
    following command retrieves the ``Trial`` object with an ID of 1:

    ::

        Trial.query.filter_by(id=1).one()

    Parameters
    ----------

    experiment:
        An instantiation of :class:`psynet.experiment.Experiment`,
        corresponding to the current experiment.

    node:
        An object of class :class:`dallinger.models.Node` to which the
        :class:`~dallinger.models.Trial` object should be attached.
        Complex experiments are often organised around networks of nodes,
        but in the simplest case one could just make one :class:`~dallinger.models.Network`
        for each type of trial and one :class:`~dallinger.models.Node` for each participant,
        and then assign the :class:`~dallinger.models.Trial`
        to this :class:`~dallinger.models.Node`.
        Ask us if you want to use this simple use case - it would be worth adding
        it as a default to this implementation, but we haven't done that yet,
        because most people are using more complex designs.

    participant:
        An instantiation of :class:`psynet.participant.Participant`,
        corresponding to the current participant.

    propagate_failure : bool
        Whether failure of a trial should be propagated to other
        parts of the experiment depending on that trial
        (for example, subsequent parts of a transmission chain).

    Attributes
    ----------

    time_estimate : numeric
        The estimated duration of the trial (including any feedback), in seconds.
        This should generally correspond to the (sum of the) ``time_estimate`` parameters in
        the page(s) generated by ``show_trial``, plus the ``time_estimate`` parameter in
        the page generated by ``show_feedback`` (if defined).
        This is used for predicting the participant's bonus payment
        and for constructing the progress bar.

    participant_id : int
        The ID of the associated participant.
        The user should not typically change this directly.
        Stored in ``property1`` in the database.

    node
        The :class:`dallinger.models.Node` to which the :class:`~dallinger.models.Trial`
        belongs.

    complete : bool
        Whether the trial has been completed (i.e. received a response
        from the participant). The user should not typically change this directly.

    finalized : bool
        Whether the trial has been finalized. This is a stronger condition than ``complete``;
        in particular, a trial is only marked as finalized once its async processes
        have completed (if it has any).
        One day we might extend this to include arbitrary conditions,
        for example waiting for another user to evaluate that trial, or similar.

    answer : Object
        The response returned by the participant. This is serialised
        to JSON, so it shouldn't be too big.
        The user should not typically change this directly.
        Stored in ``details`` in the database.

    parent_trial_id : int
        If the trial is a repeat trial, this attribute corresponds to the ID
        of the trial from which that repeat trial was cloned.

    awaiting_async_process : bool
        Whether the trial is waiting for some asynchronous process
        to complete (e.g. to synthesise audiovisual material).

    earliest_async_process_start_time : Optional[datetime]
        Time at which the earliest pending async process was called.

    propagate_failure : bool
        Whether failure of a trial should be propagated to other
        parts of the experiment depending on that trial
        (for example, subsequent parts of a transmission chain).

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    definition : Object
        An arbitrary Python object that somehow defines the content of
        a trial. Often this will be a dictionary comprising a few
        named parameters.
        The user should not typically change this directly,
        as it is instead determined by
        :meth:`~psynet.trial.main.Trial.make_definition`.

    run_async_post_trial : bool
        Set this to ``True`` if you want the :meth:`~psynet.trial.main.Trial.async_post_trial`
        method to run after the user responds to the trial.

    wait_for_feedback : bool
        Set this class attribute to ``False`` if you don't want to wait for asynchronous processes
        to complete before giving feedback. The default is to wait.

    accumulate_answers : bool
        Set this class attribute to ``True`` if the trial contains multiple pages and you want
        the answers to all of these pages to be stored as a list in ``participant.answer``.
        Otherwise, the default behaviour is to only store the answer from the final page.

    time_credit_before_trial: float
        Reports the amount of time credit that the participant had before they started the trial (in seconds).

    time_credit_after_trial: float
        Reports the amount of time credit that the participant had after they finished the trial (in seconds).

    time_credit_from_trial: float
        Reports the amount of time credit that was allocated to the participant on the basis of this trial (in seconds).
        This should be equal to ``time_credit_after_trial - time_credit_before_trial``.

    check_time_credit_received : bool
        If ``True`` (default), PsyNet will check at the end of the trial whether the participant received
        the expected amount of time credit. If the received amount is inconsistent with the amount
        specified by ``time_estimate``, then a warning message will be delivered,
        suggesting a revised value for ``time_estimate``.

    response_id : int
        ID of the associated :class:`~psynet.timeline.Response` object.
        Equals ``None`` if no such object has been created yet.

    response :
        The associated :class:`~psynet.timeline.Response` object,
        which records in detail the response received from the participant's web browser.
        Equals ``None`` if no such object has been created yet.
    """

    # pylint: disable=unused-argument
    __extra_vars__ = {
        **SQLMixinDallinger.__extra_vars__.copy(),
        **AsyncProcessOwner.__extra_vars__.copy(),
        **HasDefinition.__extra_vars__.copy(),
    }

    # Properties ###
    participant_id = claim_field("participant_id", __extra_vars__, int)
    complete = claim_field("complete", __extra_vars__, bool)
    finalized = claim_field("finalized", __extra_vars__, bool)
    is_repeat_trial = claim_field("is_repeat_trial", __extra_vars__, bool)
    score = claim_field("score", __extra_vars__, float)
    bonus = claim_field("bonus", __extra_vars__, float)
    parent_trial_id = claim_field("parent_trial_id", __extra_vars__, int)
    answer = claim_field("answer", __extra_vars__)
    propagate_failure = claim_field("propagate_failure", __extra_vars__, bool)
    response_id = claim_field("response_id", __extra_vars__, int)
    repeat_trial_index = claim_field("repeat_trial_index", __extra_vars__, int)
    num_repeat_trials = claim_field("num_repeat_trials", __extra_vars__, int)
    time_taken = claim_field("time_taken", __extra_vars__, float)

    time_credit_before_trial = claim_field(
        "time_credit_before_trial", __extra_vars__, float
    )
    time_credit_after_trial = claim_field(
        "time_credit_after_trial", __extra_vars__, float
    )
    time_credit_from_trial = claim_field(
        "time_credit_from_trial", __extra_vars__, float
    )

    # It is compulsory to override this time_estimate parameter for the specific experiment implementation.
    time_estimate = None

    check_time_credit_received = True

    wait_for_feedback = True  # determines whether feedback waits for async_post_trial
    accumulate_answers = False

    @property
    def parent_trial(self):
        assert self.parent_trial_id is not None
        return Trial.query.filter_by(id=self.parent_trial_id).one()

    @property
    def response(self):
        if self.response_id is None:
            return None
        return Response.query.filter_by(id=self.response_id).one()

    # VarStore occupies the <details> slot.
    @property
    def var(self):
        return VarStore(self)

    @property
    def participant(self):
        return Participant.query.filter_by(id=self.participant_id).one()

    @property
    def position(self):
        """
        Returns the position of the current trial within that participant's current trial maker (0-indexed).
        This can be used, for example, to display how many trials the participant has taken so far.
        """
        trials = self.get_for_participant(
            self.participant_id, self.network.trial_maker_id
        )
        trial_ids = [t.id for t in trials]
        return trial_ids.index(self.id)

    @classmethod
    def get_for_participant(cls, participant_id: int, trial_maker_id: int = None):
        """
        Returns all trials for a given participant.
        """
        query = (
            db.session.query(cls)
            .join(TrialNetwork)
            .filter(Trial.participant_id == participant_id)
        )
        if trial_maker_id is not None:
            query = query.filter(TrialNetwork.trial_maker_id == trial_maker_id)
        return query.order_by(Trial.id).all()

    @property
    def visualization_html(self):
        experiment = dallinger.experiment.load()
        participant = self.participant
        page = self.show_trial(experiment=experiment, participant=participant)
        return page.visualize(trial=self)

    def fail(self, reason=None):
        """
        Marks a trial as failed. Failing a trial means that it is somehow
        excluded from certain parts of the experiment logic, for example
        not counting towards data collection quotas, or not contributing
        towards latter parts of a transmission chain.

        The original fail function from the
        :class:`~dallinger.models.Info` class
        throws an error if the object is already failed,
        but this behaviour is disabled here.

        If a `reason` argument is passed, this will be stored in
        :attr:`~dallinger.models.SharedMixin.failed_reason`.
        """

        if not self.failed:
            self.failed = True
            self.failed_reason = reason
            self.time_of_death = datetime.datetime.now()

    @property
    def ready_for_feedback(self):
        """
        Determines whether a trial is ready to give feedback to the participant.
        """
        return self.complete and (
            (not self.wait_for_feedback) or (not self.awaiting_async_process)
        )

    @property
    @extra_var(__extra_vars__)
    def trial_maker_id(self):
        return self.network.trial_maker_id

    #################

    def __init__(
        self,
        experiment,
        node,
        participant,
        propagate_failure,  # If the trial fails, should its failure be propagated to its descendants?
        is_repeat_trial,  # Is the trial a repeat trial?
        parent_trial=None,  # If the trial is a repeat trial, what is its parent?
        repeat_trial_index=None,  # Only relevant if the trial is a repeat trial
        num_repeat_trials=None,  # Only relevant if the trial is a repeat trial
    ):
        super().__init__(origin=node)
        AsyncProcessOwner.__init__(self)
        self.complete = False
        self.finalized = False
        self.awaiting_async_process = False
        self.participant_id = participant.id
        self.propagate_failure = propagate_failure
        self.is_repeat_trial = is_repeat_trial
        self.parent_trial_id = None if parent_trial is None else parent_trial.id
        self.repeat_trial_index = repeat_trial_index
        self.num_repeat_trials = num_repeat_trials
        self.score = None
        self.response_id = None
        self.time_taken = None

        if is_repeat_trial:
            self.definition = parent_trial.definition
        else:
            self.definition = self.make_definition(experiment, participant)

    def mark_as_finalized(self):
        """
        Marks a trial as finalized. This means that all relevant data has been stored from the
        participant's response, and any pending asynchronous processes have completed.
        """
        if self.finalized:
            raise RuntimeError(
                f"Tried to mark trial {self.id} as finalized, but it was already finalized."
            )
        self.finalized = True
        self._on_finalized()

    def _on_finalized(self):
        self.score = self.score_answer(answer=self.answer, definition=self.definition)
        self._allocate_bonus()

    def _allocate_bonus(self):
        bonus = self.compute_bonus(score=self.score)
        assert isinstance(bonus, (float, int))
        self._log_bonus(bonus)
        self.bonus = bonus
        self.participant.inc_performance_bonus(bonus)

    def _log_bonus(self, bonus):
        logger.info(
            "Allocating a performance bonus of $%.2f to participant %i for trial %i.",
            bonus,
            self.participant.id,
            self.id,
        )

    def score_answer(self, answer, definition):
        """
        Scores the participant's answer. At the point that this method is called,
        any pending asynchronous processes should already have been completed.

        Parameters
        ----------
        answer :
            The answer provided to the trial.

        definition :
            The trial's definition

        Returns
        -------

        A numeric score quantifying the participant's success.
        The experimenter is free to decide the directionality
        (whether high scores are better than low scores, or vice versa).
        Alternatively, ``None`` indicating no score.
        """
        return None

    def compute_bonus(self, score):
        """
        Computes a bonus to allocate to the participant as a reward for the current trial.
        By default, no bonus is given.
        Note: this trial-level bonus system is complementary to the trial-maker-level bonus system,
        which computes an overall bonus for the participant at the end of a trial maker.
        It is possible to use these two bonus systems independently or simultaneously.
        See :meth:`~psynet.trial.main.TrialMaker.compute_bonus` for more details.

        Parameters
        ----------

        score:
            The score achieved by the participant, as computed by :meth:`~psynet.trial.main.Trial.score_answer`.

        Returns
        -------

        The resulting bonus, typically in dollars.
        """
        return 0.0

    def json_data(self):
        x = super().json_data()
        x["participant_id"] = self.participant_id
        return x

    def make_definition(self, experiment, participant):
        """
        Creates and returns a definition for the trial,
        which will be later stored in the ``definition`` attribute.
        This can be an arbitrary object as long as it
        is serialisable to JSON.

        Parameters
        ----------

        experiment:
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant:
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """
        raise NotImplementedError

    def show_trial(self, experiment, participant):
        """
        Returns a :class:`~psynet.timeline.Page` object,
        or alternatively a list of such objects,
        that solicits an answer from the participant.

        Parameters
        ----------

        experiment:
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant:
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """
        raise NotImplementedError

    def show_feedback(self, experiment, participant):
        """
        Returns a Page object displaying feedback
        (or None, which means no feedback).

        Parameters
        ----------

        experiment:
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant:
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """
        return None

    def gives_feedback(self, experiment, participant):
        return (
            self.show_feedback(experiment=experiment, participant=participant)
            is not None
        )

    run_async_post_trial = False

    def async_post_trial(self):
        """
        Optional function to be run after a trial is completed by the participant.
        Will only run if :attr:`~psynet.trial.main.Trial.run_async_post_trial`
        is set to ``True``.
        """
        raise NotImplementedError

    def call_async_post_trial(self):
        experiment = dallinger.experiment.load()
        trial_maker = experiment.timeline.get_trial_maker(self.trial_maker_id)
        self.async_post_trial()
        self.mark_as_finalized()
        trial_maker._grow_network(self.network, self.participant, experiment)

    def fail_async_processes(self, reason):
        super().fail_async_processes(reason)
        self.fail(reason="fail_async_processes")

    def new_repeat_trial(self, experiment, repeat_trial_index, num_repeat_trials):
        repeat_trial = self.__class__(
            experiment=experiment,
            node=self.origin,
            participant=self.participant,
            propagate_failure=False,
            is_repeat_trial=True,
            parent_trial=self,
            repeat_trial_index=repeat_trial_index,
            num_repeat_trials=num_repeat_trials,
        )
        return repeat_trial


class TrialMaker(Module):
    """
    Generic trial generation module, to be inserted
    in an experiment timeline. It is responsible for organising
    the administration of trials to the participant.

    Users are invited to override the following abstract methods/attributes:

    * :meth:`~psynet.trial.main.TrialMaker.prepare_trial`,
      which prepares the next trial to administer to the participant.

    * :meth:`~psynet.trial.main.TrialMaker.experiment_setup_routine`
      (optional), which defines a routine that sets up the experiment
      (for example initialising and seeding networks).

    * :meth:`~psynet.trial.main.TrialMaker.init_participant`
      (optional), a function that is run when the participant begins
      this sequence of trials, intended to initialize the participant's state.
      Make sure you call ``super().init_participant`` when overriding this.

    * :meth:`~psynet.trial.main.TrialMaker.finalize_trial`
      (optional), which finalizes the trial after the participant
      has given their response.

    * :meth:`~psynet.trial.main.TrialMaker.on_complete`
      (optional), run once the sequence of trials is complete.

    * :meth:`~psynet.trial.main.TrialMaker.performance_check`
      (optional), which checks the performance of the participant
      with a view to rejecting poor-performing participants.

    * :meth:`~psynet.trial.main.TrialMaker.compute_bonus`;
      computes the final performance bonus to assign to the participant.

    * :attr:`~psynet.trial.main.TrialMaker.num_trials_still_required`
      (optional), which is used to estimate how many more participants are
      still required in the case that ``recruit_mode="num_trials"``.

    * :attr:`~psynet.trial.main.TrialMaker.give_end_feedback_passed`
      (default = ``False``); if ``True``, then participants who pass the
      final performance check will be given feedback. This feedback can
      be customised by overriding
      :meth:`~psynet.trial.main.TrialMaker.get_end_feedback_passed_page`.

    Users are also invited to add new recruitment criteria for selection with
    the ``recruit_mode`` argument. This may be achieved using a custom subclass
    of :class:`~psynet.trial.main.TrialMaker` as follows:

    ::

        class CustomTrialMaker(TrialMaker):
            def new_recruit(self, experiment):
                if experiment.my_condition:
                    return True # True means recruit more
                else:
                    return False # False means don't recruit any more (for now)

            recruit_criteria = {
                **TrialMaker.recruit_criteria,
                "new_recruit": new_recruit
            }

    With the above code, you'd then be able to use ``recruit_mode="new_recruit"``.
    If you're subclassing a subclass of :class:`~psynet.trial.main.TrialMaker`,
    then just replace that subclass wherever :class:`~psynet.trial.main.TrialMaker`
    occurs in the above code.

    Parameters
    ----------

    trial_class
        The class object for trials administered by this maker.

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".

    expected_num_trials
        Expected number of trials that the participant will take,
        including repeat trials
        (used for progress estimation).

    check_performance_at_end
        If ``True``, the participant's performance
        is evaluated at the end of the series of trials.

    check_performance_every_trial
        If ``True``, the participant's performance
        is evaluated after each trial.

    fail_trials_on_premature_exit
        If ``True``, a participant's trials are marked as failed
        if they leave the experiment prematurely.

    fail_trials_on_participant_performance_check
        If ``True``, a participant's trials are marked as failed
        if the participant fails a performance check.

    propagate_failure
        If ``True``, the failure of a trial is propagated to other
        parts of the experiment (the nature of this propagation is left up
        to the implementation).

    recruit_mode
        Selects a recruitment criterion for determining whether to recruit
        another participant. The built-in criteria are ``"num_participants"``
        and ``"num_trials"``, though the latter requires overriding of
        :attr:`~psynet.trial.main.TrialMaker.num_trials_still_required`.

    target_num_participants
        Target number of participants to recruit for the experiment. All
        participants must successfully finish the experiment to count
        towards this quota. This target is only relevant if
        ``recruit_mode="num_participants"``.

    num_repeat_trials
        Number of repeat trials to present to the participant. These trials
        are typically used to estimate the reliability of the participant's
        responses.
        Defaults to ``0``.

    Attributes
    ----------

    check_timeout_interval_sec : float
        How often to check for timeouts, in seconds (default = 30).
        Users are invited to override this.

    response_timeout_sec : float
        How long until a trial's response times out, in seconds (default = 60)
        (i.e. how long PsyNet will wait for the participant's response to a trial).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval_sec`.
        Users are invited to override this.

    async_timeout_sec : float
        How long until an async process times out, in seconds (default = 300).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval_sec`.
        Users are invited to override this.

    introduction
        An optional event or list of elts to execute prior to beginning the trial loop.

    give_end_feedback_passed : bool
        If ``True``, then participants who pass the final performance check
        are given feedback. This feedback can be customised by overriding
        :meth:`~psynet.trial.main.TrialMaker.get_end_feedback_passed_page`.

    performance_check_threshold : float
        Score threshold used by the default performance check method, defaults to 0.0.
        By default, corresponds to the minimum proportion of non-failed trials that
        the participant must achieve to pass the performance check.

    end_performance_check_waits : bool
        If ``True`` (default), then the final performance check waits until all trials no
        longer have any pending asynchronous processes.
    """

    def __init__(
        self,
        id_: str,
        trial_class,
        phase: str,
        expected_num_trials: Union[int, float],
        check_performance_at_end: bool,
        check_performance_every_trial: bool,
        fail_trials_on_premature_exit: bool,
        fail_trials_on_participant_performance_check: bool,
        propagate_failure: bool,
        recruit_mode: str,
        target_num_participants: Optional[int],
        num_repeat_trials: int,
    ):
        if recruit_mode == "num_participants" and target_num_participants is None:
            raise ValueError(
                "If <recruit_mode> == 'num_participants', then <target_num_participants> must be provided."
            )

        if recruit_mode == "num_trials" and target_num_participants is not None:
            raise ValueError(
                "If <recruit_mode> == 'num_trials', then <target_num_participants> must be None."
            )

        if trial_class.time_estimate is None:
            raise ValueError(
                f"Trial class '{trial_class}' was missing a `time_estimate`. Please set an appropriate time estimate "
                + "as a class attribute in the trial class, for example `time_estimate = 5`. "
                + "(Note: previous versions of PsyNet set this time estimate via the trial maker. "
                + "If you are running code from a previous version of PsyNet, you can update it "
                + "by simply cutting and pasting this argument from the trial-maker constructor call "
                + "to the definition of your trial class.)"
            )

        self.trial_class = trial_class
        self.id = id_
        self.phase = phase
        self.expected_num_trials = expected_num_trials
        self.check_performance_at_end = check_performance_at_end
        self.check_performance_every_trial = check_performance_every_trial
        self.fail_trials_on_premature_exit = fail_trials_on_premature_exit
        self.fail_trials_on_participant_performance_check = (
            fail_trials_on_participant_performance_check
        )
        self.propagate_failure = propagate_failure
        self.recruit_mode = recruit_mode
        self.target_num_participants = target_num_participants
        self.num_repeat_trials = num_repeat_trials

        elts = join(
            ExperimentSetupRoutine(self.experiment_setup_routine),
            ParticipantFailRoutine(
                self.with_namespace(), self.participant_fail_routine
            ),
            RecruitmentCriterion(
                self.with_namespace(), self.selected_recruit_criterion
            ),
            self.check_timeout_task,
            CodeBlock(self.init_participant),
            self.introduction,
            self._trial_loop(),
            CodeBlock(self.on_complete),
            self._check_performance_logic(type="end")
            if check_performance_at_end
            else None,
        )
        label = self.with_namespace()
        super().__init__(label, elts)

    participant_progress_threshold = 0.1

    performance_check_threshold = 0.0

    introduction = None

    @property
    def num_complete_participants(self):
        return Participant.query.filter_by(complete=True).count()

    @property
    def num_working_participants(self):
        return Participant.query.filter_by(status="working", failed=False).count()

    @property
    def num_viable_participants(self):
        return

    def prepare_trial(self, experiment, participant):
        """
        Prepares and returns a trial to administer the participant.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.


        Returns
        _______

        :class:`~psynet.trial.main.Trial`
            A :class:`~psynet.trial.main.Trial` object representing the trial
            to be taken by the participant.
        """
        raise NotImplementedError

    def experiment_setup_routine(self, experiment):
        """
        Defines a routine for setting up the experiment.
        Note that this routine is (currently) called every time the Experiment
        class is initialized, so it should be idempotent (calling it
        multiple times should have no effect) and be efficient
        (so that it doesn't incur a repeated costly overhead).

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        """
        raise NotImplementedError

    check_timeout_interval_sec = 30
    response_timeout_sec = 60 * 5
    async_timeout_sec = 300
    end_performance_check_waits = True

    def participant_fail_routine(self, participant, experiment):
        if (
            self.fail_trials_on_participant_performance_check
            and "performance_check" in participant.failure_tags
        ) or (
            self.fail_trials_on_premature_exit
            and "premature_exit" in participant.failure_tags
        ):
            self.fail_participant_trials(
                participant, reason=", ".join(participant.failure_tags)
            )

    @property
    def check_timeout_task(self):
        return DatabaseCheck(self.with_namespace("check_timeout"), self.check_timeout)

    def check_timeout(self):
        # pylint: disable=no-member
        self.check_old_trials()
        self.check_async_trials()
        db.session.commit()

    def selected_recruit_criterion(self, experiment):
        if self.recruit_mode not in self.recruit_criteria:
            raise ValueError(f"Invalid recruitment mode: {self.recruit_mode}")
        function = self.recruit_criteria[self.recruit_mode]
        return call_function(function, {"self": self, "experiment": experiment})

    def null_criterion(self, experiment):
        logger.info("Recruitment is disabled for this module.")
        return False

    def num_participants_criterion(self, experiment):
        logger.info(
            "Target number of participants = %i, number of completed participants = %i, number of working participants = %i.",
            self.target_num_participants,
            self.num_complete_participants,
            self.num_working_participants,
        )
        return (
            self.num_complete_participants + self.num_working_participants
        ) < self.target_num_participants

    def num_trials_criterion(self, experiment):
        num_trials_still_required = self.num_trials_still_required
        num_trials_pending = self.num_trials_pending
        logger.info(
            "Number of trials still required = %i, number of pending trials = %i.",
            num_trials_still_required,
            num_trials_pending,
        )
        return num_trials_still_required > num_trials_pending

    recruit_criteria = {
        None: null_criterion,
        "num_participants": num_participants_criterion,
        "num_trials": num_trials_criterion,
    }

    give_end_feedback_passed = False

    def get_end_feedback_passed_page(self, score):
        """
        Defines the feedback given to participants who pass the final performance check.
        This feedback is only given if :attr:`~psynet.trial.main.TrialMaker.give_end_feedback_passed`
        is set to ``True``.

        Parameters
        ----------

        score :
            The participant's score on the performance check.

        Returns
        -------

        :class:`~psynet.timeline.Page` :
            A feedback page.
        """
        score_to_display = "NA" if score is None else f"{(100 * score):.0f}"

        return InfoPage(
            Markup(
                f"Your performance score was <strong>{score_to_display}&#37;</strong>."
            ),
            time_estimate=5,
        )

    def _get_end_feedback_passed_logic(self):
        if self.give_end_feedback_passed:

            def f(participant):
                score = participant.var.get(self.with_namespace("performance_check"))[
                    "score"
                ]
                return self.get_end_feedback_passed_page(score)

            return PageMaker(f, time_estimate=5)
        else:
            return []

    def visualize(self):
        rendered_div = super().visualize()

        div = tags.div()
        with div:
            with tags.ul(cls="details"):
                if (
                    hasattr(self, "expected_num_trials")
                    and self.expected_num_trials is not None
                ):
                    tags.li(f"Expected number of trials: {self.expected_num_trials}")
                if (
                    hasattr(self, "target_num_participants")
                    and self.target_num_participants is not None
                ):
                    tags.li(
                        f"Target number of participants: {self.target_num_participants}"
                    )
                if hasattr(self, "recruit_mode") and self.recruit_mode is not None:
                    tags.li(f"Recruitment mode: {self.recruit_mode}")

        return rendered_div + div.render()

    def get_progress_info(self):
        return super().get_progress_info()

    def visualize_tooltip(self):
        return super().visualize_tooltip()

    @property
    def num_trials_pending(self):
        return sum(
            [
                self.estimate_num_pending_trials(p)
                for p in self.established_working_participants
            ]
        )

    @property
    def num_trials_still_required(self):
        raise NotImplementedError

    def estimate_num_pending_trials(self, participant):
        return self.expected_num_trials - self.get_num_completed_trials_in_phase(
            participant
        )

    @property
    def working_participants(self):
        return Participant.query.filter_by(status="working", failed=False)

    @property
    def established_working_participants(self):
        return [
            p
            for p in self.working_participants
            if p.progress > self.participant_progress_threshold
        ]

    def check_old_trials(self):
        time_threshold = datetime.datetime.now() - datetime.timedelta(
            seconds=self.response_timeout_sec
        )
        trials_to_fail = (
            self.trial_class.query.filter_by(complete=False, failed=False)
            .filter(self.trial_class.creation_time < time_threshold)
            .all()
        )
        logger.info("Found %i old trial(s) to fail.", len(trials_to_fail))
        for trial in trials_to_fail:
            trial.fail(reason="response_timeout")

    def check_async_trials(self):
        trials_awaiting_processes = self.trial_class.query.filter_by(
            awaiting_async_process=True
        ).all()
        time_threshold = datetime.datetime.now() - datetime.timedelta(
            seconds=self.async_timeout_sec
        )
        trials_to_fail = [
            t
            for t in trials_awaiting_processes
            if t.earliest_async_process_start_time < time_threshold
        ]
        logger.info(
            "Found %i trial(s) with long-pending asynchronous processes to fail.",
            len(trials_to_fail),
        )
        for trial in trials_to_fail:
            trial.fail_async_processes(reason="async_process_timeout")

    def init_participant(self, experiment, participant):
        # pylint: disable=unused-argument
        """
        Initializes the participant at the beginning of the sequence of trials.
        If you override this, make sure you call ``super().init_particiant(...)``
        somewhere in your new method.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """
        self.init_num_completed_trials_in_phase(participant)
        participant.var.set(self.with_namespace("in_repeat_phase"), False)
        self.init_participant_group(experiment, participant)

    def init_participant_group(self, experiment, participant):
        if participant.has_participant_group(self.id):
            return None
        participant.set_participant_group(
            self.id,
            self.choose_participant_group(
                experiment=experiment, participant=participant
            ),
        )

    def choose_participant_group(self, experiment, participant):
        # pylint: disable=unused-argument
        """
        Determines the participant group assigned to the current participant.
        By default the participant is assigned to the group "default".

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        Returns
        -------

        A string label identifying the selected participant group.
        """
        return "default"

    def on_complete(self, experiment, participant):
        """
        An optional function run once the participant completes their
        sequence of trials.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """

    def finalize_trial(self, answer, trial, experiment, participant):
        # pylint: disable=unused-argument,no-self-use
        """
        This function is run after the participant completes the trial.
        It can be optionally customised, for example to add some more postprocessing.
        If you override this, make sure you call ``super().finalize_trial(...)``
        somewhere in your new method.


        Parameters
        ----------

        answer
            The ``answer`` object provided by the trial.

        trial
            The :class:`~psynet.trial.main.Trial` object representing the trial.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """
        trial.answer = answer
        trial.complete = True
        trial.response_id = participant.last_response_id
        trial.time_taken = trial.response.metadata["time_taken"]
        self.increment_num_completed_trials_in_phase(participant)

    def performance_check(self, experiment, participant, participant_trials):
        # pylint: disable=unused-argument
        """
        Defines an automated check for evaluating the participant's
        current performance.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        participant_trials
            A list of all trials completed so far by the participant.


        Returns
        -------

        dict
            The dictionary should include the following values:

            - ``score``, expressed as a ``float`` or ``None``.
            - ``passed`` (Boolean), identifying whether the participant passed the check.

        """
        raise NotImplementedError

    def with_namespace(self, x=None):
        return with_trial_maker_namespace(self.id, x=x)

    def fail_participant_trials(self, participant, reason=None):
        trials_to_fail = (
            db.session.query(Trial)
            .filter_by(participant_id=participant.id, failed=False)
            .join(TrialNetwork)
            .filter_by(trial_maker_id=self.id)
        )
        for trial in trials_to_fail:
            trial.fail(reason=reason)

    def check_fail_logic(self):
        """
        Determines the timeline logic for when a participant fails
        the performance check.
        By default, the participant is shown an :class:`~psynet.timeline.UnsuccessfulEndPage`.

        Returns
        -------

        An :class:`~psynet.timeline.Elt` or a list of :class:`~psynet.timeline.Elt` s.
        """
        return join(UnsuccessfulEndPage(failure_tags=["performance_check"]))

    def _check_performance_logic(self, type):
        assert type in ["trial", "end"]

        def eval_checks(experiment, participant):
            participant_trials = self.get_participant_trials(participant)
            results = self.performance_check(
                experiment=experiment,
                participant=participant,
                participant_trials=participant_trials,
            )

            assert isinstance(results["passed"], bool)
            participant.var.set(self.with_namespace("performance_check"), results)

            if type == "end":
                bonus = self.compute_bonus(**results)
                participant.var.set(self.with_namespace("performance_bonus"), bonus)
                participant.inc_performance_bonus(bonus)

            return results["passed"]

        logic = switch(
            "performance_check",
            function=eval_checks,
            branches={
                True: [] if type == "trial" else self._get_end_feedback_passed_logic(),
                False: self.check_fail_logic(),
            },
            fix_time_credit=False,
            log_chosen_branch=False,
        )

        if type == "end" and self.end_performance_check_waits:
            return join(
                wait_while(
                    self.any_pending_async_trials,
                    expected_wait=5,
                    log_message="Waiting for pending async trials.",
                ),
                logic,
            )
        else:
            return logic

    def any_pending_async_trials(self, participant):
        trials = self.get_participant_trials(participant)
        return any([t.awaiting_async_process for t in trials])

    def get_participant_trials(self, participant):
        """
        Returns all trials (complete and incomplete) owned by the current participant,
        including repeat trials, in the current phase. Not intended for overriding.

        Parameters
        ----------

        participant:
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        """
        all_participant_trials = self.trial_class.query.filter_by(
            participant_id=participant.id
        ).all()
        return [
            t
            for t in all_participant_trials
            if t.trial_maker_id == self.id
            and t.phase
            == self.phase  # the latter check shouldn't strictly be necessary
        ]

    def _prepare_trial(self, experiment, participant):
        if participant.var.get(self.with_namespace("in_repeat_phase")):
            trial = None
        else:
            # Returns None if there are no more experiment trials available.
            trial = self.prepare_trial(experiment=experiment, participant=participant)
        if trial is None and self.num_repeat_trials > 0:
            participant.var.set(self.with_namespace("in_repeat_phase"), True)
            trial = self._prepare_repeat_trial(
                experiment=experiment, participant=participant
            )
        if trial is not None:
            participant.var.current_trial = trial.id
        else:
            participant.var.current_trial = None
        experiment.save()

    def _prepare_repeat_trial(self, experiment, participant):
        if not participant.var.has(self.with_namespace("trials_to_repeat")):
            self._init_trials_to_repeat(participant)
        trials_to_repeat = participant.var.get(self.with_namespace("trials_to_repeat"))
        repeat_trial_index = participant.var.get(
            self.with_namespace("repeat_trial_index")
        )
        try:
            trial_to_repeat_id = trials_to_repeat[repeat_trial_index]
            trial_to_repeat = self.trial_class.query.filter_by(
                id=trial_to_repeat_id
            ).one()
            trial = trial_to_repeat.new_repeat_trial(
                experiment, repeat_trial_index, len(trials_to_repeat)
            )
            participant.var.inc(self.with_namespace("repeat_trial_index"))
            experiment.save(trial)
        except IndexError:
            trial = None
        return trial

    def _init_trials_to_repeat(self, participant):
        completed_trial_ids = [t.id for t in self.get_participant_trials(participant)]
        actual_num_repeat_trials = min(len(completed_trial_ids), self.num_repeat_trials)
        participant.var.set(
            self.with_namespace("trials_to_repeat"),
            random.sample(completed_trial_ids, actual_num_repeat_trials),
        )
        participant.var.set(self.with_namespace("repeat_trial_index"), 0)

    def _show_trial(self, experiment, participant):
        trial = self._get_current_trial(participant)
        return trial.show_trial(experiment=experiment, participant=participant)

    def postprocess_answer(self, answer, trial, participant):
        return answer

    def _postprocess_answer(self, experiment, participant):
        answer = participant.answer
        trial = self._get_current_trial(participant)
        participant.answer = self.postprocess_answer(answer, trial, participant)

    def _finalize_trial(self, experiment, participant):
        trial = self._get_current_trial(participant)
        answer = participant.answer
        self.finalize_trial(
            answer=answer, trial=trial, experiment=experiment, participant=participant
        )
        if not trial.awaiting_async_process:
            trial.mark_as_finalized()

    def _get_current_trial(self, participant):
        trial_id = participant.var.current_trial
        if trial_id is None:
            return None
        return self.trial_class.query.get(trial_id)

    def _construct_feedback_logic(self):
        return conditional(
            label=self.with_namespace("feedback"),
            condition=lambda experiment, participant: (
                self._get_current_trial(participant).gives_feedback(
                    experiment, participant
                )
            ),
            logic_if_true=join(
                wait_while(
                    lambda participant: not self._get_current_trial(
                        participant
                    ).ready_for_feedback,
                    expected_wait=0,
                    log_message="Waiting for feedback to be ready.",
                ),
                PageMaker(
                    lambda experiment, participant: (
                        self._get_current_trial(participant).show_feedback(
                            experiment=experiment, participant=participant
                        )
                    ),
                    time_estimate=0,
                ),
            ),
            fix_time_credit=False,
            log_chosen_branch=False,
        )

    def _get_current_time_credit(self, participant):
        return participant.time_credit.confirmed_credit

    def _log_time_credit_before_trial(self, participant):
        trial = self._get_current_trial(participant)
        trial.time_credit_before_trial = self._get_current_time_credit(participant)

    def _log_time_credit_after_trial(self, participant):
        trial = self._get_current_trial(participant)
        trial.time_credit_after_trial = self._get_current_time_credit(participant)
        trial.time_credit_from_trial = (
            trial.time_credit_after_trial - trial.time_credit_before_trial
        )
        if trial.check_time_credit_received:
            if trial.time_credit_from_trial != trial.time_estimate:
                logger.info(
                    f"Warning: Trial {trial.id} received an unexpected amount of time credit "
                    f"(expected = {trial.time_estimate} seconds; "
                    f"actual = {trial.time_credit_from_trial} seconds). "
                    f"Consider setting the trial's `time_estimate` parameter to {trial.time_credit_from_trial}."
                    "You can disable this warning message by setting `Trial.check_time_credit_received = False`."
                )

    def _wait_for_trial(self, experiment, participant):
        return False

    def _trial_loop(self):
        return join(
            wait_while(
                self._wait_for_trial,
                expected_wait=0.0,
                log_message="Waiting for trial to be ready.",
            ),
            CodeBlock(self._prepare_trial),
            while_loop(
                self.with_namespace("trial_loop"),
                lambda experiment, participant: self._get_current_trial(participant)
                is not None,
                logic=join(
                    CodeBlock(self._log_time_credit_before_trial),
                    PageMaker(
                        self._show_trial,
                        time_estimate=self.trial_class.time_estimate,
                        accumulate_answers=self.trial_class.accumulate_answers,
                    ),
                    CodeBlock(self._postprocess_answer),
                    CodeBlock(self._finalize_trial),
                    self._construct_feedback_logic(),
                    CodeBlock(self._log_time_credit_after_trial),
                    (
                        self._check_performance_logic(type="trial")
                        if self.check_performance_every_trial
                        else None
                    ),
                    wait_while(
                        self._wait_for_trial,
                        expected_wait=0.0,
                        log_message="Waiting for trial to be ready.",
                    ),
                    CodeBlock(self._prepare_trial),
                ),
                expected_repetitions=self.expected_num_trials,
                fix_time_credit=False,
            ),
        )

    @property
    def num_completed_trials_in_phase_var_id(self):
        return self.with_namespace("num_completed_trials_in_phase")

    def set_num_completed_trials_in_phase(self, participant, value):
        participant.var.set(self.num_completed_trials_in_phase_var_id, value)

    def get_num_completed_trials_in_phase(self, participant):
        try:
            return participant.var.get(self.num_completed_trials_in_phase_var_id)
        except UndefinedVariableError:
            return 0

    def init_num_completed_trials_in_phase(self, participant):
        self.set_num_completed_trials_in_phase(participant, 0)

    def increment_num_completed_trials_in_phase(self, participant):
        self.set_num_completed_trials_in_phase(
            participant, self.get_num_completed_trials_in_phase(participant) + 1
        )


class NetworkTrialMaker(TrialMaker):
    """
    Trial maker for network-based experiments.
    These experiments are organised around networks
    in an analogous way to the network-based experiments in Dallinger.
    A :class:`~dallinger.models.Network` comprises a collection of
    :class:`~dallinger.models.Node` objects organised in some kind of structure.
    Here the role of :class:`~dallinger.models.Node` objects
    is to generate :class:`~dallinger.models.Trial` objects.
    Typically the :class:`~dallinger.models.Node` object represents some
    kind of current experiment state, such as the last datum in a transmission chain.
    In some cases, a :class:`~dallinger.models.Network` or a :class:`~dallinger.models.Node`
    will be owned by a given participant; in other cases they will be shared
    between participants.

    An important feature of these networks is that their structure can change
    over time. This typically involves adding new nodes that somehow
    respond to the trials that have been submitted previously.

    The present class facilitates this behaviour by providing
    a built-in :meth:`~psynet.trial.main.TrialMaker.prepare_trial`
    implementation that comprises the following steps:

    1. Find the available networks from which to source the next trial,
       ordered by preference
       (:meth:`~psynet.trial.main.NetworkTrialMaker.find_networks`).
       These may be created on demand, or alternatively pre-created by
       :meth:`~psynet.trial.main.NetworkTrialMaker.experiment_setup_routine`.
    2. Give these networks an opportunity to grow (i.e. update their structure
       based on the trials that they've received so far)
       (:meth:`~psynet.trial.main.NetworkTrialMaker.grow_network`).
    3. Iterate through these networks, and find the first network that has a
       node available for the participant to attach to.
       (:meth:`~psynet.trial.main.NetworkTrialMaker.find_node`).
    4. Create a trial from this node
       (:meth:`psynet.trial.main.Trial.__init__`).

    The trial is then administered to the participant, and a response elicited.
    Once the trial is finished, the network is given another opportunity to grow.

    The implementation also provides support for asynchronous processing,
    for example to prepare the stimuli available at a given node,
    or to postprocess trials submitted to a given node.
    There is some sophisticated logic to make sure that a
    participant is not assigned to a :class:`~dallinger.models.Node` object
    if that object is still waiting for an asynchronous process,
    and likewise a trial won't contribute to a growing network if
    it is still pending the outcome of an asynchronous process.

    The user is expected to override the following abstract methods/attributes:

    * :meth:`~psynet.trial.main.NetworkTrialMaker.experiment_setup_routine`,
      (optional), which defines a routine that sets up the experiment
      (for example initialising and seeding networks).

    * :meth:`~psynet.trial.main.NetworkTrialMaker.find_networks`,
      which finds the available networks from which to source the next trial,
      ordered by preference.

    * :meth:`~psynet.trial.main.NetworkTrialMaker.grow_network`,
      which give these networks an opportunity to grow (i.e. update their structure
      based on the trials that they've received so far).

    * :meth:`~psynet.trial.main.NetworkTrialMaker.find_node`,
      which takes a given network and finds a node which the participant can
      be attached to, if one exists.

    Do not override prepare_trial.

    Parameters
    ----------

    trial_class
        The class object for trials administered by this maker.

    network_class
        The class object for the networks used by this maker.
        This should subclass :class`~psynet.trial.main.TrialNetwork`.

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".

    expected_num_trials
        Expected number of trials that the participant will take,
        including repeat trials
        (used for progress estimation).

    check_performance_at_end
        If ``True``, the participant's performance
        is evaluated at the end of the series of trials.

    check_performance_every_trial
        If ``True``, the participant's performance
        is evaluated after each trial.

    fail_trials_on_premature_exit
        If ``True``, a participant's trials are marked as failed
        if they leave the experiment prematurely.

    fail_trials_on_participant_performance_check
        If ``True``, a participant's trials are marked as failed
        if the participant fails a performance check.

    propagate_failure
        If ``True``, the failure of a trial is propagated to other
        parts of the experiment (the nature of this propagation is left up
        to the implementation).

    recruit_mode
        Selects a recruitment criterion for determining whether to recruit
        another participant. The built-in criteria are ``"num_participants"``
        and ``"num_trials"``, though the latter requires overriding of
        :attr:`~psynet.trial.main.TrialMaker.num_trials_still_required`.

    target_num_participants
        Target number of participants to recruit for the experiment. All
        participants must successfully finish the experiment to count
        towards this quota. This target is only relevant if
        ``recruit_mode="num_participants"``.

    num_repeat_trials
        Number of repeat trials to present to the participant. These trials
        are typically used to estimate the reliability of the participant's
        responses.
        Defaults to ``0``.

    wait_for_networks
        If ``True``, then the participant will be made to wait if there are
        still more networks to participate in, but these networks are pending asynchronous processes.


    Attributes
    ----------

    check_timeout_interval_sec : float
        How often to check for trials that have timed out, in seconds (default = 30).
        Users are invited to override this.

    response_timeout_sec : float
        How long until a trial's response times out, in seconds (default = 60)
        (i.e. how long PsyNet will wait for the participant's response to a trial).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval_sec`.
        Users are invited to override this.

    async_timeout_sec : float
        How long until an async process times out, in seconds (default = 300).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval_sec`.
        Users are invited to override this.

    network_query : sqlalchemy.orm.Query
        An SQLAlchemy query for retrieving all networks owned by the current trial maker.
        Can be used for operations such as the following: ``self.network_query.count()``.

    num_networks : int
        Returns the number of networks owned by the trial maker.

    networks : list
        Returns the networks owned by the trial maker.

    performance_check_threshold : float
        Score threshold used by the default performance check method, defaults to 0.0.
        By default, corresponds to the minimum proportion of non-failed trials that
        the participant must achieve to pass the performance check.

    end_performance_check_waits : bool
        If ``True`` (default), then the final performance check waits until all trials no
        longer have any pending asynchronous processes.

    performance_threshold : float (default = -1.0)
        The performance threshold that is used in the
        :meth:`~psynet.trial.main.NetworkTrialMaker.performance_check` method.
    """

    def __init__(
        self,
        id_,
        trial_class,
        network_class,
        phase,
        expected_num_trials,
        check_performance_at_end,
        check_performance_every_trial,
        fail_trials_on_premature_exit,
        fail_trials_on_participant_performance_check,
        # latest performance check is saved in as a participant variable (value, success)
        propagate_failure,
        recruit_mode,
        target_num_participants,
        num_repeat_trials: int,
        wait_for_networks: bool,
    ):
        super().__init__(
            id_=id_,
            trial_class=trial_class,
            phase=phase,
            expected_num_trials=expected_num_trials,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants,
            num_repeat_trials=num_repeat_trials,
        )
        self.network_class = network_class
        self.wait_for_networks = wait_for_networks

    # The following methods are overwritten from TrialMaker.
    # Returns None if no trials could be found (this may not yet be supported by TrialMaker)
    def prepare_trial(self, experiment, participant):
        logger.info("Preparing trial for participant %i.", participant.id)
        networks = self.find_networks(participant=participant, experiment=experiment)
        logger.info(
            "Found %i network(s) for participant %i.", len(networks), participant.id
        )

        # Used to grow all available networks, but this was unscalable.

        for network in networks:
            self._grow_network(network, participant, experiment)
            node = self.find_node(
                network=network, participant=participant, experiment=experiment
            )
            if node is not None:
                logger.info(
                    "Attached node %i to participant %i.", node.id, participant.id
                )
                return self._create_trial(
                    node=node, participant=participant, experiment=experiment
                )
        logger.info(
            "Found no available nodes for participant %i, exiting.", participant.id
        )
        return None

    ####

    def find_networks(self, participant, experiment, ignore_async_processes=False):
        """
        Returns a list of all available networks for the participant's next trial, ordered
        in preference (most preferred to least preferred).

        Parameters
        ----------

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.
        """
        raise NotImplementedError

    def grow_network(self, network, participant, experiment):
        """
        Extends the network if necessary by adding one or more nodes.
        Returns ``True`` if any nodes were added.

        Parameters
        ----------

        network
            The network to be potentially extended.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.
        """
        raise NotImplementedError

    def find_node(self, network, participant, experiment):
        """
        Finds the node to which the participant should be attached for the next trial.

        Parameters
        ----------

        network
            The network to be potentially extended.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.
        """
        raise NotImplementedError

    def _create_trial(self, node, participant, experiment):
        trial = self.trial_class(
            experiment=experiment,
            node=node,
            participant=participant,
            propagate_failure=self.propagate_failure,
            is_repeat_trial=False,
        )
        db.session.add(trial)
        db.session.commit()
        return trial

    def finalize_trial(self, answer, trial, experiment, participant):
        # pylint: disable=unused-argument,no-self-use,no-member
        super().finalize_trial(answer, trial, experiment, participant)
        db.session.commit()
        if trial.run_async_post_trial:
            trial.queue_async_method("call_async_post_trial")
            db.session.commit()
        self._grow_network(trial.network, participant, experiment)

    def _grow_network(self, network, participant, experiment):
        # pylint: disable=no-member
        grown = self.grow_network(network, participant, experiment)
        assert isinstance(grown, bool)
        if grown and network.run_async_post_grow_network:
            network.queue_async_method("call_async_post_grow_network")
            db.session.commit()

    @property
    def network_query(self):
        return self.network_class.query.filter_by(
            trial_maker_id=self.id, phase=self.phase
        )

    @property
    def num_networks(self):
        return self.network_query.count()

    @property
    def networks(self):
        return self.network_query.all()

    def check_timeout(self):
        super().check_timeout()
        self.check_async_networks()
        db.session.commit()  # pylint: disable=no-member

    def check_async_networks(self):
        time_threshold = datetime.datetime.now() - datetime.timedelta(
            seconds=self.async_timeout_sec
        )
        networks_awaiting_processes = self.network_class.query.filter_by(
            awaiting_async_process=True
        ).all()
        networks_to_fail = [
            n
            for n in networks_awaiting_processes
            if n.earliest_async_process_start_time < time_threshold
        ]
        logger.info(
            "Found %i network(s) with long-pending asynchronous processes to clear.",
            len(networks_to_fail),
        )
        for network in networks_to_fail:
            network.fail_async_processes(reason="long-pending network process")

    performance_threshold = -1.0
    min_nodes_for_performance_check = 2
    performance_check_type = "consistency"
    consistency_check_type = "spearman_correlation"

    def compute_bonus(self, score, passed):
        """
        Computes the bonus to allocate to the participant at the end of a phase
        on the basis of the results of the final performance check.
        Note: if `check_performance_at_end = False`, then this function will not be run
        and the bonus will not be assigned.
        """
        return 0.0

    def performance_check(self, experiment, participant, participant_trials):
        if self.performance_check_type == "consistency":
            return self.performance_check_consistency(
                experiment, participant, participant_trials
            )
        elif self.performance_check_type == "performance":
            return self.performance_check_accuracy(
                experiment, participant, participant_trials
            )
        else:
            raise NotImplementedError

    def performance_check_accuracy(self, experiment, participant, participant_trials):
        num_trials = len(participant_trials)
        if num_trials == 0:
            p = None
            passed = True
        else:
            num_failed_trials = len([t for t in participant_trials if t.failed])
            p = 1 - num_failed_trials / num_trials
            passed = p >= self.performance_check_threshold
        return {"score": p, "passed": passed}

    def get_answer_for_consistency_check(self, trial):
        # Must return a number
        return float(trial.answer)

    def performance_check_consistency(
        self, experiment, participant, participant_trials
    ):
        trials_by_id = {trial.id: trial for trial in participant_trials}

        repeat_trials = [t for t in participant_trials if t.is_repeat_trial]
        parent_trials = [trials_by_id[t.parent_trial_id] for t in repeat_trials]

        repeat_trial_answers = [
            self.get_answer_for_consistency_check(t) for t in repeat_trials
        ]
        parent_trial_answers = [
            self.get_answer_for_consistency_check(t) for t in parent_trials
        ]

        assert self.min_nodes_for_performance_check >= 2

        if len(repeat_trials) < self.min_nodes_for_performance_check:
            logger.info(
                "min_nodes_for_performance_check was not reached, so consistency score cannot be calculated."
            )
            score = None
            passed = True
        else:
            consistency = self.get_consistency(
                repeat_trial_answers, parent_trial_answers
            )
            if isnan(consistency):
                logger.info(
                    """
                    get_consistency returned 'nan' in the performance check.
                    This commonly indicates that the participant gave the same response
                    to all repeat trials. The participant will be failed.
                    """
                )
                score = None
                passed = False
            else:
                score = float(consistency)
                passed = bool(score >= self.performance_threshold)
        logger.info(
            "Performance check for participant %i: consistency = %s, passed = %s",
            participant.id,
            "NA" if score is None else f"{score:.3f}",
            passed,
        )
        return {"score": score, "passed": passed}

    def get_consistency(self, x, y):
        if self.consistency_check_type == "pearson_correlation":
            return corr(x, y)
        elif self.consistency_check_type == "spearman_correlation":
            return corr(x, y, method="spearman")
        elif self.consistency_check_type == "percent_agreement":
            num_cases = len(x)
            num_agreements = sum([a == b for a, b in zip(x, y)])
            return num_agreements / num_cases
        else:
            raise NotImplementedError

    @staticmethod
    def group_trials_by_parent(trials):
        res = {}
        for trial in trials:
            parent_id = trial.parent_trial_id
            if parent_id not in res:
                res[parent_id] = []
            res[parent_id].append(trial)
        return res

    def _wait_for_trial(self, experiment, participant):
        if not self.wait_for_networks:
            return False
        else:
            num_networks_available_now = len(
                self.find_networks(participant, experiment)
            )
            if num_networks_available_now > 0:
                return False
            else:
                num_networks_available_in_future = len(
                    self.find_networks(
                        participant, experiment, ignore_async_processes=True
                    )
                )
                if num_networks_available_in_future > 0:
                    return True
                else:
                    return False


class TrialNetwork(SQLMixinDallinger, Network, AsyncProcessOwner):
    """
    A network class to be used by :class:`~psynet.trial.main.NetworkTrialMaker`.
    The user must override the abstract method :meth:`~psynet.trial.main.TrialNetwork.add_node`.
    The user may also wish to override the
    :meth:`~psynet.trial.main.TrialNetwork.async_post_grow_network` method
    if they wish to implement asynchronous network processing.

    Parameters
    ----------

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".

    experiment
        An instantiation of :class:`psynet.experiment.Experiment`,
        corresponding to the current experiment.

    Attributes
    ----------

    target_num_trials : int or None
        Indicates the target number of trials for that network.
        Left empty by default, but can be set by custom ``__init__`` functions.
        Stored as the field ``property2`` in the database.

    awaiting_async_process : bool
        Whether the network is currently closed and waiting for an asynchronous process to complete.
        Set by default to ``False`` in the ``__init__`` function.

    phase : str
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".
        Set by default in the ``__init__`` function.
        Stored as the field ``role`` in the database.

    source : Optional[TrialSource]
        Returns the network's :class:`~psynet.trial.main.TrialSource`,
        or ``None`` if none can be found.

    participant : Optional[Participant]
        Returns the network's :class:`~psynet.participant.Participant`,
        or ``None`` if none can be found.
        Implementation note:
        The network's participant corresponds to the participant
        listed in the network's :class:`~psynet.trial.main.TrialSource`.
        If the network has no such :class:`~psynet.trial.main.TrialSource`
        then an error is thrown.

    num_nodes : int
        Returns the number of non-failed nodes in the network.

    num_completed_trials : int
        Returns the number of completed and non-failed trials in the network
        (irrespective of asynchronous processes, but excluding repeat trials).

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    run_async_post_grow_network : bool
        Set this to ``True`` if you want the :meth:`~psynet.trial.main.TrialNetwork.async_post_grow_network`
        method to run after the network is grown.
    """

    __extra_vars__ = {
        **SQLMixinDallinger.__extra_vars__.copy(),
        **AsyncProcessOwner.__extra_vars__.copy(),
    }

    trial_maker_id = claim_field("trial_maker_id", __extra_vars__, str)
    target_num_trials = claim_field("target_num_trials", __extra_vars__, int)

    def calculate_full(self):
        "A more efficient version of Dallinger's built-in calculate_full method."
        n_nodes = Node.query.filter_by(network_id=self.id, failed=False).count()
        self.full = n_nodes >= (self.max_size or 0)

    def add_node(self, node):
        """
        Adds a node to the network. This method is responsible for setting
        ``self.full = True`` if the network is full as a result.
        """
        raise NotImplementedError

    # VarStore occuppies the <details> slot.
    @property
    def var(self):
        return VarStore(self)

    # Phase ####
    @hybrid_property
    def phase(self):
        return self.role

    @phase.setter
    def phase(self, value):
        self.role = value

    @phase.expression
    def phase(self):
        return cast(self.role, String)

    ####

    def __init__(self, trial_maker_id: str, phase: str, experiment):
        # pylint: disable=unused-argument
        AsyncProcessOwner.__init__(self)
        self.trial_maker_id = trial_maker_id
        self.awaiting_async_process = False
        self.phase = phase

    @property
    def source(self):
        sources = TrialSource.query.filter_by(network_id=self.id, failed=False)
        if len(sources) == 0:
            return None
        if len(sources) > 1:
            raise RuntimeError(f"Network {self.id} has more than one source!")
        return sources[0]

    @property
    def participant(self):
        source = self.source
        assert source is not None
        return source.participant

    @property
    def num_nodes(self):
        return TrialNode.query.filter_by(network_id=self.id, failed=False).count()

    def trials(self, failed=False, complete=True, is_repeat_trial=False):
        return Trial.query.filter_by(
            network_id=self.id,
            failed=failed,
            complete=complete,
            is_repeat_trial=is_repeat_trial,
        ).all()

    @property
    def num_completed_trials(self):
        return Trial.query.filter_by(
            network_id=self.id, failed=False, complete=True, is_repeat_trial=False
        ).count()

    run_async_post_grow_network = False

    def async_post_grow_network(self):
        """
        Optional function to be run after the network is grown.
        Will only run if :attr:`~psynet.trial.main.TrialNetwork.run_async_post_grow_network`
        is set to ``True``.
        """

    def call_async_post_grow_network(self):
        # Currently this function is redundant, but it's there in case we want to
        # add wrapping logic one day.
        self.async_post_grow_network()

    @property
    @extra_var(__extra_vars__)
    def n_nodes(self):
        return len([node for node in self.all_nodes])

    @property
    @extra_var(__extra_vars__)
    def n_active_nodes(self):
        return len([node for node in self.all_nodes if not node.failed])

    @property
    @extra_var(__extra_vars__)
    def n_failed_nodes(self):
        return len([node for node in self.all_nodes if node.failed])

    @property
    @extra_var(__extra_vars__)
    def n_trials(self):
        return len([info for info in self.all_infos if isinstance(info, Trial)])

    @property
    @extra_var(__extra_vars__)
    def n_active_trials(self):
        return len(
            [
                info
                for info in self.all_infos
                if isinstance(info, Trial) and not info.failed
            ]
        )

    @property
    @extra_var(__extra_vars__)
    def n_failed_trials(self):
        return len(
            [info for info in self.all_infos if isinstance(info, Trial) and info.failed]
        )


class TrialNode(SQLMixinDallinger, dallinger.models.Node, AsyncProcessOwner):
    __extra_vars__ = {
        **SQLMixinDallinger.__extra_vars__.copy(),
        **AsyncProcessOwner.__extra_vars__.copy(),
    }

    def __init__(self, network, participant=None):
        super().__init__(network=network, participant=participant)
        AsyncProcessOwner.__init__(self)


class TrialSource(TrialNode):
    pass
