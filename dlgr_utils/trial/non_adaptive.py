import random
from statistics import mean

from sqlalchemy.sql.expression import not_

import dallinger.models

from ..field import claim_field
from .main import Trial, NetworkTrialGenerator

class NonAdaptiveTrial(Trial):
    # Refactor this bit with claim_field equivalent.
    @property
    def definition(self):
        return self.contents

    @definition.setter
    def definition(self, definition):
        self.contents = definition

    @property
    def stimulus_version(self):
        return self.origin

    @property
    def stimulus(self):
        return self.origin.origin

    def __init__(self, experiment, node, participant):
        super().__init__(origin=node)
        self.participant_id = participant.id
        self.definition = {
            **self.stimulus.definition, 
            **self.stimulus_version.definition
        }

    def show_trial(self, experiment, participant):
        """Should return a Page object that returns an answer that can be stored in Trial.answer."""
        raise NotImplementedError

    def show_feedback(self, experiment, participant):
        """Should return a Page object displaying feedback (or None, which means no feedback)"""
        return None

class NonAdaptiveTrialGenerator(NetworkTrialGenerator):
    def __init__(
        self,  
        trial_class, 
        phase,
        stimulus_set,
        time_allotted_per_trial,
        expected_num_trials: int,
        new_participant_group: bool
    ):
        super().__init__(trial_class, phase, time_allotted_per_trial, expected_num_trials)
        self.stimulus_set = stimulus_set
        self.new_participant_group = new_participant_group

    def init_participant(self, experiment, participant):
        self.init_block_order(experiment, participant)
        self.init_participant_group(experiment, participant)

    def init_block_order(self, experiment, participant):
        participant.new_var(
            self.with_namespace("block_order"),
            self.choose_block_order(experiment=experiment, participant=participant)
        )

    def init_participant_group(self, experiment, participant):
        var_id = self.with_namespace("participant_group", shared_between_phases=True)
        if self.new_participant_group:
            participant.new_var(var_id, self.assign_participant_group(experiment=experiment, participant=participant))
        else:
            if not participant.has_var(var_id):
                raise ValueError("<assign_participant_group> was False but the participant hasn't yet been assigned to a group.")

    def on_complete(self, experiment, participant):
        pass

    def experiment_setup_routine(self, experiment):
        if self.count_networks() > 0:
            self.create_networks(experiment)

    def choose_block_order(self, experiment, participant):
        # pylint: disable=unused-argument
        """
        By default this function shuffles the blocks randomly for each participant. 
        Override it for alternative behaviour.
        """
        blocks = self.stimulus_set.blocks
        random.shuffle(blocks)
        return blocks

    def assign_participant_group(self, experiment, participant):
        # pylint: disable=unused-argument
        """
        By default this function randomly chooses from the available participant groups. 
        Override it for alternative behaviour.
        """
        participant_groups = self.stimulus_set.participant_groups
        return random.choice(participant_groups)

    def count_networks(self):
        return (
            NonAdaptiveNetwork.query
                              .filter_by(trial_type=self.trial_type)
                              .count()
        )

    def create_networks(self, experiment):
        for network_spec in self.stimulus_set.network_specs:
            network_spec.create_network(trial_type=self.trial_type)
        experiment.save()
        
    def find_networks(self, participant, experiment):
        # pylint: disable=protected-access
        """Should find the appropriate network for the participant's next trial."""
        block_order = participant.get_var(self.with_namespace("block_order"))
        networks = (
            NonAdaptiveNetwork.query
                              .filter_by(
                                  trial_type=self.trial_type,
                                  participant_group=participant.var.participant_group,
                                  phase=participant.var.phase
                              )
                              .filter(NonAdaptiveNetwork.block._in(tuple(block_order)))
                              .all()
        )
        networks.sort(key=lambda network: block_order.index(network.block))
        return networks

    def grow_network(self, network, participant, experiment):
        """Networks never get expanded in a non-adaptive experiment."""

    def find_node(self, network, participant, experiment):
        """Should find the node (i.e. stimulus) to which the participant should be attached for the next trial."""
        stimulus = self.find_stimulus(network, participant, experiment)
        if stimulus is None:
            return None
        else:
            return self.find_stimulus_version(stimulus, participant, experiment)

    def find_stimulus(self, network, participant, experiment):
        # pylint: disable=unused-argument,protected-access
        completed_stimuli = tuple(participant.var.completed_stimuli)
        candidates = (
            Stimulus.query
                    .filter_by(network_id=network.id)
                    .filter(not_(Stimulus.id._in(completed_stimuli)))
                    .all()
        )
        if len(candidates) == 0:
            return None
        else: 
            return random.choice(candidates)

    def find_stimulus_version(self, stimulus, participant, experiment):
        # pylint: disable=unused-argument
        candidates = (
            StimulusVersion.query
                           .filter_by(stimulus_id=stimulus.id)
                           .all()
        )
        assert len(candidates) > 0
        return random.choice(candidates)

class NonAdaptiveNetwork(dallinger.models.Network):
    """
    A network corresponds to a unique combination of trial_type, phase, participant group, and block.
    """
    #pylint: disable=abstract-method
    
    __mapper_args__ = {"polymorphic_identity": "non_adaptive_network"}
    
    trial_type = claim_field(1, str)
    participant_group = claim_field(2, str)
    block = claim_field(3, str)
    
    @property 
    def phase(self):
        return self.role

    @phase.setter
    def phase(self, value):
        self.role = value

    def __init__(self, trial_type, phase, participant_group, block, stimulus_set, experiment):
        self.trial_type = trial_type
        self.phase = phase
        self.participant_group = participant_group
        self.block = block

        if not self.is_populated:
            self.populate(stimulus_set, experiment)

    @property
    def is_populated(self):
        return dallinger.models.Node.query.filter_by(network_id=self.id).count() > 0

    def populate(self, stimulus_set, experiment):
        stimulus_specs = [
            x for x in stimulus_set.stimulus_specs 
            if x.phase == self.phase
            and x.participant_group == self.participant_group
            and x.block == self.block
        ]
        for stimulus_spec in stimulus_specs:
            stimulus_spec.add_stimulus_to_network(network=self, experiment=experiment)
        experiment.save()


class Stimulus(dallinger.models.Node):
    __mapper_args__ = {"polymorphic_identity": "stimulus"}

    @property
    def definition(self):
        return self.details

    @definition.setter
    def definition(self, definition):
        self.details = definition

    def __init__(self, stimulus_spec, network):
        assert network.phase == stimulus_spec.phase
        assert network.participant_group == stimulus_spec.participant_group
        assert network.block == stimulus_spec.block

        super().__init__(network=network)
        self.definition = stimulus_spec.definition

class StimulusSpec():
    def __init__(
        self, 
        definition,
        version_specs,
        phase,
        participant_group="default",
        block="default"
    ):
        assert isinstance(definition, dict)
        assert isinstance(version_specs, list)
        assert len(version_specs) > 0
        for version_spec in version_specs:
            assert isinstance(version_spec, StimulusVersionSpec)

        self.definition = definition
        self.version_specs = version_specs
        self.phase = phase
        self.participant_group = participant_group
        self.block = block

    def add_stimulus_to_network(self, network, experiment):
        stimulus = Stimulus(self, network=network)
        experiment.session.add(stimulus)
        
        for version_spec in self.version_specs:
            version = StimulusVersion(version_spec, stimulus, network)
            experiment.session.add(version)

class StimulusVersion(dallinger.models.Node):
    __mapper_args__ = {"polymorphic_identity": "stimulus_version"}

    stimulus_id = claim_field(1, int)

    def __init__(self, stimulus_version_spec, stimulus, network):
        super().__init__(network=network)
        self.stimulus_id = stimulus.id
        self.definition = stimulus_version_spec.definition

    def connect_to_parent(self, parent):
        self.connect(parent, direction="from")

class StimulusVersionSpec():
    def __init__(self, definition):
        assert isinstance(definition, dict)
        self.definition = definition

class StimulusSet():
    def __init__(self, stimulus_specs):
        assert isinstance(stimulus_specs, list)

        self.stimulus_specs = stimulus_specs

        network_specs = set()
        self.blocks = set()
        self.num_trials_by_participant_group = dict()
        self.participant_groups = set()
        
        for s in stimulus_specs:
            assert isinstance(s, StimulusSpec)
            network_specs.add((
                s.phase,
                s.participant_group, 
                s.block
            ))

            self.blocks.add(s.block)
            self.participant_groups.add(s.participant_group)
            
            if s.participant_group in self.num_trials_by_participant_group:
                self.num_trials_by_participant_group[s.participant_group] += 1
            else:
                self.num_trials_by_participant_group[s.participant_group] = 1

        self.network_specs = [
            NetworkSpec(
                phase=x[0],
                participant_group=x[1], 
                block=x[2],
                stimulus_set=self
            )
            for x in network_specs
        ]

    def estimate_num_trials_per_participant(self):
        return mean([x for x in self.num_trials_by_participant_group.values()])

class NetworkSpec():
    def __init__(self, phase, participant_group, block, stimulus_set):
        self.phase = phase
        self.participant_group = participant_group
        self.block = block
        self.stimulus_set = stimulus_set # note: this includes stimuli outside this network too!

    def create_network(self, trial_type, experiment):
        network = NonAdaptiveNetwork(
            trial_type=trial_type,
            phase=self.phase,
            participant_group=self.participant_group,
            block=self.block,
            stimulus_set=self.stimulus_set,
            experiment=experiment
        )
        experiment.session.add(network)
