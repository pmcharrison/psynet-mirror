from dallinger.models import Info

from .field import claim_field

from .timeline import (
    Page,
    InfoPage,
    CodeBlock,
    Module,
    join
)

class Trial(Info):
    participant_id = claim_field(1, int)
    answer = claim_field(2)

    stimulus_version = origin

    def __init__(self, experiment, node, participant):
        super().__init__(origin=node)
        self.participant_id = participant.id

    def show(self, experiment, participant):
        """Should return a Page object that returns an answer that can be stored in Trial.answer."""
        raise NotImplementedError

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

    def prepare_trial(self, experiment, participant):
        """Should return a Trial object."""
        raise NotImplementedError

    def finalise_trial(self, answer, trial, experiment, participant):
        """This can be optionally customised, for example to add some more postprocessing."""
        trial.answer = answer

    def experiment_setup_routine(self, experiment):
        pass

    def _prepare_trial(self, experiment, participant):
        trial = self.prepare_trial(experiment=experiment, participant=participant)
        experiment.session.add(trial)
        participant.var.current_trial = trial.id
        experiment.save()

    def _show_trial(self, experiment, participant):
        trial = self._get_current_trial(self, participant)
        return trial.show(experiment=experiment, participant=participant)

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
        return self.trial_class.query.get(trial_id)

    elts = join(
        ExperimentSetupRoutine(self),
        CodeBlock(self._prepare_trial),
        ReactivePage(self._show_trial),
        CodeBlock(self.finalise_trial)
    )

    def __init__(self, label, trial_class):
        self.label = label
        self.trial_class = trial_class

class NetworkTrialGenerator(TrialGenerator):
    """Trial generator for network-based experiments.
    The user should override find_network, grow_network, and find_node.
    They can also override create_trial if they want.
    Do not override prepare_trial.
    """

    #### The following method is overwritten from TrialGenerator.
    #### Returns None if no trials could be found (this may not yet be supported by TrialGenerator)
    def prepare_trial(self, experiment, participant):
        networks = self.find_networks(participant=participant, experiment=experiment)
        for network in networks:
            self.grow_network(network=network, participant=participant, experiment=experiment)
            node = self.find_node(network=network, participant=participant, experiment=experiment)
            if node is not None:
                return self._create_trial(node=node, participant=participant, experiment=experiment)
        return None 
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
        experiment.session.add(trial)
        experiment.save()
        return trial
