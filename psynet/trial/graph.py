# pylint: disable=unused-argument,abstract-method

from .chain import ChainNetwork, ChainNode, ChainSource, ChainTrial, ChainTrialMaker
import json
from typing import Optional, Union, List
from dallinger import db

from trial.main import with_trial_maker_namespace
# from .utils import (
#     import_local_experiment,
# )


class GraphChainNetwork(ChainNetwork):
    """
    A Network class for graph chains.
    """

    __mapper_args__ = {"polymorphic_identity": "graph_chain_network"}

    def __init__(
        self,
        trial_maker_id: str,
        source_class,
        phase: str,
        experiment,
        chain_type: str,
        vertex_id: int,  # Unique vertex id specifying the location of the network vertex within the graph
        dependent_vertex_ids: List[int],  # vertices which the current vertex depends on (incoming)
        trials_per_node: int,
        target_num_nodes: int,
        participant=None,
        id_within_participant: Optional[int] = None,
    ):
        super().__init__(trial_maker_id, phase, experiment)
        db.session.add(self)
        db.session.commit()

        if participant is not None:
            self.id_within_participant = id_within_participant
            self.participant_id = participant.id

        self.chain_type = chain_type
        self.trials_per_node = trials_per_node
        self.target_num_nodes = target_num_nodes
        # The last node in the chain doesn't receive any trials
        self.target_num_trials = (target_num_nodes - 1) * trials_per_node
        self.definition = self.make_definition()
        self.participant_group = self.get_participant_group()
        self.add_source(source_class, experiment, participant)
        self.vertex_id = vertex_id
        self.dependent_vertex_ids = dependent_vertex_ids

        self.validate()

        experiment.save()

    def make_definition(self):
        return {}


class GraphChainTrial(ChainTrial):
    """
    A Trial class for graph chains.
    """

    __mapper_args__ = {"polymorphic_identity": "graph_chain_trial"}

    def make_definition(self, experiment, participant):
        """
        (Built-in)
        In an graph chain, the trial's definition equals the definition of
        the node that created it.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            Optional participant with which to associate the trial.

        Returns
        -------

        object
            The trial's definition, equal to the node's definition.
        """
        return self.node.definition


class GraphChainNode(ChainNode):
    """
    A Node class for graph chains.
    """

    __mapper_args__ = {"polymorphic_identity": "graph_chain_node"}

    def create_definition_from_seed(self, seed, experiment, participant):
        """
        (Built-in)
        In an graph chain, the next node in the chain
        is a faithful reproduction of the previous iteration.

        Parameters
        ----------

        seed
            The seed being passed to the node.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            Current participant, if relevant.

        Returns
        -------

        object
            The node's new definition, which is a faithful reproduction of the seed
            that it was passed.
        """
        # The next node in the chain is a faithful reproduction of the previous iteration.
        return seed

    def summarize_trials(self, trials: list, experiment, participant):
        """
        (Abstract method, to be overridden)
        This method should summarize the answers to the provided trials.
        A default method is implemented for cases when there is
        just one trial per node; in this case, the method
        extracts and returns the trial's answer, available in ``trial.answer``.
        The method must be extended if it is to cope with multiple trials per node,
        however.

        Parameters
        ----------

        trials
            Trials to be summarized. By default only trials that are completed
            (i.e. have received a response) and processed
            (i.e. aren't waiting for an asynchronous process)
            are provided here.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            The participant who initiated the creation of the node.

        Returns
        -------

        object
            The derived seed. Should be suitable for serialisation to JSON.
        """

        if len(trials) == 1:
            return trials[0].answer
        raise NotImplementedError

    @property
    def ready_to_spawn(self):
        parents = self.get_parent_nodes()
        if (len(parents) < len(self.network.dependent_vertex_ids)):
            return False
        else:
            all_parents_ready = all([self.is_ready(p) for p in parents])
            current_vertex_ready = self.is_ready(self)
            return all_parents_ready and current_vertex_ready

    def get_parent_nodes(self):
        return NotImplementedError  # CONTINUE HERE!

    def is_ready(self, node):
        return node.completed_and_processed_trials.count() >= node.target_num_trials


class GraphChainSource(ChainSource):
    """
    A Source class for graph chains.
    """

    __mapper_args__ = {"polymorphic_identity": "graph_chain_source"}

    def generate_seed(self, network, experiment, participant):
        raise NotImplementedError


class GraphChainTrialMaker(ChainTrialMaker):
    """
    A TrialMaker class for graph chains;
    see the documentation for
    :class:`~psynet.trial.chain.ChainTrialMaker`
    for usage instructions.
    """

    def __init__(
        self,
        *,
        id_,
        network_class,
        node_class,
        source_class,
        trial_class,
        phase: str,
        time_estimate_per_trial: Union[int, float],
        network_structure: str,
        chain_type: str,
        num_trials_per_participant: int,
        num_chains_per_participant: Optional[int],
        # num_chains_per_experiment: Optional[int],
        trials_per_node: int,
        balance_across_chains: bool,
        check_performance_at_end: bool,
        check_performance_every_trial: bool,
        recruit_mode: str,
        target_num_participants=Optional[int],
        num_iterations_per_chain: Optional[int] = None,
        num_nodes_per_chain: Optional[int] = None,
        fail_trials_on_premature_exit: bool = False,
        fail_trials_on_participant_performance_check: bool = False,
        propagate_failure: bool = True,
        num_repeat_trials: int = 0,
        wait_for_networks: bool = False,
        allow_revisiting_networks_in_across_chains: bool = False,
    ):
        if chain_type == "within":
            raise NotImplementedError  # UNCLEAR TO ME HOW TO UNITE THE ON-DEMAND CREATION OF WITHIN NETS AND THE PRE-DFINED GRAPH NETWORK STRUCTURE
        num_chains_per_experiment = len(json.loads(network_structure)["vertices"])
        super().__init__(
            id_=id_,
            network_class=network_class,
            node_class=node_class,
            source_class=source_class,
            trial_class=trial_class,
            phase=phase,
            time_estimate_per_trial=time_estimate_per_trial,
            chain_type=chain_type,
            num_trials_per_participant=num_trials_per_participant,
            num_chains_per_participant=num_chains_per_participant,
            num_chains_per_experiment=num_chains_per_experiment,
            trials_per_node=trials_per_node,
            balance_across_chains=balance_across_chains,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants,
            num_iterations_per_chain=num_iterations_per_chain,
            num_nodes_per_chain=num_nodes_per_chain,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            num_repeat_trials=num_repeat_trials,
            wait_for_networks=wait_for_networks,
            allow_revisiting_networks_in_across_chains=allow_revisiting_networks_in_across_chains
        )

    def experiment_setup_routine(self, experiment):
        if self.num_networks == 0 and self.chain_type == "across":
            experiment.var.set(with_trial_maker_namespace(self.trial_maker_id, "network_structure"), self.network_structure)
            self.create_networks_across(experiment)

    def create_networks_across(self, experiment):
        network_structure = json.loads(self.network_structure)
        vertices = network_structure["vertices"]
        for i in range(self.num_chains_per_experiment):
            vertex_id = vertices[i]
            dependent_vertex_ids = self.get_dependent_vertex_ids(vertex_id, network_structure)
            self.create_network(experiment, vertex_id, dependent_vertex_ids)

    def create_network(self, experiment, vertex_id, dependent_vertex_ids, participant=None, id_within_participant=None):
        network = self.network_class(
            trial_maker_id=self.id,
            source_class=self.source_class,
            phase=self.phase,
            experiment=experiment,
            chain_type=self.chain_type,
            vertex_id=vertex_id,
            dependent_vertex_ids=dependent_vertex_ids,
            trials_per_node=self.trials_per_node,
            target_num_nodes=self.num_nodes_per_chain,
            participant=participant,
            id_within_participant=id_within_participant,
        )
        db.session.add(network)
        db.session.commit()
        self._grow_network(network, participant, experiment)
        return network

    def get_dependent_vertex_ids(target, network_structure):
        edges = network_structure["edges"]
        dependent_vertex_ids = [e["origin"] for e in edges if e["target"] == target]
        return dependent_vertex_ids


class GridChainTrialMaker(ChainTrialMaker):
    """
    A TrialMaker class for grid-type graph chains;
    see the documentation for
    :class:`~psynet.trial.chain.ChainTrialMaker`
    for usage instructions.
    """

    def __init__(
        self,
        *,
        id_,
        network_class,
        node_class,
        source_class,
        trial_class,
        phase: str,
        time_estimate_per_trial: Union[int, float],
        grid_dimension: int,
        chain_type: str,
        num_trials_per_participant: int,
        num_chains_per_participant: Optional[int],
        # num_chains_per_experiment: Optional[int],
        trials_per_node: int,
        balance_across_chains: bool,
        check_performance_at_end: bool,
        check_performance_every_trial: bool,
        recruit_mode: str,
        target_num_participants=Optional[int],
        num_iterations_per_chain: Optional[int] = None,
        num_nodes_per_chain: Optional[int] = None,
        fail_trials_on_premature_exit: bool = False,
        fail_trials_on_participant_performance_check: bool = False,
        propagate_failure: bool = True,
        num_repeat_trials: int = 0,
        wait_for_networks: bool = False,
        allow_revisiting_networks_in_across_chains: bool = False,
    ):

        network_structure = self.generate_grid_json(grid_dimension)
        super().__init__(
            id_=id_,
            network_class=network_class,
            node_class=node_class,
            source_class=source_class,
            trial_class=trial_class,
            phase=phase,
            time_estimate_per_trial=time_estimate_per_trial,
            network_structure=network_structure,
            chain_type=chain_type,
            num_trials_per_participant=num_trials_per_participant,
            num_chains_per_participant=num_chains_per_participant,
            # num_chains_per_experiment=num_chains_per_experiment,
            trials_per_node=trials_per_node,
            balance_across_chains=balance_across_chains,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants,
            num_iterations_per_chain=num_iterations_per_chain,
            num_nodes_per_chain=num_nodes_per_chain,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            num_repeat_trials=num_repeat_trials,
            wait_for_networks=wait_for_networks,
            allow_revisiting_networks_in_across_chains=allow_revisiting_networks_in_across_chains
        )

        def generate_grid_json(self, size):
            vertices = [i for i in range(1, size**2 + 1)]
            edges = []
            for v in vertices:
                if v % size != 0:
                    edges = edges + [{"origin": v, "target": v + 1, "properties": {"type": "default"}}]
                if (v - 1) % size != 0:
                    edges = edges + [{"origin": v, "target": v - 1, "properties": {"type": "default"}}]
                if (v + size) <= size ** 2:
                    edges = edges + [{"origin": v, "target": v + size, "properties": {"type": "default"}}]
                if (v - size) > 0:
                    edges = edges + [{"origin": v, "target": v - size, "properties": {"type": "default"}}]
            return json.dumps({"vertices": vertices, "edges": edges})
