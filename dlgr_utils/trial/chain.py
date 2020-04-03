import random
import datetime
from sqlalchemy import func
from sqlalchemy.sql.expression import not_

from typing import Optional, Union

from dallinger import db
import dallinger.models
import dallinger.nodes
import dallinger.networks

from ..field import claim_field, claim_var, VarStore
from .main import Trial, TrialNetwork, NetworkTrialMaker

# pylint: disable=unused-import
import rpdb

class ChainNetwork(TrialNetwork):
    """
    Implements a network in the form of a chain.
    Intended for use with :class:`~dlgr_utils.trial.chain.ChainTrialMaker`.
    Typically the user won't have to override anything here.
    
    """
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
        trials = self.completed_and_processed_trials.all()
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
        return self.completed_and_processed_trials.count() >= self.target_num_trials

    @property
    def completed_and_processed_trials(self):
        return Trial.query.filter_by(
            origin_id=self.id, failed=False, complete=True, awaiting_process=False
        )

    # TODO: we don't need 3 attributes here, just keep _query_completed_trials

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

class ChainTrialMaker(NetworkTrialMaker):
    """
    Administers a sequence of trials in a chain-based paradigm.
    This trial maker is suitable for implementing paradigms such as 
    Markov Chain Monte Carlo with People, iterated reproduction, and so on.
    It is intended for use with the following helper classes,
    which should be customised for the particular paradigm:
    
    * :class:`~dlgr_utils.trial.chain.ChainNetwork`;
      a special type of :class:`~dlgr_utils.trial.main.TrialNetwork` 

    * :class:`~dlgr_utils.trial.chain.ChainNode`;
      a special type of :class:`~dallinger.models.Node` 

    * :class:`~dlgr_utils.trial.chain.ChainTrial`;
      a special type of :class:`~dlgr_utils.trial.main.NetworkTrial` 

    * :class:`~dlgr_utils.trial.chain.ChainSource`;
      a special type of :class:`~dallinger.nodes.Source`, corresponding
      to the initial state of the network.
      
    A chain is initialised with a :class:`~dlgr_utils.trial.chain.ChainSource` object.
    This :class:`~dlgr_utils.trial.chain.ChainSource` object provides
    the initial seed to the chain. 
    The :class:`~dlgr_utils.trial.chain.ChainSource object is followed 
    by a series of :class:`~dlgr_utils.trial.chain.ChainNode` objects
    which are generated through the course of the experiment.
    The last :class:`~dlgr_utils.trial.chain.ChainNode` in the chain 
    represents the current state of the chain, and it determines the
    properties of the next trials to be drawn from that chain.
    A new :class:`~dlgr_utils.trial.chain.ChainNode` object is generated once 
    sufficient :class:`~dlgr_utils.trial.chain.ChainTrial` objects
    have been created for that :class:`~dlgr_utils.trial.chain.ChainNode`.
    There can be multiple chains in an experiment, with these chains
    either being owned by individual participants ("within-participant" designs)
    or shared across participants ("across-participant" designs).    
    
    The user will typically not have to override any methods or attributes in this class.
    
    Parameters 
    ----------

    source_class
        The class object for sources
        (should subclass :class:`~dlgr_utils.trial.chain.ChainSource`).
        
    trial_class
        The class object for trials administered by this maker
        (should subclass :class:`~dlgr_utils.trial.chain.ChainTrial`).

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".
    
    time_estimate_per_trial
        Time estimated for each trial (seconds).

    chain_type
        Either ``"within"`` for within-participant chains,
        or ``"across"`` for across-participant chains.
        
    num_trials_per_participant
        Maximum number of trials that each participant may complete;
        once this number is reached, the participant will move on
        to the next stage in the timeline.
    
    num_chains_per_participant
        Number of chains to be created for each participant;
        only relevant if ``chain_type="within"``.
    
    num_chains_per_experiment
        Number of chains to be created for the entire experiment;
        only relevant if ``chain_type="across"`
    
    num_nodes_per_chain
        Maximum number of nodes in the chain before the chain is marked as
        full and no more nodes will be added.
    
    trials_per_node
        Number of satisfactory trials to be received by the last node
        in the chain before another chain will be added.
        Most paradigms have this equal to 1.    
    
    active_balancing_across_chains
        Whether trial selection should be actively balanced across chains,
        such that trials are preferentially sourced from chains with 
        fewer valid trials.

    check_performance_at_end
        If ``True``, the participant's performance is 
        is evaluated at the end of the series of trials.
        
    check_performance_every_trial
        If ``True``, the participant's performance is 
        is evaluated after each trial.
        
    recruit_mode
        Selects a recruitment criterion for determining whether to recruit 
        another participant. The built-in criteria are ``"num_participants"``
        and ``"num_trials"``, though the latter requires overriding of 
        :attr:`~dlgr_utils.trial.main.TrialMaker.num_trials_still_required`.
        
    target_num_participants
        Target number of participants to recruit for the experiment. All 
        participants must successfully finish the experiment to count
        towards this quota. This target is only relevant if 
        ``recruit_mode="num_participants"``.
        
    async_post_trial
        Optional function to be run after a trial is completed by the participant.
        This should be specified as a fully qualified string, for example
        ``"dlgr_utils.trial.async_example.async_update_trial"``.
        This function should take one argument, ``trial_id``, corresponding to the
        ID of the relevant trial to process.
        ``trial.awaiting_process`` is set to ``True`` when the asynchronous process is
        initiated; the present method is responsible for setting ``trial.awaiting_process = False``
        once it is finished. It is also responsible for committing to the database
        using ``db.session.commit()`` once processing is complete
        (``db`` can be imported using ``from dallinger import db``).
        See the source code for ``dlgr_utils.trial.async_example.async_update_trial``
        for an example.
        
    async_post_grow_network
        Optional function to be run after a network is grown, only runs if
        :meth:`~dlgr_utils.trial.main.NetworkTrialMaker.grow_network` returns ``True``.
        This should be specified as a fully qualified string, for example
        ``dlgr_utils.trial.async_example.async_update_network``.
        This function should take one argument, ``network_id``, corresponding to the
        ID of the relevant network to process.
        ``network.awaiting_process`` is set to ``True`` when the asynchronous process is
        initiated; the present method is responsible for setting ``network.awaiting_process = False``
        once it is finished, and for committing to the database
        using ``db.session.commit()`` (``db`` can be imported using ``from dallinger import db``).
        See the source code for ``dlgr_utils.trial.async_example.async_update_trial``
        for a relevant example (for processing trials, not networks).
        
    fail_trials_on_premature_exit
        If ``True``, a participant's trials are marked as failed
        if they leave the experiment prematurely.
        Defaults to ``False`` because failing such trials can end up destroying
        large parts of existing chains.

    fail_trials_on_participant_performance_check
        If ``True``, a participant's trials are marked as failed
        if the participant fails a performance check.    
        Defaults to ``False`` because failing such trials can end up destroying
        large parts of existing chains.
        
    propagate_failure
        If ``True``, the failure of a trial is propagated to other
        parts of the experiment (the nature of this propagation is left up
        to the implementation).
        
    network_class
        The class object for the networks used by this maker.
        This should subclass :class`~dlgr_utils.trial.chain.ChainNetwork`,
        or alternatively be left at the default of 
        :class`~dlgr_utils.trial.chain.ChainNetwork`
        
        
    node_class
        The class object for the networks used by this maker.
        This should subclass :class`~dlgr_utils.trial.chain.ChainNode`,
        or alternatively be left at the default of 
        :class`~dlgr_utils.trial.chain.ChainNode`
    """
    def __init__(
        self,  
        source_class,
        trial_class, 
        phase: str,
        time_estimate_per_trial: Union[int, float],
        chain_type: str,
        num_trials_per_participant: int,
        num_chains_per_participant: Optional[int],
        num_chains_per_experiment: Optional[int],
        num_nodes_per_chain: int,
        trials_per_node: int,
        active_balancing_across_chains: bool, 
        check_performance_at_end: bool,
        check_performance_every_trial: bool,
        recruit_mode: str,
        target_num_participants=Optional[int],
        async_post_trial: Optional[str] = None, # this should be a string, for example "dlgr_utils.trial.async_example.async_update_network"
        async_post_grow_network: Optional[str] = None,
        fail_trials_on_premature_exit: bool = False,
        fail_trials_on_participant_performance_check: bool = False,
        propagate_failure: bool = True,
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
        self.time_estimate_per_trial = time_estimate_per_trial
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
            time_estimate_per_trial=time_estimate_per_trial, 
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
        participant.var.set(self.with_namespace("participated_networks"), [])

    def get_participated_networks(self, participant):
        return participant.var.get(self.with_namespace("participated_networks"))

    def add_to_participated_networks(self, participant, network_id):
        networks = self.get_participated_networks(participant)
        networks.append(network_id)
        participant.var.set(self.with_namespace("participated_networks"), networks)

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
