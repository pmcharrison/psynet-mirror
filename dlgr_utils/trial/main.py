import json

import dallinger.models
from dallinger.models import Info, Network

from ..field import claim_field

from ..timeline import (
    ReactivePage,
    CodeBlock,
    InfoPage,
    UnsuccessfulEndPage,
    ExperimentSetupRoutine,
    Module,
    conditional,
    while_loop,
    join
)

from sqlalchemy import String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import cast

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

# pylint: disable=unused-import
import rpdb

class Trial(Info):
    # pylint: disable=unused-argument
    __mapper_args__ = {"polymorphic_identity": "trial"}

    # Properties ###
    participant_id = claim_field(1, int)
    complete = claim_field(2, bool)
    answer = claim_field(3)

    # Refactor this bit with claim_field equivalent.
    @property
    def definition(self):
        return json.loads(self.contents)

    @definition.setter
    def definition(self, definition):
        self.contents = json.dumps(definition)

    #################

    def __init__(self, experiment, node, participant, definition):
        super().__init__(origin=node)
        self.participant_id = participant.id
        self.definition = definition

    def show_trial(self, experiment, participant):
        """Should return a Page object that returns an answer that can be stored in Trial.answer."""
        raise NotImplementedError

    def show_feedback(self, experiment, participant):
        """Should return a Page object displaying feedback (or None, which means no feedback)"""
        return None

    def gives_feedback(self, experiment, participant):
        return self.show_feedback(experiment=experiment, participant=participant) is not None

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
        phase, 
        time_allotted_per_trial, 
        expected_num_trials,
        check_performance_at_end,
        check_performance_every_trial
        # latest performance check is saved in as a participant variable (value, success)
    ):
        self.trial_class = trial_class
        self.trial_type = trial_class.__name__
        self.phase = phase
        self.time_allotted_per_trial = time_allotted_per_trial
        self.expected_num_trials = expected_num_trials
        self.check_performance_at_end = check_performance_at_end
        self.check_performance_every_trial = check_performance_every_trial

        elts = join(
            ExperimentSetupRoutine(self.experiment_setup_routine),
            CodeBlock(self.init_participant),
            self._trial_loop(),
            CodeBlock(self.on_complete),
            self._check_performance_logic() if check_performance_at_end else None
        )
        super().__init__(label=self.with_namespace(), elts=elts)

    def prepare_trial(self, experiment, participant):
        """Should return a Trial object."""
        raise NotImplementedError

    def experiment_setup_routine(self, experiment):
        raise NotImplementedError

    def init_participant(self, experiment, participant):
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
        """Should return a tuple (score: float, passed: bool)"""
        raise NotImplementedError

    def with_namespace(self, x=None, shared_between_phases=False):
        prefix = self.trial_type if shared_between_phases else f"{self.trial_type}__{self.phase}"
        if x is None:
            return prefix
        return f"{prefix}__{x}"

    def check_fail_logic(self):
        """Should return a test element or a sequence of test elements. Can be overridden."""
        return join(
            InfoPage(
                "Unfortunately you did not meet the performance criteria to continue in the experiment. "
                "You will still be paid for the time you spent already. "
                "Thank you for taking part!",
                time_allotted=0
            ),
            UnsuccessfulEndPage()
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
            experiment.session.add(trial)
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
            fix_time_credit=False
        )
        
    def _trial_loop(self):
        return join(
            CodeBlock(self._prepare_trial),
            while_loop(
                self.with_namespace("trial_loop"), 
                lambda experiment, participant: self._get_current_trial(participant) is not None,
                logic=join(
                    ReactivePage(self._show_trial, time_allotted=self.time_allotted_per_trial),
                    self._construct_feedback_logic(),
                    CodeBlock(self._finalise_trial),
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
        check_performance_at_end=False,
        check_performance_every_trial=False
        # latest performance check is saved in as a participant variable (value, success)
    ):
        super().__init__(
            trial_class=trial_class, 
            phase=phase, 
            time_allotted_per_trial=time_allotted_per_trial, 
            expected_num_trials=expected_num_trials,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial
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

    def init_participant(self, experiment, participant):
        raise NotImplementedError

    def on_complete(self, experiment, participant):
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
        trial = self.trial_class(experiment=experiment, node=node, participant=participant)
        return trial

    def count_networks(self):
        return (
            self.network_class.query
                              .filter_by(
                                  trial_type=self.trial_type,
                                  phase=self.phase
                                )   
                              .count()
        )

class TrialNetwork(Network):
    __mapper_args__ = {"polymorphic_identity": "trial_network"}

    trial_type = claim_field(1, str)

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

