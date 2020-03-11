import dallinger.models

from .field import claim_field
from .trial import NetworkTrialGenerator

class NonAdaptiveTrialGenerator(NetworkTrialGenerator):
    """Nothing to override here."""

    def __init__(self, stimulus_set, namespace):
        self.namespace = namespace
        stimulus_set.create_networks

    def find_network(self, participant, experiment):
        """Should find the appropriate network for the participant's next trial."""
        raise NotImplementedError

    def grow_network(self, network, participant, experiment):
        """Should extend the network if necessary by adding one or more nodes."""
        raise NotImplementedError

    def find_node(self, network, participant, experiment):
        """Should find the node to which the participant should be attached for the next trial."""
        raise NotImplementedError

    def create_trial(self, node, participant, experiment):
        """Should create and return a trial object for the participant at the current node."""
        raise NotImplementedError

class NonAdaptiveNetwork(dallinger.models.Network):
    """A network corresponds to a block. Multiple networks may belong to a participant group."""
    
    __mapper_args__ = {"polymorphic_identity": "non_adaptive_network"}
    
    namespace = claim_field(1, str)
    participant_group = claim_field(2, str)
    block = claim_field(3, str)

    def __init__(self, namespace: str, role: str, participant_group: str, block: str):
        self.role = role
        self.participant_group = participant_group
        self.namespace = namespace

        if self.is_populated:
            self.populate()

    @property
    def is_populated(self):
        return dallinger.models.Node.query.filter_by(network_id=self.id).count() > 0

    def populate(self, stimulus_set, experiment):
        stimulus_specs = [
            x in stimulus_set.stimulus_specs 
            if x.role = self.role
            and x.participant_group == self.participant_group
            and x.block = self.block
        ]
        for stimulus_spec in stimulus_specs:
            stimulus = Stimulus(stimulus_spec, network=self)
            experiment.session.add(stimulus)
        experiment.save()


class Stimulus(dallinger.models.Node):
    __mapper_args__ = {"polymorphic_identity": "stimulus"}

    def __init__(stimulus_spec, network):
        assert network.role == stimulus_spec.role
        assert network.participant_group == stimulus_spec.participant_group
        assert network.block == stimulus_spec.block

        super().__init__(network=network)
        self.details = stimulus_spec.details

class StimulusSpec():
    def __init__(
        details,
        role,
        participant_group=None,
        block="default"
    ):
        self.details = details
        self.role = role
        self.participant_group = participant_group
        self.block = block

class StimulusSet():
    def __init__(self, stimulus_specs:
        assert isinstance(stimulus_specs, list)
        for s in stimulus_specs:
            assert isinstance(s, StimulusSpec)
        self.stimulus_specs = stimulus_specs
