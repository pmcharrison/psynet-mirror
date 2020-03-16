from dallinger.models import Info

from ..field import claim_field

from ..timeline import (
    ReactivePage,
    CodeBlock,
    ExperimentSetupRoutine,
    Module,
    conditional,
    while_loop,
    join
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

import rpdb

class Trial(Info):
    # pylint: disable=unused-argument
    __mapper_args__ = {"polymorphic_identity": "trial"}

    participant_id = claim_field(1, int)
    answer = claim_field(2)

    def __init__(self, experiment, node, participant):
        super().__init__(origin=node)
        self.participant_id = participant.id

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

    def __init__(self, trial_class, phase, time_allotted_per_trial, expected_num_trials):
        self.trial_class = trial_class
        self.trial_type = trial_class.__name__
        self.phase = phase
        self.time_allotted_per_trial = time_allotted_per_trial
        self.expected_num_trials = expected_num_trials

        elts = join(
            ExperimentSetupRoutine(self.experiment_setup_routine),
            CodeBlock(self.init_participant),
            self._trial_loop(),
            CodeBlock(self.on_complete)
        )
        super().__init__(label=self.with_namespace(), elts=elts)

    def prepare_trial(self, experiment, participant):
        """Should return a Trial object."""
        raise NotImplementedError

    def experiment_setup_routine(self, experiment):
        raise NotImplementedError

    def init_participant(self, experiment, participant):
        raise NotImplementedError

    def on_complete(self, experiment, participant):
        raise NotImplementedError

    def finalise_trial(self, answer, trial, experiment, participant):
        # pylint: disable=unused-argument,no-self-use
        """This can be optionally customised, for example to add some more postprocessing."""
        trial.answer = answer

    def with_namespace(self, x=None, shared_between_phases=False):
        prefix = self.trial_type if shared_between_phases else f"{self.trial_type}__{self.phase}"
        if x is None:
            return prefix
        return f"{prefix}__{x}"

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
                    CodeBlock(self._prepare_trial)
                ),
                expected_repetitions=self.expected_num_trials,
                fix_time_credit=False
            ),
        )

class NetworkTrialGenerator(TrialGenerator):
    """Trial generator for network-based experiments.
    The user should override find_network, grow_network, and find_node.
    They can also override create_trial if they want.
    Do not override prepare_trial.
    """

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
