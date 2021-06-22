# pylint: disable=unused-argument,abstract-method

from .chain import ChainNetwork, ChainNode, ChainSource, ChainTrial, ChainTrialMaker
import json
from typing import Optional, Union

from trial.main import with_trial_maker_namespace


class GraphChainNetwork(ChainNetwork):
    """
    A Network class for graph chains.
    """

    __mapper_args__ = {"polymorphic_identity": "graph_chain_network"}

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
            # CONTINUE HERE, NEED TO HANDLE HOW NETWORKS GET ASSIGNED TO VERTICES (SAMPLE W/O REP?),
            # USE THAT TO HANDLE GET_PARENTS TO IMPLEMENT INSIDE READY_TO_SPAWN,
            # FOLLOW DOCS FOR THE REST
            # IMPLEMENT GRID DEMO AND MAKE SURE IT ALL WORKS


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
