import random
import datetime
from sqlalchemy import func
from sqlalchemy.sql.expression import not_

from typing import Optional

from dallinger import db
import dallinger.models
import dallinger.nodes
import dallinger.networks

from ..field import claim_field, claim_var, VarStore
from .main import Trial, TrialNetwork, NetworkTrialGenerator

# pylint: disable=unused-import
import rpdb

class ChainNetwork(TrialNetwork):
    # pylint: disable=abstract-method
    __mapper_args__ = {"polymorphic_identity": "chain_network"}

    participant_id = claim_field(4, int)
    id_within_participant = claim_field(5, int)

    chain_type = claim_var("_chain_type")
    trials_per_node = claim_var("_trials_per_node")

    # Note - the <details> slot is occupied by VarStore.

    def __init__(
        self, 
        trial_type, 
        source_class, 
        phase, 
        experiment, 
        chain_type, 
        trials_per_node, 
        target_num_nodes,
        participant=None, 
        id_within_participant=None
    ):
        super().__init__(trial_type, phase, experiment)
        experiment.session.add(self)
        experiment.save()

        if participant is not None:
            self.id_within_participant = id_within_participant
            self.participant_id = participant.id

        self.chain_type = chain_type
        self.trials_per_node = trials_per_node
        self.target_num_nodes = target_num_nodes
        self.add_source(source_class, experiment, participant)
        self.target_num_trials = target_num_nodes * trials_per_node
        
        experiment.save()

    @property
    def target_num_nodes(self):
        # Subtract 1 to account for the source
        return self.max_size - 1

    @target_num_nodes.setter
    def target_num_nodes(self, target_num_nodes):
        self.max_size = target_num_nodes + 1

    @property
    def num_nodes(self):
        return ChainNode.query.filter_by(network_id=self.id, failed=False).count()

    @property
    def degree(self):
        if self.num_nodes == 0:
            return 0
        return (
            db.session
                .query(func.max(ChainNode.degree))
                .filter_by(network_id=self.id, failed=False)
                .scalar()
        )

    @property
    def source(self):
        return ChainSource.query.filter_by(network_id=self.id).one()

    @property
    def head(self):
        if self.num_nodes == 0:
            return self.source
        else: 
            degree = self.degree
            return self.get_node_with_degree(degree)

    def get_node_with_degree(self, degree):
        assert degree >= 0
        if degree == 0:
            return self.source
        return ChainNode.query.filter_by(degree=degree, network_id=self.id, failed=False).one()

    def add_node(self, node):
        if node.degree > 0:
            previous_head = self.get_node_with_degree(node.degree - 1)
            previous_head.connect(whom=node)
            previous_head.child = node
        if self.num_nodes >= self.target_num_nodes:
            self.full = True

    def add_source(self, source_class, experiment, participant=None):
        source = source_class(self, experiment, participant)
        experiment.session.add(source)
        self.add_node(source)
        experiment.save()

    @property
    def num_trials_still_required(self):
        assert self.target_num_trials is not None
        return self.target_num_trials - self.num_completed_trials

class ChainNode(dallinger.models.Node):
    __mapper_args__ = {"polymorphic_identity": "chain_node"}

    def __init__(self, seed, degree, network, experiment, propagate_failure, participant=None):
        # pylint: disable=unused-argument
        super().__init__(network=network, participant=participant)
        self.seed = seed
        self.degree = degree
        self.definition = self.create_definition_from_seed(seed, experiment, participant)
        self.propagate_failure = propagate_failure

    def create_definition_from_seed(self, seed, experiment, participant):
        raise NotImplementedError

    def create_seed(self, experiment, participant):
        trials = self.completed_trials
        return self.summarise_trials(trials, experiment, participant)

    def summarise_trials(self, trials, experiment, participant):
        raise NotImplementedError

    degree = claim_field(1, int)
    child_id = claim_field(2, int)
    seed = claim_field(3)
    definition = claim_field(4)    

    propagate_failure = claim_var("propagate_failure")

    # VarStore occuppies the <details> slot.
    @property
    def var(self):
        return VarStore(self)

    @property
    def source(self):
        return self.network.source

    @property
    def child(self):
        if self.child_id is None:
            return None
        return ChainNode.query.filter_by(id=self.child_id).one()

    @child.setter
    def child(self, child):
        self.child_id = child.id

    @property 
    def phase(self):
        return self.network.phase

    @property 
    def target_num_trials(self):
        return self.network.trials_per_node

    @property 
    def ready_to_spawn(self):
        return self.num_completed_trials >= self.target_num_trials

    @property 
    def _query_completed_trials(self):
        return Trial.query.filter_by(
            origin_id=self.id, failed=False, complete=True
        )

    @property 
    def completed_trials(self):
        return self._query_completed_trials.all()

    @property
    def num_completed_trials(self):
        return self._query_completed_trials.count()

    @property
    def num_viable_trials(self):
        return Trial.query.filter_by(origin_id=self.id, failed=False).count()

    def fail(self):
        if not self.failed:
            self.failed = True
            self.time_of_death = datetime.datetime.now()
            self.network.calculate_full()
            if self.propagate_failure:
                for i in self.infos():
                    i.fail()

class ChainSource(dallinger.nodes.Source):
    # pylint: disable=abstract-method
    __mapper_args__ = {"polymorphic_identity": "chain_source"}

    ready_to_spawn = True
    seed = claim_field(1)

    degree = 0

    @property
    def var(self): # occupies the <details> attribute
        return VarStore(self)

    def __init__(self, network, experiment, participant):
        super().__init__(network, participant)
        self.seed = self.generate_seed(network, experiment, participant)

    def create_seed(self, experiment, participant):
        # pylint: disable=unused-argument
        return self.seed

    def generate_seed(self, network, experiment, participant):
        raise NotImplementedError
        

class ChainTrial(Trial):
    # pylint: disable=abstract-method
    __mapper_args__ = {"polymorphic_identity": "chain_trial"}

    @property
    def node(self):
        return self.origin

    @property
    def source(self):
        return self.node.source

    @property 
    def phase(self):
        return self.node.phase  

    def fail(self):
        if not self.failed:
            self.failed = True
            self.time_of_death = datetime.datetime.now()
            if self.propagate_failure:
                self.fail_descendants()

    def fail_descendants(self):
        """We fail the child node of the current node, since that will have been 
        created with reference to the failed trial."""
        node = self.node
        child_node = node.child
        if child_node is not None:
            child_node.fail()

class ChainTrialGenerator(NetworkTrialGenerator):
    def __init__(
        self,  
        source_class,
        trial_class, 
        phase,
        time_allotted_per_trial,
        chain_type,
        num_trials_per_participant,
        num_chains_per_participant,
        num_chains_per_experiment,
        num_nodes_per_chain,
        trials_per_node,
        active_balancing_across_chains, 
        check_performance_at_end,
        check_performance_every_trial,
        recruit_mode,
        target_num_participants=None,
        async_post_trial: Optional[str] = None, # this should be a string, for example "dlgr_utils.trial.async_example.async_update_network"
        async_post_grow_network: Optional[str] = None,
        fail_trials_on_premature_exit=False,
        fail_trials_on_participant_performance_check=False,
        propagate_failure=True,
        network_class=ChainNetwork,
        node_class=ChainNode
    ):
        assert chain_type in ["within", "across"]

        if chain_type == "across" and num_trials_per_participant > num_chains_per_experiment:
            raise ValueError(
                "In across-chain experiments, <num_trials_per_participant> "
                "cannot exceed <num_chains_per_experiment>."
            )

        self.node_class = node_class
        self.source_class = source_class
        self.trial_class = trial_class
        self.phase = phase
        self.time_allotted_per_trial = time_allotted_per_trial
        self.chain_type = chain_type
        self.num_trials_per_participant = num_trials_per_participant
        self.num_chains_per_participant = num_chains_per_participant
        self.num_chains_per_experiment = num_chains_per_experiment
        self.num_nodes_per_chain = num_nodes_per_chain
        self.trials_per_node = trials_per_node
        self.active_balancing_across_chains = active_balancing_across_chains
        self.check_performance_at_end = check_performance_at_end
        self.check_performance_every_trial = check_performance_every_trial
        self.propagate_failure = propagate_failure

        super().__init__(
            trial_class, 
            network_class=network_class,
            phase=phase,
            time_allotted_per_trial=time_allotted_per_trial, 
            expected_num_trials=num_trials_per_participant,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants,
            async_post_trial=async_post_trial,
            async_post_grow_network=async_post_grow_network
        )
    
    def init_participant(self, experiment, participant):
        super().init_participant(experiment, participant)
        self.init_participated_networks(participant)
        if self.chain_type == "within":
            self.create_networks_within(experiment, participant)

    @property
    def num_trials_still_required(self):
        assert self.chain_type == "across"
        return sum([network.num_trials_still_required for network in self.networks])

    # def fail_trial(self, trial):
    #     if not trial.failed:
    #         trial.fail()
    #     if self.propagate_failure_to_descendants:
    #         current_node = trial.origin
    #         child_node = current_node.child
    #         if child_node:
    #             self.fail_node(child_node)

    # def fail_node(self, node):
    #     if not node.failed:
    #         node.fail()
           
    #### Participated networks
    def init_participated_networks(self, participant):
        participant.set_var(self.with_namespace("participated_networks"), [])

    def get_participated_networks(self, participant):
        return participant.get_var(self.with_namespace("participated_networks"))

    def add_to_participated_networks(self, participant, network_id):
        networks = self.get_participated_networks(participant)
        networks.append(network_id)
        participant.set_var(self.with_namespace("participated_networks"), networks)

    def experiment_setup_routine(self, experiment):
        if self.num_networks == 0 and self.chain_type == "across":
            self.create_networks_across(experiment)

    def create_networks_within(self, experiment, participant):
        for i in range(self.num_chains_per_participant):
            self.create_network(experiment, participant, id_within_participant=i)

    def create_networks_across(self, experiment):
        for _ in range(self.num_chains_per_experiment):
            self.create_network(experiment)

    def create_network(self, experiment, participant=None, id_within_participant=None):
        network = self.network_class(
            trial_type=self.trial_type,
            source_class=self.source_class,
            phase=self.phase,
            experiment=experiment,
            chain_type=self.chain_type,
            trials_per_node=self.trials_per_node,
            target_num_nodes=self.num_nodes_per_chain,
            participant=participant,
            id_within_participant=id_within_participant
        )
        experiment.session.add(network)
        experiment.save()
        self._grow_network(network, participant, experiment)
        return network
    
    def on_complete(self, experiment, participant):
        pass

    def find_networks(self, participant, experiment):
        if self.get_num_completed_trials_in_phase(participant) >= self.num_trials_per_participant:
            return []

        networks = self.network_class.query.filter_by(
            trial_type=self.trial_type,
            phase=self.phase,
            full=False,
            awaiting_process=False
        )

        if self.chain_type == "within":
            networks = self.filter_by_participant_id(networks, participant)
        elif self.chain_type == "across":
            networks = self.exclude_participated(networks, participant)

        networks = networks.all()

        if self.active_balancing_across_chains:    
            networks.sort(key=lambda network: network.num_completed_trials)
        else:
            random.shuffle(networks)

        return networks

    @staticmethod
    def filter_by_participant_id(networks, participant):
        return networks.filter_by(participant_id=participant.id)

    def exclude_participated(self, networks, participant):
        return networks.filter(
            not_(self.network_class.id.in_(self.get_participated_networks(participant)))
        )
    
    def grow_network(self, network, participant, experiment):
        head = network.head
        if head.ready_to_spawn:
            seed = head.create_seed(participant, experiment)
            node = self.node_class(seed, head.degree + 1, network, experiment, self.propagate_failure, participant)
            experiment.session.add(node)
            network.add_node(node)
            return True
        return False

    def find_node(self, network, participant, experiment): 
        head = network.head
        if head.num_viable_trials >= self.trials_per_node:
            return None
        return head

    def finalise_trial(self, answer, trial, experiment, participant):
        super().finalise_trial(answer, trial, experiment, participant)
        self.add_to_participated_networks(participant, trial.network_id)
