# pylint: disable=unused-argument

import json
import random
import datetime

from flask import Markup
from statistics import mean
from math import isnan, nan
from typing import Union, Optional
from uuid import uuid4

from dallinger import db
import dallinger.models
from dallinger.models import Info, Network

from rq import Queue
from dallinger.db import redis_conn

from ..participant import Participant
from ..field import claim_field, claim_var, VarStore, UndefinedVariableError

from ..timeline import (
    PageMaker,
    CodeBlock,
    ExperimentSetupRoutine,
    ParticipantFailRoutine,
    RecruitmentCriterion,
    BackgroundTask,
    Module,
    conditional,
    switch,
    while_loop,
    reactive_seq,
    join
)

from ..page import (
    InfoPage,
    UnsuccessfulEndPage,
    wait_while
)

from ..utils import (
    call_function,
    corr,
    import_local_experiment,
    serialise_datetime,
    unserialise_datetime
)

from sqlalchemy import String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

# pylint: disable=unused-import
import rpdb

class AsyncProcessOwner():
    awaiting_async_process = claim_field(5, bool)
    pending_async_processes = claim_var("pending_async_processes", use_default=True, default=lambda: {})
    failed_async_processes = claim_var("failed_async_processes", use_default=True, default=lambda: {})

    @property
    def earliest_async_process_start_time(self):
        return min([unserialise_datetime(x["start_time"]) for x in self.pending_async_processes.values()])

    def queue_async_process(self, function):
        process_id = str(uuid4())
        self.push_async_process(process_id)
        db.session.commit()
        q = Queue("default", connection = redis_conn)
        q.enqueue_call(
            func=function,
            args=(self.id, process_id),
            timeout=1e10 # PsyNet deals with timeouts itself
        ) # pylint: disable=no-member

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
            "reason": reason
        }
        self.failed_async_processes = failed_async_processes

class Trial(Info, AsyncProcessOwner):
    """
    Represents a trial in the experiment.
    The user is expected to override the following methods:

    * :meth:`~psynet.trial.main.Trial.make_definition`,
      responsible for deciding on the content of the trial.
    * :meth:`~psynet.trial.main.Trial.show_trial`,
      determines how the trial is turned into a webpage for presentation to the participant.
    * :meth:`~psynet.trial.main.Trial.show_feedback`,
      defines an optional feedback page to be displayed after the trial.

    The user may also wish to override the
    :meth:`~psynet.trial.main.Trial.async_post_trial` method
    if they wish to implement asynchronous trial processing.

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
        Stored in ``property2`` in the database.

    answer : Object
        The response returned by the participant. This is serialised
        to JSON, so it shouldn't be too big.
        The user should not typically change this directly.
        Stored in ``details`` in the database.

    awaiting_async_process : bool
        Whether the trial is waiting for some asynchronous process
        to complete (e.g. to synthesise audiovisual material).

    earliest_async_process_start_time : Optional[datetime]
        Time at which the earliest pending async process was called.

    propagate_failure : bool
        Whether failure of a trial should be propagated to other
        parts of the experiment depending on that trial
        (for example, subsequent parts of a transmission chain).

    num_pages : int
        The number of pages that this trial comprises.
        Defaults to 1; override it for trials comprising multiple pages.

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
    """
    # pylint: disable=unused-argument
    __mapper_args__ = {"polymorphic_identity": "trial"}

    # Properties ###
    participant_id = claim_field(1, int)
    complete = claim_field(2, bool)
    is_repeat_trial = claim_field(3, bool)

    answer = claim_var("answer")
    propagate_failure = claim_var("propagate_failure")
    response_id = claim_var("response_id")
    repeat_trial_index = claim_var("repeat_trial_index")
    num_repeat_trials = claim_var("num_repeat_trials")

    # Override this if you intend to return multiple pages
    num_pages = 1

    # @property
    # def num_pages(self):
    #     raise NotImplementedError

    # VarStore occupies the <details> slot.
    @property
    def var(self):
        return VarStore(self)

    # Refactor this bit with claim_field equivalent.
    @property
    def definition(self):
        return json.loads(self.contents)

    @definition.setter
    def definition(self, definition):
        self.contents = json.dumps(definition)

    @property
    def participant(self):
        return Participant.query.filter_by(id=self.participant_id).one()

    def fail(self):
        """
        Marks a trial as failed. Failing a trial means that it is somehow
        excluded from certain parts of the experiment logic, for example
        not counting towards data collection quotas, or not contributing
        towards latter parts of a transmission chain.

        The original fail function from the
        :class:`~dallinger.models.Info` class
        throws an error if the object is already failed,
        but this behaviour is disabled here.
        """

        if not self.failed:
            self.failed = True
            self.time_of_death = datetime.datetime.now()

    #################

    def __init__(self, experiment, node, participant, propagate_failure, is_repeat_trial):
        super().__init__(origin=node)
        self.complete = False
        self.awaiting_async_process = False
        self.participant_id = participant.id
        self.propagate_failure = propagate_failure
        self.is_repeat_trial = is_repeat_trial
        self.definition = self.make_definition(experiment, participant)

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
        If this method returns a list, then this list must have
        a length equal to the :attr:`~psynet.trial.main.Trial.num_pages`
        attribute.

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
        return self.show_feedback(experiment=experiment, participant=participant) is not None

    run_async_post_trial = False

    def async_post_trial(self):
        """
        Optional function to be run after a trial is completed by the participant.
        Will only run if :attr:`~psynet.trial.main.Trial.run_async_post_trial`
        is set to ``True``.
        """
        raise NotImplementedError

    def fail_async_processes(self, reason):
        super().fail_async_processes(reason)
        self.fail()

    # def fail(self):
    #     self.failed = True
    #     self.time_of_death = timenow()

    def new_repeat_trial(self, experiment, repeat_trial_index, num_repeat_trials):
        repeat_trial = self.__class__(
            experiment=experiment,
            node=self.origin,
            participant=self.participant,
            propagate_failure=False,
            is_repeat_trial=True
        )
        repeat_trial.repeat_trial_index = repeat_trial_index
        repeat_trial.num_repeat_trials = num_repeat_trials
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
      this sequence of trials, intended to initialise the participant's state.
      Make sure you call ``super().init_participant`` when overriding this.

    * :meth:`~psynet.trial.main.TrialMaker.finalise_trial`
      (optional), which finalises the trial after the participant
      has given their response.

    * :meth:`~psynet.trial.main.TrialMaker.on_complete`
      (optional), run once the the sequence of trials is complete.

    * :meth:`~psynet.trial.main.TrialMaker.performance_check`
      (optional), which checks the performance of the participant
      with a view to rejecting poor-performing participants.

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

    time_estimate_per_trial
        Time estimated for each trial (seconds).

    expected_num_trials
        Expected number of trials that the participant will take,
        including repeat trials
        (used for progress estimation).

    check_performance_at_end
        If ``True``, the participant's performance is
        is evaluated at the end of the series of trials.

    check_performance_every_trial
        If ``True``, the participant's performance is
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

    Attributes
    ----------

    check_timeout_interval : float
        How often to check for timeouts, in seconds (default = 30).
        Users are invited to override this.

    response_timeout_sec : float
        How long until a trial's response times out, in seconds (default = 60)
        (i.e. how long PsyNet will wait for the participant's response to a trial).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval`.
        Users are invited to override this.

    async_timeout_sec : float
        How long until an async process times out, in seconds (default = 300).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval`.
        Users are invited to override this.

    introduction
        An optional event or list of events to execute prior to beginning the trial loop.

    give_end_feedback_passed : bool
        If ``True``, then participants who pass the final performance check
        are given feedback. This feedback can be customised by overriding
        :meth:`~psynet.trial.main.TrialMaker.get_end_feedback_passed_page`.

    performance_check_threshold : float
        Score threshold used by the default performance check method, defaults to 0.0.
        By default, corresponds to the minimum proportion of non-failed trials that
        the participant must achieve to pass the performance check.

    end_performance_check_waits : bool
        If True (default), then the final performance check waits until all trials no
        longer have any pending asynchronous processes.
    """

    def __init__(
        self,
        trial_class,
        phase: str,
        time_estimate_per_trial: Union[int, float],
        expected_num_trials: Union[int, float],
        check_performance_at_end: bool,
        check_performance_every_trial: bool,
        fail_trials_on_premature_exit: bool,
        fail_trials_on_participant_performance_check: bool,
        propagate_failure: bool,
        recruit_mode: str,
        target_num_participants: Optional[int],
        num_repeat_trials: int
    ):
        if recruit_mode == "num_participants" and target_num_participants is None:
            raise ValueError("If <recruit_mode> == 'num_participants', then <target_num_participants> must be provided.")

        if recruit_mode == "num_trials" and target_num_participants is not None:
            raise ValueError("If <recruit_mode> == 'num_trials', then <target_num_participants> must be None.")

        self.trial_class = trial_class
        self.trial_type = trial_class.__name__
        self.phase = phase
        self.time_estimate_per_trial = time_estimate_per_trial
        self.expected_num_trials = expected_num_trials
        self.check_performance_at_end = check_performance_at_end
        self.check_performance_every_trial = check_performance_every_trial
        self.fail_trials_on_premature_exit = fail_trials_on_premature_exit
        self.fail_trials_on_participant_performance_check = fail_trials_on_participant_performance_check
        self.propagate_failure = propagate_failure
        self.recruit_mode = recruit_mode
        self.target_num_participants = target_num_participants
        self.num_repeat_trials = num_repeat_trials

        events = join(
            ExperimentSetupRoutine(self.experiment_setup_routine),
            ParticipantFailRoutine(self.with_namespace(), self.participant_fail_routine),
            RecruitmentCriterion(self.with_namespace(), self.selected_recruit_criterion),
            self.check_timeout_task,
            CodeBlock(self.init_participant),
            self.introduction,
            self._trial_loop(),
            CodeBlock(self.on_complete),
            self._check_performance_logic(type="end") if check_performance_at_end else None
        )
        super().__init__(label=self.with_namespace(), events=events)

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

    # def recruitment_criterion(self, experiment):
    #     """Should return True if more participants are required."""
    #     raise NotImplementedError

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
        class is initialised, so it should be idempotent (calling it
        multiple times should have no effect) and be efficient
        (so that it doesn't incur a repeated costly overhead).

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        """
        raise NotImplementedError

    check_timeout_interval = 30
    response_timeout_sec = 60
    async_timeout_sec = 300
    end_performance_check_waits = True

    def participant_fail_routine(self, participant, experiment):
        if (
            self.fail_trials_on_participant_performance_check and
            "performance_check" in participant.failure_tags
        ) or (
            self.fail_trials_on_premature_exit and
            "premature_exit" in participant.failure_tags
        ):
            self.fail_participant_trials(participant)

    @property
    def check_timeout_task(self):
        return BackgroundTask(
            self.with_namespace("check_timeout"),
            self.check_timeout,
            interval_sec=self.check_timeout_interval
        )

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
            self.num_working_participants
        )
        return (self.num_complete_participants + self.num_working_participants) < self.target_num_participants

    def num_trials_criterion(self, experiment):
        num_trials_still_required = self.num_trials_still_required
        num_trials_pending = self.num_trials_pending
        logger.info(
            "Number of trials still required = %i, number of pending trials = %i.",
            num_trials_still_required,
            num_trials_pending
        )
        return num_trials_still_required > num_trials_pending

    recruit_criteria = {
        None: null_criterion,
        "num_participants": num_participants_criterion,
        "num_trials": num_trials_criterion
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
            Markup(f"Your performance score was <strong>{score_to_display}&#37;</strong>."),
            time_estimate=5
        )

    def _get_end_feedback_passed_logic(self):
        if self.give_end_feedback_passed:
            def f(participant):
                score = participant.var.get(self.with_namespace("performance_check"))["score"]
                return self.get_end_feedback_passed_page(score)
            return PageMaker(f, time_estimate = 5)
        else:
            return []

    @property
    def num_trials_pending(self):
        return sum([self.estimate_num_pending_trials(p) for p in self.established_working_participants])

    @property
    def num_trials_still_required(self):
        raise NotImplementedError

    def estimate_num_pending_trials(self, participant):
        return self.expected_num_trials - self.get_num_completed_trials_in_phase(participant)

    @property
    def working_participants(self):
        return (
            Participant
                .query
                .filter_by(status="working", failed=False)
        )

    @property
    def established_working_participants(self):
        return [
            p for p in self.working_participants
            if p.progress > self.participant_progress_threshold
        ]

    def check_old_trials(self):
        time_threshold = datetime.datetime.now() - datetime.timedelta(seconds=self.response_timeout_sec)
        trials_to_fail = (
            self.trial_class
                .query
                .filter_by(
                    complete=False,
                    failed=False
                )
                .filter(self.trial_class.creation_time < time_threshold)
                .all()
        )
        logger.info("Found %i old trial(s) to fail.", len(trials_to_fail))
        for trial in trials_to_fail:
            trial.fail()

    def check_async_trials(self):
        trials_awaiting_processes = self.trial_class.query.filter_by(awaiting_async_process=True).all()
        time_threshold = datetime.datetime.now() - datetime.timedelta(seconds=self.async_timeout_sec)
        trials_to_fail = [t for t in trials_awaiting_processes if t.earliest_async_process_start_time < time_threshold]
        logger.info("Found %i trial(s) with long-pending asynchronous processes to fail.", len(trials_to_fail))
        for trial in trials_to_fail:
            trial.fail_async_processes(reason="long-pending trial process")

    def init_participant(self, experiment, participant):
        # pylint: disable=unused-argument
        """
        Initialises the participant at the beginning of the sequence of trials.
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

    def finalise_trial(self, answer, trial, experiment, participant):
        # pylint: disable=unused-argument,no-self-use
        """
        This function is run after the participant completes the trial.
        It can be optionally customised, for example to add some more postprocessing.
        If you override this, make sure you call ``super().finalise_trial(...)``
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

    def with_namespace(self, x=None, shared_between_phases=False):
        prefix = self.trial_type if shared_between_phases else f"{self.trial_type}__{self.phase}"
        if x is None:
            return prefix
        return f"__{prefix}__{x}"

    def fail_participant_trials(self, participant):
        trials_to_fail = Trial.query.filter_by(participant_id=participant.id, failed=False)
        for trial in trials_to_fail:
            trial.fail()

    def check_fail_logic(self):
        """
        Determines the timeline logic for when a participant fails
        the performance check.
        By default, the participant is shown an :class:`~psynet.timeline.UnsuccessfulEndPage`.

        Returns
        -------

        An event (:class:`~psynet.timeline.Event`) or a list of events.
        """
        return join(
            UnsuccessfulEndPage(failure_tags=["performance_check"])
        )

    def _check_performance_logic(self, type):
        def eval_checks(experiment, participant):
            participant_trials = self.get_participant_trials(participant)
            results = self.performance_check(
                experiment=experiment,
                participant=participant,
                participant_trials=participant_trials
            )
            bonus = self.compute_bonus(**results)
            assert isinstance(results["passed"], bool)
            participant.var.set(self.with_namespace("performance_check"), results)
            participant.var.set(self.with_namespace("performance_bonus"), bonus)
            participant.inc_performance_bonus(bonus)
            return results["passed"]

        assert type in ["trial", "end"]

        logic = switch(
            "performance_check",
            function=eval_checks,
            branches={
                True: [] if type == "trial" else self._get_end_feedback_passed_logic(),
                False: self.check_fail_logic()
            },
            fix_time_credit=False,
            log_chosen_branch=False
        )

        if type == "end" and self.end_performance_check_waits:
            return join(
                wait_while(self.any_pending_async_trials, expected_wait=5),
                logic
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
        all_participant_trials = self.trial_class.query.filter_by(participant_id=participant.id).all()
        trials_in_phase = [t for t in all_participant_trials if t.phase == self.phase]
        return trials_in_phase

    def _prepare_trial(self, experiment, participant):
        if participant.var.get(self.with_namespace("in_repeat_phase")):
            trial = None
        else:
            # Returns None if there are no more experiment trials available.
            trial = self.prepare_trial(experiment=experiment, participant=participant)
        if trial is None and self.num_repeat_trials > 0:
            participant.var.set(self.with_namespace("in_repeat_phase"), True)
            trial = self._prepare_repeat_trial(experiment=experiment, participant=participant)
        if trial is not None:
            participant.var.current_trial = trial.id
        else:
            participant.var.current_trial = None
        experiment.save()

    def _prepare_repeat_trial(self, experiment, participant):
        if not participant.var.has(self.with_namespace("trials_to_repeat")):
            self._init_trials_to_repeat(participant)
        trials_to_repeat = participant.var.get(self.with_namespace("trials_to_repeat"))
        repeat_trial_index = participant.var.get(self.with_namespace("repeat_trial_index"))
        try:
            trial_to_repeat_id = trials_to_repeat[repeat_trial_index]
            trial_to_repeat = self.trial_class.query.filter_by(id=trial_to_repeat_id).one()
            trial = trial_to_repeat.new_repeat_trial(experiment, repeat_trial_index, len(trials_to_repeat))
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
            random.sample(completed_trial_ids, actual_num_repeat_trials)
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

    def _finalise_trial(self, experiment, participant):
        trial = self._get_current_trial(participant)
        answer = participant.answer
        self.finalise_trial(
            answer=answer,
            trial=trial,
            experiment=experiment,
            participant=participant
        )

    def _get_current_trial(self, participant):
        trial_id = participant.var.current_trial
        if trial_id is None:
            return None
        return self.trial_class.query.get(trial_id)

    def _construct_feedback_logic(self):
        return conditional(
            label=self.with_namespace("feedback"),
            condition=lambda experiment, participant: (
                self._get_current_trial(participant)
                    .gives_feedback(experiment, participant)
            ),
            logic_if_true=PageMaker(
                lambda experiment, participant: (
                    self._get_current_trial(participant)
                        .show_feedback(experiment=experiment, participant=participant)
                ),
                time_estimate=0
            ),
            fix_time_credit=False,
            log_chosen_branch=False
        )

    def _wait_for_trial(self, experiment, participant):
        return False

    def _trial_loop(self):
        return join(
            CodeBlock(self._prepare_trial),
            while_loop(
                self.with_namespace("trial_loop"),
                lambda experiment, participant: self._get_current_trial(participant) is not None,
                logic=join(
                    reactive_seq(
                        "show_trial",
                        self._show_trial,
                        num_pages=self.trial_class.num_pages,
                        time_estimate=self.time_estimate_per_trial
                    ),
                    CodeBlock(self._postprocess_answer),
                    CodeBlock(self._finalise_trial),
                    self._construct_feedback_logic(),
                    self._check_performance_logic(type="trial") if self.check_performance_every_trial else None,
                    wait_while(self._wait_for_trial, expected_wait=0.0),
                    CodeBlock(self._prepare_trial)
                ),
                expected_repetitions=self.expected_num_trials,
                fix_time_credit=False
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
            participant,
            self.get_num_completed_trials_in_phase(participant) + 1
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

    time_estimate_per_trial
        Time estimated for each trial (seconds).

    expected_num_trials
        Expected number of trials that the participant will take,
        including repeat trials
        (used for progress estimation).

    check_performance_at_end
        If ``True``, the participant's performance is
        is evaluated at the end of the series of trials.

    check_performance_every_trial
        If ``True``, the participant's performance is
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

    wait_for_networks
        If ``True``, then the participant will be made to wait if there are
        still more networks to participate in, but these networks are pending asynchronous processes.


    Attributes
    ----------

    check_timeout_interval : float
        How often to check for trials that have timed out, in seconds (default = 30).
        Users are invited to override this.

    response_timeout_sec : float
        How long until a trial's response times out, in seconds (default = 60)
        (i.e. how long PsyNet will wait for the participant's response to a trial).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval`.
        Users are invited to override this.

    async_timeout_sec : float
        How long until an async process times out, in seconds (default = 300).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval`.
        Users are invited to override this.

    network_query
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
        If True (default), then the final performance check waits until all trials no
        longer have any pending asynchronous processes.

    performance_threshold : float (default = -1.0)
        The performance threshold that is used in the
        :meth:`~psynet.trial.main.NetworkTrialMaker.performance_check` method.
    """

    def __init__(
        self,
        trial_class,
        network_class,
        phase,
        time_estimate_per_trial,
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
        wait_for_networks: bool
    ):
        super().__init__(
            trial_class=trial_class,
            phase=phase,
            time_estimate_per_trial=time_estimate_per_trial,
            expected_num_trials=expected_num_trials,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants,
            num_repeat_trials=num_repeat_trials
        )
        self.network_class = network_class
        self.wait_for_networks = True

    #### The following methods are overwritten from TrialMaker.
    #### Returns None if no trials could be found (this may not yet be supported by TrialMaker)
    def prepare_trial(self, experiment, participant):
        logger.info("Preparing trial for participant %i.", participant.id)
        networks = self.find_networks(participant=participant, experiment=experiment)
        logger.info("Found %i network(s) for participant %i.", len(networks), participant.id)
        for network in networks:
            self._grow_network(network, participant, experiment)
        for network in networks:
            node = self.find_node(network=network, participant=participant, experiment=experiment)
            if node is not None:
                logger.info("Attached node %i to participant %i.", node.id, participant.id)
                return self._create_trial(node=node, participant=participant, experiment=experiment)
        logger.info("Found no available nodes for participant %i, exiting.", participant.id)
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
            experiment,
            node,
            participant,
            self.propagate_failure,
            is_repeat_trial=False
        )
        experiment.session.add(trial)
        experiment.save()
        return trial

    def finalise_trial(self, answer, trial, experiment, participant):
        # pylint: disable=unused-argument,no-self-use,no-member
        super().finalise_trial(answer, trial, experiment, participant)
        if trial.run_async_post_trial:
            trial.queue_async_process(call_async_post_trial)
            db.session.commit()
        self._grow_network(trial.network, participant, experiment)

    def _grow_network(self, network, participant, experiment):
        # pylint: disable=no-member
        grown = self.grow_network(network, participant, experiment)
        assert isinstance(grown, bool)
        if grown and network.run_async_post_grow_network:
            network.queue_async_process(call_async_post_grow_network)
            db.session.commit()

    @property
    def network_query(self):
        return (
            self.network_class
                .query
                .filter_by(
                    trial_type=self.trial_type,
                    phase=self.phase
                )
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
        db.session.commit() # pylint: disable=no-member

    def check_async_networks(self):
        time_threshold = datetime.datetime.now() - datetime.timedelta(seconds=self.async_timeout_sec)
        networks_awaiting_processes = self.network_class.query.filter_by(awaiting_async_process=True).all()
        networks_to_fail = [n for n in networks_awaiting_processes if n.earliest_async_process_start_time < time_threshold]
        logger.info("Found %i network(s) with long-pending asynchronous processes to clear.", len(networks_to_fail))
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
        """
        return 0.0

    def performance_check(self, experiment, participant, participant_trials):
        if self.performance_check_type == "consistency":
            return self.performance_check_consistency(experiment, participant, participant_trials)
        elif self.performance_check_type == "performance":
            return self.performance_check_accuracy(experiment, participant, participant_trials)
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
        return {
            "score": p,
            "passed": passed
        }

    def get_answer_for_consistency_check(self, trial):
        # Must return a number
        return float(trial.answer)

    def performance_check_consistency(self, experiment, participant, participant_trials):
        assert self.min_nodes_for_performance_check >= 2
        trials_by_node = self.group_trials_by_node(participant_trials)
        answer_groups = [
            [self.get_answer_for_consistency_check(t) for t in trials]
            for trials in trials_by_node.values()
            if len(trials) > 1
        ]
        if len(answer_groups) < self.min_nodes_for_performance_check:
            score = None
            passed = True
        else:
            consistency = self.monte_carlo_consistency(answer_groups, n=100)
            if isnan(consistency):
                score = None
                passed = False
            else:
                score = float(consistency)
                passed = bool(score >= self.performance_threshold)
        logger.info(
            "Performance check for participant %i: consistency = %s, passed = %s",
            participant.id,
            "NA" if score is None else f"{score:.3f}",
            passed
        )
        return {
            "score": score,
            "passed": passed
        }

    def monte_carlo_consistency(self, groups, n):
        rels = []
        for _ in range(n):
            trial_pairs = [random.sample(group, 2) for group in groups]
            x = [pair[0] for pair in trial_pairs]
            y = [pair[1] for pair in trial_pairs]
            res = self.get_consistency(x, y)
            if not isnan(res):
                rels.append(res)
        if len(rels) == 0:
            return nan
        return mean(rels)

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
    def group_trials_by_node(trials):
        res = {}
        for trial in trials:
            node_id = trial.origin.id
            if node_id not in res:
                res[node_id] = []
            res[node_id].append(trial)
        return res

    def _wait_for_trial(self, experiment, participant):
        if not self.wait_for_networks:
            return False
        else:
            num_networks_available_now = len(self.find_networks(participant, experiment))
            if num_networks_available_now > 0:
                return False
            else:
                num_networks_available_in_future = len(self.find_networks(
                    participant, experiment, ignore_async_processes=True))
                if num_networks_available_in_future > 0:
                    return True
                else:
                    return False


class TrialNetwork(Network, AsyncProcessOwner):
    """
    A network class to be used by :class:`~psynet.trial.main.NetworkTrialMaker`.
    The user must override the abstract method :meth:`~psynet.trial.main.TrialNetwork.add_node`.
    The user may also wish to override the
    :meth:`~psynet.trial.main.TrialNetwork.async_post_grow_network` method
    if they wish to implement asynchronous network processing.

    Parameters
    ----------

    trial_type
        A string uniquely identifying the type of trial to be administered,
        typically just the name of the relevant class,
        e.g. ``"MelodyTrial"``.
        The same experiment should not contain multiple TrialMaker objects
        with the same ``trial_type``, unless they correspond to different
        phases of the experiment and are marked as such with the
        ``phase`` parameter.

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".

    experiment
        An instantiation of :class:`psynet.experiment.Experiment`,
        corresponding to the current experiment.

    Attributes
    ----------

    trial_type : str
        A string uniquely identifying the type of trial to be administered,
        typically just the name of the relevant class,
        e.g. ``"MelodyTrial"``.
        The same experiment should not contain multiple TrialMaker objects
        with the same ``trial_type``, unless they correspond to different
        phases of the experiment and are marked as such with the
        ``phase`` parameter.
        Stored as the field ``property1`` in the database.

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

    __mapper_args__ = {"polymorphic_identity": "trial_network"}

    trial_type = claim_field(1, str)
    target_num_trials = claim_field(2, int)

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

    def __init__(self, trial_type: str, phase: str, experiment):
        # pylint: disable=unused-argument
        self.trial_type = trial_type
        self.awaiting_async_process = False
        self.phase = phase

    @property
    def num_nodes(self):
        return dallinger.models.Node.query.filter_by(network_id=self.id, failed=False).count()

    @property
    def num_completed_trials(self):
        return Trial.query.filter_by(
            network_id=self.id,
            failed=False,
            complete=True,
            is_repeat_trial=False
        ).count()

    run_async_post_grow_network = False
    def async_post_grow_network(self):
        """
        Optional function to be run after the network is grown.
        Will only run if :attr:`~psynet.trial.main.TrialNetwork.run_async_post_grow_network`
        is set to ``True``.
        """

def call_async_post_trial(trial_id, process_id):
    logger.info("Running async_post_trial process %s for trial %i...", process_id, trial_id)
    import_local_experiment()
    trial = Trial.query.filter_by(id=trial_id).one()
    try:
        if process_id in trial.pending_async_processes:
            trial.async_post_trial()
            trial.pop_async_process(process_id)
        else:
            logger.info("Skipping async process %s as it is no longer queued.", process_id)
    except BaseException as e:
        trial.fail_async_processes(reason=f"exception in post-trial process: {e.__class__.__name__}")
        raise
    finally:
        db.session.commit() # pylint: disable=no-member

def call_async_post_grow_network(network_id, process_id):
    logger.info("Running async_post_grow_network for network %i...", network_id)
    import_local_experiment()
    network = Network.query.filter_by(id=network_id).one()
    try:
        if process_id in network.pending_async_processes:
            network.async_post_grow_network()
            network.pop_async_process(process_id)
        else:
            logger.info("Skipping async process %s as it is no longer queued.", process_id)
    except BaseException as e:
        network.fail_async_processes(reason=f"exception in post-grow-network process: {e.__class__.__name__}")
        raise
    finally:
        db.session.commit() # pylint: disable=no-member
