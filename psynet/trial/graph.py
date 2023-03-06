# pylint: disable=unused-argument,abstract-method

from typing import List, Optional, Type

from dallinger import db

from ..field import claim_field
from .chain import ChainNetwork, ChainNode, ChainTrial, ChainTrialMaker

# from psynet.trial.main import with_trial_maker_namespace
from .main import with_trial_maker_namespace


class GraphChainNetwork(ChainNetwork):
    """
    A Network class for graph chains. A graph chain corresponds to the evolution of
    a vertex within a graph.

    Parameters (for now stating the new ones)
    -----------------------------------------

    vertex_id
        The id of the vertex that the network is representing within the graph.

    dependent_vertex_ids
        A list of the vertex ids on which the current node depends (incoming edges).

    source_seed
        Source seed to use when initializing the graph in the trialmaker.

    """

    __extra_vars__ = ChainNetwork.__extra_vars__.copy()

    vertex_id = claim_field("vertex_id", __extra_vars__, int)
    dependent_vertex_ids = claim_field("dependent_vertex_ids", __extra_vars__)
    source_seed = claim_field("source_seed", __extra_vars__)

    def __init__(  # overriden
        self,
        trial_maker_id: str,
        experiment,
        start_node: "GraphChainNode",
        chain_type: str,
        trials_per_node: int,
        target_n_nodes: int,
        participant=None,
        id_within_participant: Optional[int] = None,
    ):
        self.vertex_id = start_node.vertex_id
        self.dependent_vertex_ids = start_node.dependent_vertex_ids
        self.source_seed = start_node.seed

        super().__init__(
            trial_maker_id=trial_maker_id,
            start_node=start_node,
            experiment=experiment,
            chain_type=chain_type,
            trials_per_node=trials_per_node,
            target_n_nodes=target_n_nodes,
            participant=participant,
            id_within_participant=id_within_participant,
        )


class GraphChainTrial(ChainTrial):
    """
    A Trial class for graph chains.
    """

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

    Parameters (for now stating the new ones)
    -----------------------------------------

    vertex_id
        The id of the vertex that the network is representing within the graph.

    dependent_vertex_ids
        A list of the vertex ids on which the current node depends (incoming edges).
    """

    __extra_vars__ = ChainNode.__extra_vars__.copy()

    def __init__(
        self,
        seed,
        degree: int,
        network,
        experiment,
        propagate_failure: bool,
        vertex_id: int,
        dependent_vertex_ids: List[int],
        participant=None,
    ):
        # pylint: disable=unused-argument
        self.vertex_id = vertex_id
        self.dependent_vertex_ids = dependent_vertex_ids
        super().__init__(
            seed=seed,
            degree=degree,
            network=network,
            experiment=experiment,
            propagate_failure=propagate_failure,
            participant=participant,
        )

    # def create_initial_seed(self, experiment, participant):
    #     return self.network.source_seed

    @staticmethod
    def generate_class_seed():
        raise NotImplementedError

    def create_definition_from_seed(self, seed, experiment, participant):
        """
        (Built-in)
        In a graph chain, the next node in the chain
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

    vertex_id = claim_field("vertex_id", __extra_vars__, int)
    dependent_vertex_ids = claim_field("dependent_vertex_ids", __extra_vars__)

    @property
    def ready_to_spawn(self):
        parents = (
            self.get_parents()
        )  # These are parent nodes from the same layer, to be passed to the next layer
        if len(parents) == len(
            self.dependent_vertex_ids
        ):  # Make sure all parents exist
            all_parents_ready = all([p.reached_target_n_trials for p in parents])
            current_vertex_ready = self.reached_target_n_trials
            return all_parents_ready and current_vertex_ready
        elif len(parents) < len(self.dependent_vertex_ids):
            return False
        else:
            raise ValueError("Invalid number of parent nodes!")

    def get_parents(self):
        trial_maker_id = self.network.trial_maker_id
        degree = self.degree
        nodes = GraphChainNode.query.all()
        current_layer = [
            n
            for n in nodes
            if n.network.trial_maker_id == trial_maker_id and n.degree == degree
        ]
        parents = [n for n in current_layer if n.vertex_id in self.dependent_vertex_ids]
        return parents


class GraphChainTrialMaker(ChainTrialMaker):
    """
    A TrialMaker class for graph chains;
    see the documentation for
    :class:`~psynet.trial.chain.ChainTrialMaker`
    for usage instructions.

    Parameters
    ----------

    network_structure
        A representation of the graph structure to instantiate.
        The representation consistes of a dictionary of vertices and edges.
        E.g. {"vertices": [1,2], "edges": [{"origin": 1, "target": 2, "properties": {"type": "default"}}]}
    """

    def __init__(
        self,
        *,
        id_,
        node_class: Type[GraphChainNode],
        trial_class: Type[GraphChainTrial],
        network_structure,
        chain_type: str,
        expected_trials_per_participant: int,
        max_trials_per_participant: int,
        chains_per_participant: Optional[int],
        # chains_per_experiment: Optional[int],
        trials_per_node: int,
        balance_across_chains: bool,
        check_performance_at_end: bool,
        check_performance_every_trial: bool,
        recruit_mode: str,
        target_n_participants=Optional[int],
        max_nodes_per_chain: Optional[int] = None,
        fail_trials_on_premature_exit: bool = False,
        fail_trials_on_participant_performance_check: bool = False,
        propagate_failure: bool = True,
        n_repeat_trials: int = 0,
        wait_for_networks: bool = False,
        allow_revisiting_networks_in_across_chains: bool = False,
    ):
        if chain_type == "within":
            raise NotImplementedError  # UNCLEAR TO ME HOW TO UNITE THE ON-DEMAND CREATION OF WITHIN CHAINS AND THE PRE-DFINED GRAPH NETWORK STRUCTURE
        chains_per_experiment = len(network_structure["vertices"])
        self.network_structure = network_structure
        super().__init__(
            id_=id_,
            node_class=node_class,
            trial_class=trial_class,
            chain_type=chain_type,
            expected_trials_per_participant=expected_trials_per_participant,
            max_trials_per_participant=max_trials_per_participant,
            chains_per_participant=chains_per_participant,
            chains_per_experiment=chains_per_experiment,
            trials_per_node=trials_per_node,
            balance_across_chains=balance_across_chains,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            recruit_mode=recruit_mode,
            target_n_participants=target_n_participants,
            max_nodes_per_chain=max_nodes_per_chain,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            n_repeat_trials=n_repeat_trials,
            wait_for_networks=wait_for_networks,
            allow_revisiting_networks_in_across_chains=allow_revisiting_networks_in_across_chains,
        )

    @property
    def default_network_class(self):
        return GraphChainNetwork

    def pre_deploy_routine(self, experiment):
        if self.chain_type == "across":
            experiment.var.set(
                with_trial_maker_namespace(self.id, "network_structure"),
                self.network_structure,
            )
        super().pre_deploy_routine(experiment)

    def create_networks_across(self, experiment):
        network_structure = self.network_structure
        vertices = network_structure["vertices"]
        source_seeds = self.generate_source_seed_bundles()
        for i in range(self.chains_per_experiment):
            vertex_id = vertices[i]
            source_seed = [
                seed["bundle"]
                for seed in source_seeds
                if seed["vertex_id"] == vertex_id
            ][0]
            dependent_vertex_ids = self.get_dependent_vertex_ids(
                vertex_id, network_structure
            )
            start_node = self.node_class(
                seed=source_seed,
                degree=0,
                network=None,
                experiment=experiment,
                propagate_failure=self.propagate_failure,
                vertex_id=vertex_id,
                dependent_vertex_ids=dependent_vertex_ids,
                participant=None,
            )
            self.create_graph_network(experiment, start_node)

    def create_graph_network(
        self,
        experiment,
        start_node,
        participant=None,
        id_within_participant=None,
    ):
        network = self.network_class(
            trial_maker_id=self.id,
            start_node=start_node,
            experiment=experiment,
            chain_type=self.chain_type,
            trials_per_node=self.trials_per_node,
            target_n_nodes=self.max_nodes_per_chain,
            participant=participant,
            id_within_participant=id_within_participant,
        )
        db.session.add(network)
        db.session.commit()
        return network

    def get_dependent_vertex_ids(self, target, network_structure):
        edges = network_structure["edges"]
        dependent_vertex_ids = [e["origin"] for e in edges if e["target"] == target]
        return dependent_vertex_ids

    def grow_network(self, network, experiment):
        # We set participant = None because of Dallinger's constraint of not allowing participants
        # to create nodes after they have finished working.
        participant = None
        head = network.head
        if head.ready_to_spawn:
            if head.degree > 0:
                seed_bundle = self.create_seed_bundle(head, experiment, participant)
            else:
                seed_bundle = head.create_seed(experiment, participant)
            node = self.node_class(
                seed_bundle,
                head.degree + 1,
                network,
                experiment,
                self.propagate_failure,
                network.vertex_id,
                network.dependent_vertex_ids,
                participant,
            )
            db.session.add(node)
            network.add_node(node)
            db.session.commit()
            node.check_on_create()
            node.check_on_deploy()
            db.session.commit()
            return True
        return False

    def create_seed_bundle(self, head, experiment, participant):
        head_seed = head.create_seed(experiment, participant)
        parents = head.get_parents()
        bundle = [
            {
                "vertex_id": head.network.vertex_id,
                "content": head_seed,
                "is_center": True,
            }
        ] + [
            {
                "vertex_id": p.network.vertex_id,
                "content": p.create_seed(
                    experiment, participant
                ),  # might require some thought if participant becomes relevant
                "is_center": False,
            }
            for p in parents
        ]
        return bundle

    def generate_source_seed_bundles(self):
        network_structure = self.network_structure
        vertices = network_structure["vertices"]
        centers = [
            {
                "vertex_id": v,
                "content": self.node_class.generate_class_seed(),
                "is_center": True,
            }
            for v in vertices
        ]
        bundles = []
        for i in range(len(centers)):
            center = centers[i]
            dependent_vertex_ids = self.get_dependent_vertex_ids(
                center["vertex_id"], network_structure
            )
            bundle = [center]
            for j in dependent_vertex_ids:
                content = [c["content"] for c in centers if c["vertex_id"] == j]
                bundle = bundle + [
                    {"vertex_id": j, "content": content[0], "is_center": False}
                ]
            bundles = bundles + [{"vertex_id": center["vertex_id"], "bundle": bundle}]
        return bundles
