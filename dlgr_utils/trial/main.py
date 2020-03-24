# pylint: disable=unused-argument

import json
from typing import Union, Optional
import datetime

from dallinger import db
import dallinger.models
from dallinger.models import Info, Network

from ..participant import Participant
from ..field import claim_field, claim_var, VarStore

from ..timeline import (
    ReactivePage,
    CodeBlock,
    InfoPage,
    UnsuccessfulEndPage,
    ExperimentSetupRoutine,
    ParticipantFailRoutine,
    RecruitmentCriterion,
    BackgroundTask,
    Module,
    NullElt,
    conditional,
    while_loop,
    reactive_seq,
    join
)

from ..utils import call_function

from sqlalchemy import String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

import rpdb

# pylint: disable=unused-import
import rpdb

class Trial(Info):
    # pylint: disable=unused-argument
    __mapper_args__ = {"polymorphic_identity": "trial"}

    # Properties ###
    participant_id = claim_field(1, int)
    complete = claim_field(2, bool)
    answer = claim_field(3)

    propagate_failure = claim_var("propagate_failure")

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

    def fail(self):
        """The original fail function throws an error if the object is already failed,
        we disabled this behaviour."""
        if not self.failed:
            self.failed = True
            self.time_of_death = datetime.datetime.now()
    
    #################

    def __init__(self, experiment, node, participant, propagate_failure):
        super().__init__(origin=node)
        self.complete = False
        self.participant_id = participant.id
        self.definition = self.make_definition(node, experiment, participant)
        self.propagate_failure = propagate_failure

    def make_definition(self, node, experiment, participant):
        raise NotImplementedError

    def show_trial(self, experiment, participant):
        """
        Should return a Page object that returns an answer that can be stored in Trial.answer.
        Alternatively 
        """
        raise NotImplementedError

    def show_feedback(self, experiment, participant):
        """Should return a Page object displaying feedback (or None, which means no feedback)"""
        return None

    def gives_feedback(self, experiment, participant):
        return self.show_feedback(experiment=experiment, participant=participant) is not None

    # def fail(self):
    #     self.failed = True
    #     self.time_of_death = timenow()

class TrialGenerator(Module):
    # Generic trial generation module.
    #
    # Users will typically want to create a subclass of this class
    # that implements a custom prepare_trial function.
    #
    # If the experiment needs pre-initialised networks, then
    # you can create these networks using experiment_setup_routine.
    # Note that this is (currently) called every time the Experiment 
    # class is initialised, so it should be idempotent (calling it 
    # multiple times should have no effect) and be efficient
    # (so that it doesn't incur a repeated costly overhead). 
    #
    # It typically won't be necessary to override finalise_trial,
    # but the option is there if you want it.

    def __init__(
        self,
        trial_class, 
        phase: str, 
        time_allotted_per_trial: Union[int, float], 
        expected_num_trials: Union[int, float],
        check_performance_at_end: bool,
        check_performance_every_trial: bool,
        fail_trials_on_premature_exit: bool,
        fail_trials_on_participant_performance_check: bool,
        propagate_failure: bool,
        recruit_mode: str,
        target_num_participants: Optional[int]
    ):
        self.trial_class = trial_class
        self.trial_type = trial_class.__name__
        self.phase = phase
        self.time_allotted_per_trial = time_allotted_per_trial
        self.expected_num_trials = expected_num_trials
        self.check_performance_at_end = check_performance_at_end
        self.check_performance_every_trial = check_performance_every_trial
        self.fail_trials_on_premature_exit = fail_trials_on_premature_exit
        self.fail_trials_on_participant_performance_check = fail_trials_on_participant_performance_check
        self.propagate_failure = propagate_failure
        self.recruit_mode = recruit_mode
        self.target_num_participants = target_num_participants

        elts = join(
            ExperimentSetupRoutine(self.experiment_setup_routine),
            ParticipantFailRoutine(self.with_namespace(), self.participant_fail_routine),
            RecruitmentCriterion(self.with_namespace(), self.recruit_criterion),
            self.fail_old_trials_task,
            CodeBlock(self.init_participant),
            self._trial_loop(),
            CodeBlock(self.on_complete),
            self._check_performance_logic() if check_performance_at_end else None
        )
        super().__init__(label=self.with_namespace(), elts=elts)

    participant_progress_threshold = 0.1

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
        """Should return a Trial object."""
        raise NotImplementedError

    # How does fail participant know whether it's a premature exit or a performance check?

    def experiment_setup_routine(self, experiment):
        raise NotImplementedError

    trial_timeout_check_interval = 60
    trial_timeout_sec = 60

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
    def fail_old_trials_task(self):
        return BackgroundTask(
            self.with_namespace("fail_old_trials"), 
            self.fail_old_trials, 
            interval_sec=self.trial_timeout_check_interval
        )

        # This could go up a few levels in the hierarchy
    def recruit_criterion(self, experiment):
        """Should return True if more participants are required."""
        try:
            function = {
                None: self.null_criterion,
                "num_participants": self.num_participants_criterion,
                "num_trials": self.num_trials_criterion
            }[self.recruit_mode]
            return call_function(function, {"experiment": experiment})
        except KeyError:
            raise ValueError(f"Invalid recruitment mode: {self.recruit_mode}")

    @staticmethod
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
            if p.estimate_progress() > self.participant_progress_threshold
        ]
        
    def fail_old_trials(self):
        time_threshold = datetime.datetime.now() - datetime.timedelta(seconds=self.trial_timeout_sec)
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
        # pylint: disable=no-member
        db.session.commit()

    def init_participant(self, experiment, participant):
        # pylint: disable=unused-argument
        self.init_num_completed_trials_in_phase(participant)

    def on_complete(self, experiment, participant):
        raise NotImplementedError

    def finalise_trial(self, answer, trial, experiment, participant):
        # pylint: disable=unused-argument,no-self-use
        """This can be optionally customised, for example to add some more postprocessing."""
        trial.answer = answer
        trial.complete = True
        self.increment_num_completed_trials_in_phase(participant)

    def performance_check(self, experiment, participant, participant_trials):
        # pylint: disable=unused-argument
        """Should return a tuple (score: float, passed: bool)"""
        return (0, True)

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
        """Should return a test element or a sequence of test elements. Can be overridden."""
        return join(
            UnsuccessfulEndPage(failure_tags=["performance_check"])
        )

    def _check_performance_logic(self):
        def eval_checks(experiment, participant):
            participant_trials = self.get_participant_trials(participant)
            (score, passed) = self.performance_check(
                experiment=experiment, 
                participant=participant, 
                participant_trials=participant_trials
            )
            assert isinstance(score, (float, int))
            assert isinstance(passed, bool)
            participant.set_var(self.with_namespace("performance_check"), {
                "score": score,
                "passed": passed
            })
            return not passed

        return conditional(
            "performance_check",
            condition=eval_checks,
            logic_if_true=self.check_fail_logic(),
            fix_time_credit=False,
            log_chosen_branch=False
        )

    def get_participant_trials(self, participant):
        return self.trial_class.query.filter_by(participant_id=participant.id).all()

    def _prepare_trial(self, experiment, participant):
        trial = self.prepare_trial(experiment=experiment, participant=participant)
        if trial is not None:
            participant.var.current_trial = trial.id
        else:
            participant.var.current_trial = None
        experiment.save()

    def _show_trial(self, experiment, participant):
        trial = self._get_current_trial(participant)
        return trial.show_trial(experiment=experiment, participant=participant)

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
            logic_if_true=ReactivePage(
                lambda experiment, participant: (
                    self._get_current_trial(participant)
                        .show_feedback(experiment=experiment, participant=participant)
                ),
                time_allotted=0
            ), 
            fix_time_credit=False,
            log_chosen_branch=False
        )
        
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
                        time_allotted=self.time_allotted_per_trial
                    ),
                    CodeBlock(self._finalise_trial),
                    self._construct_feedback_logic(),
                    self._check_performance_logic() if self.check_performance_every_trial else None,
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
        participant.set_var(self.num_completed_trials_in_phase_var_id, value)

    def get_num_completed_trials_in_phase(self, participant):
        return participant.get_var(self.num_completed_trials_in_phase_var_id)

    def init_num_completed_trials_in_phase(self, participant):
        self.set_num_completed_trials_in_phase(participant, 0)

    def increment_num_completed_trials_in_phase(self, participant):
        self.set_num_completed_trials_in_phase(
            participant,
            self.get_num_completed_trials_in_phase(participant) + 1
        )

class NetworkTrialGenerator(TrialGenerator):
    """Trial generator for network-based experiments.
    The user should override find_network, grow_network, and find_node.
    They can also override create_trial if they want.
    Do not override prepare_trial.
    """

    def __init__(
        self,
        trial_class, 
        network_class,
        phase, 
        time_allotted_per_trial, 
        expected_num_trials,
        check_performance_at_end,
        check_performance_every_trial,
        fail_trials_on_premature_exit,
        fail_trials_on_participant_performance_check,
        # latest performance check is saved in as a participant variable (value, success)
        propagate_failure,
        recruit_mode,
        target_num_participants
    ):
        super().__init__(
            trial_class=trial_class, 
            phase=phase, 
            time_allotted_per_trial=time_allotted_per_trial, 
            expected_num_trials=expected_num_trials,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants
        )
        self.network_class = network_class

    #### The following methods are overwritten from TrialGenerator.
    #### Returns None if no trials could be found (this may not yet be supported by TrialGenerator)
    def prepare_trial(self, experiment, participant):
        logger.info("Preparing trial for participant %i.", participant.id)
        networks = self.find_networks(participant=participant, experiment=experiment)
        logger.info("Found %i network(s) for participant %i.", len(networks), participant.id)
        for network in networks:
            self.grow_network(network=network, participant=participant, experiment=experiment)
            node = self.find_node(network=network, participant=participant, experiment=experiment)
            if node is not None:
                logger.info("Attached node %i to participant %i.", node.id, participant.id)
                return self._create_trial(node=node, participant=participant, experiment=experiment)
        logger.info("Found no available nodes for participant %i, exiting.", participant.id)
        return None 

    def experiment_setup_routine(self, experiment):
        """Networks should be created here."""
        raise NotImplementedError
    
    ####

    def find_networks(self, participant, experiment):
        """
        Should return a list of all available networks for the participant's next trial, ordered 
        in preference (most preferred to least preferred).
        """
        raise NotImplementedError

    def grow_network(self, network, participant, experiment):
        """Should extend the network if necessary by adding one or more nodes."""
        raise NotImplementedError

    def find_node(self, network, participant, experiment):
        """Should find the node to which the participant should be attached for the next trial."""
        raise NotImplementedError

    def _create_trial(self, node, participant, experiment):
        trial = self.trial_class(experiment, node, participant, self.propagate_failure)
        experiment.session.add(trial)
        experiment.save()
        return trial

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

class TrialNetwork(Network):
    __mapper_args__ = {"polymorphic_identity": "trial_network"}

    trial_type = claim_field(1, str)

    def add_node(self, node):
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

    def __init__(self, trial_type, phase, experiment):
        # pylint: disable=unused-argument
        self.trial_type = trial_type
        self.phase = phase
        
    @property
    def num_nodes(self):
        return dallinger.models.Node.query.filter_by(network_id=self.id).count()

    @property
    def num_complete_trials(self):
        return Trial.query.filter_by(network_id=self.id, failed=False, complete=True).count()

