import dallinger.models

from .field import claim_field
from .trial import NetworkTrialGenerator

# def _count_non_adaptive_networks():
# def _non_adaptive_experiment_setup_routine(experiment):

class NonAdaptiveTrialGenerator(NetworkTrialGenerator):
    def __init__(self, stimulus_set, namespace, max_repetitions=1):
        self.stimulus_set = stimulus_set
        self.namespace = namespace
        self.max_repetitions = max_repetitions

    def count_networks(self):
        return NonAdaptiveNetwork.query \
                                 .filter_by(namespace=self.namespace)
                                 .count()

    def experiment_setup_routine(self, experiment):
        if self.count_networks > 0:
            self.create_networks(experiment)

    def create_networks(self, experiment):
        for network_spec in stimulus_set.network_specs:
            network_spec.create_network(namespace)
        experiment.save()
        
    def find_network(self, participant, experiment):
        """Should find the appropriate network for the participant's next trial."""
        networks = NonAdaptiveNetwork.query \
                                     .filter_by(
                                        namespace=self.namespace,
                                        participant_group=participant.var.participant_group,
                                        phase=participant.var.phase,
                                        block=participant.var.block # need to make sure we increment block if no space left
                                     ).all()
        assert len(networks) == 1
        return networks[0]

    def grow_network(self, network, participant, experiment):
        """Networks never get expanded in a non-adaptive experiment."""
        pass

    def find_node(self, network, participant, experiment):
        """Should find the node (i.e. stimulus) to which the participant should be attached for the next trial."""
        stimulus_counts = participant.var.stimulus_counts

        # STUFF MISSING HERE

        completed_stimuli = tuple(participant.var.stimulus_counts)
        candidates = Stimulus.query \
                             .filter_by(network_id=network.id)
                             .filter(not_(Stimulus.id._in(completed_stimuli)))

        raise NotImplementedError

    def create_trial(self, node, participant, experiment):
        """Should create and return a trial object for the participant at the current node."""
        raise NotImplementedError

# def with_namespace(label, namespace):
#     return f"__{namespace}__{label}"

class NonAdaptiveNetwork(dallinger.models.Network):
    """
    A network corresponds to a unique combination of namespace, role, participant group, and block.
    """
    
    __mapper_args__ = {"polymorphic_identity": "non_adaptive_network"}
    
    namespace = claim_field(1, str)
    participant_group = claim_field(2, str)
    block = claim_field(3, str)
    
    phase = role

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

        network_specs = set()
        
        for s in stimulus_specs:
            assert isinstance(s, StimulusSpec)
            network_specs.add((
                s.role,
                s.participant_group, 
                s.block
            ))

        self.stimulus_specs = stimulus_specs

        self.network_specs = [
            NetworkSpec(
                role=x[0],
                participant_group=x[1], 
                block=x[2]
            )
            for x in network_specs
        ]

class NetworkSpec():
    def __init__(self, role, participant_group, block):
        self.role = role
        self.participant_group = participant_group
        self.block = block

    def create_network(self, namespace, experiment):
        network = NonAdaptiveNetwork(
            namespace=namespace,
            role=self.role,
            participant_group=self.participant_group,
            block=self.block
        )
        experiment.session.add(network)
