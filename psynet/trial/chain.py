import random
import warnings
from typing import List, Optional, Set, Type

from dallinger import db
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import not_

from ..field import PythonObject, VarStore, extra_var
from ..page import wait_while
from ..utils import call_function, call_function_with_context, get_logger, negate
from .main import NetworkTrialMaker, Trial, TrialNetwork, TrialNode

logger = get_logger()


# class HasSeed:
#     # Mixin class that provides a 'seed' slot.
#     # See https://docs.sqlalchemy.org/en/14/orm/inheritance.html#resolving-column-conflicts
#     @declared_attr
#     def seed(cls):
#         return cls.__table__.c.get(
#             "seed", Column(JSONB, server_default="{}", default=lambda: {})
#         )
#
#     __extra_vars__ = {}
#     register_extra_var(__extra_vars__, "seed", field_type=dict)


class ChainNetwork(TrialNetwork):
    """
    Implements a network in the form of a chain.
    Intended for use with :class:`~psynet.trial.chain.ChainTrialMaker`.
    Typically the user won't have to override anything here,
    but they can optionally override :meth:`~psynet.trial.chain.ChainNetwork.validate`.

    Parameters
    ----------

    experiment
        An instantiation of :class:`psynet.experiment.Experiment`,
        corresponding to the current experiment.

    chain_type
        Either ``"within"`` for within-participant chains,
        or ``"across"`` for across-participant chains.

    trials_per_node
        Number of satisfactory trials to be received by the last node
        in the chain before another chain will be added.
        Most paradigms have this equal to 1.

    target_num_nodes
        Indicates the target number of nodes for that network.
        In a network with one trial per node, the total number of nodes will generally
        be one greater than the total number of trials. This is because
        we start with one node, representing the random starting location of the
        chain, and each new trial takes us to a new node.

    participant
        Optional participant with which to associate the network.

    id_within_participant
        If ``participant is not None``, then this provides an optional ID for the network
        that is unique within a given participant.

    Attributes
    ----------

    target_num_trials : int or None
        Indicates the target number of trials for that network.
        Left empty by default, but can be set by custom ``__init__`` functions.

    awaiting_async_process : bool
        Whether the network is currently waiting for an asynchronous process to complete.

    earliest_async_process_start_time : Optional[datetime]
        Time at which the earliest pending async process was called.

    num_nodes : int
        Returns the number of non-failed nodes in the network.

    num_completed_trials : int
        Returns the number of completed and non-failed trials in the network
        (irrespective of asynchronous processes, but excluding repeat trials).

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    participant_id : int
        The ID of the associated participant, or ``None`` if there is no such participant.
        Set by default in the ``__init__`` function.

    id_within_participant
        If ``participant is not None``, then this provides an optional ID for the network
        that is unique within a given participant.
        Set by default in the ``__init__`` function.

    chain_type
        Either ``"within"`` for within-participant chains,
        or ``"across"`` for across-participant chains.
        Set by default in the ``__init__`` function.

    trials_per_node
        Number of satisfactory trials to be received by the last node
        in the chain before another chain will be added.
        Most paradigms have this equal to 1.
        Set by default in the ``__init__`` function.
    """

    # pylint: disable=abstract-method
    # __extra_vars__ = TrialNetwork.__extra_vars__.copy()

    participant_id = Column(Integer)
    id_within_participant = Column(Integer)

    chain_type = Column(String)
    trials_per_node = Column(Integer)
    definition = Column(PythonObject)

    def __init__(
        self,
        trial_maker_id: str,
        start_node,
        experiment,
        chain_type: str,
        trials_per_node: int,
        target_num_nodes: int,
        participant=None,
        id_within_participant: Optional[int] = None,
    ):
        super().__init__(trial_maker_id, experiment)
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
        self.block = start_node.block

        if start_node.participant_group:
            self.participant_group = start_node.participant_group
        elif isinstance(self.definition, dict):
            try:
                self.participant_group = self.definition["participant_group"]
            except KeyError:
                pass
        else:
            self.participant_group = "default"

        db.session.add(start_node)
        self.add_node(start_node)
        db.session.commit()

        self.validate()

        db.session.commit()

    def validate(self):
        """
        Runs at the end of the constructor function to check that the
        network object has a legal structure. This can be useful for
        checking that the user hasn't passed illegal argument values.
        """
        pass

    def make_definition(self):
        """
        Derives the definition for the network.
        This definition represents some collection of attributes
        that is shared by all nodes/trials in a network,
        but that may differ between networks.

        Suppose one wishes to have multiple networks in the experiment,
        each characterised by a different value of an attribute
        (e.g. a different color).
        One approach would be to sample randomly; however, this would not
        guarantee an even distribution of attribute values.
        In this case, a better approach is to use the
        :meth:`psynet.trial.chain.ChainNetwork.balance_across_networks`
        method, as follows:

        ::

            colors = ["red", "green", "blue"]
            return {
                "color": self.balance_across_networks(colors)
            }

        See :meth:`psynet.trial.chain.ChainNetwork.balance_across_networks`
        for details on how this balancing works.

        Returns
        -------

        object
            By default this returns an empty dictionary,
            but this can be customised by subclasses.
            The object should be suitable for serialisation to JSON.
        """
        return {}

    def balance_across_networks(self, values: list):
        """
        Chooses a value from a list, with choices being balanced across networks.
        Relies on the fact that network IDs are guaranteed to be consecutive.
        sequences of integers.

        Suppose we wish to assign our networks to colors,
        and we want to balance color assignment across networks.
        We might write the following:

        ::

            colors = ["red", "green", "blue"]
            chosen_color = self.balance_across_networks(colors)

        In across-participant chain designs,
        :meth:`~psynet.trial.chain.ChainNetwork.balance_across_networks`
        will ensure that the distribution of colors is maximally uniform across
        the experiment by assigning
        the first network to red, the second network to green, the third to blue,
        then the fourth to red, the fifth to green, the sixth to blue,
        and so on. This is achieved by referring to the network's
        :attr:`~psynet.trial.chain.ChainNetwork.id`
        attribute.
        In within-participant chain designs,
        the same method is used but within participants,
        so that each participant's first network is assigned to red,
        their second network to green,
        their third to blue,
        then their fourth, fifth, and sixth to red, green, and blue respectively.

        Parameters
        ----------

        values
            The list of values from which to choose.

        Returns
        -------

        Object
            An object from the provided list.
        """
        if self.chain_type == "across":
            id_to_use = self.id
        elif self.chain_type == "within":
            id_to_use = self.id_within_participant
        else:
            raise RuntimeError(f"Unexpected chain_type: {self.chain_type}")

        return values[id_to_use % len(values)]

    @property
    def target_num_nodes(self):
        return self.max_size

    @target_num_nodes.setter
    def target_num_nodes(self, target_num_nodes):
        self.max_size = target_num_nodes

    @property
    def degree(self):
        if self.num_nodes == 0:
            return 0
        return max([node.degree for node in self.active_nodes])

    @property
    def head(self):
        return self.get_node_with_degree(self.degree)

    def get_node_with_degree(self, degree):
        nodes = [n for n in self.active_nodes if n.degree == degree]
        nodes.sort(key=lambda n: n.id)

        first_node = nodes[0]
        other_nodes = nodes[1:]
        for node in other_nodes:
            node.fail(reason=f"duplicate_node_at_degree_{node.degree}")
        return first_node

    def add_node(self, node):
        if node.degree > 0:
            previous_head = self.get_node_with_degree(node.degree - 1)
            previous_head.connect(whom=node)
            previous_head.child = node
            node.parent = previous_head
        if self.num_nodes >= self.target_num_nodes:
            self.full = True

    @property
    def num_trials_still_required(self):
        assert self.target_num_trials is not None
        if self.full:
            return 0
        else:
            return self.target_num_trials - self.num_completed_trials


class ChainNode(TrialNode):
    """
    Represents a node in a chain network.
    In an experimental context, the node represents a state in the experiment;
    in particular, the last node in the chain represents a current state
    in the experiment.

    This class is intended for use with :class:`~psynet.trial.chain.ChainTrialMaker`.
    It subclasses :class:`dallinger.models.Node`.

    The most important attribute is :attr:`~psynet.trial.chain.ChainNode.definition`.
    This is the core information that represents the current state of the node.
    In a transmission chain of drawings, this might be an (encoded) drawing;
    in a Markov Chain Monte Carlo with People paradigm, this might be the current state
    from the proposal is sampled.

    The user is required to override the following abstract methods:

    * :meth:`~psynet.trial.chain.ChainNode.create_definition_from_seed`,
      which creates a node definition from the seed passed from the previous
      source or node in the chain;

    * :meth:`~psynet.trial.chain.ChainNode.summarize_trials`,
      which summarizes the trials at a given node to produce a seed that can
      be passed to the next node in the chain.

    Parameters
    ----------

    seed
        The seed which is used to initialize the node, potentially stochastically.
        This seed typically comes from either a :class:`~psynet.trial.chain.ChainSource`
        or from another :class:`~psynet.trial.chain.ChainNode`
        via the :meth:`~psynet.trial.chain.ChainNode.create_seed` method.
        For example, in a transmission chain of drawings, the seed might be
        a serialised version of the last drawn image.

    degree
        The position of the node in the chain,
        where 0 indicates the source,
        where 1 indicates the first node,
        2 the second node, and so on.

    network
        The network with which the node is to be associated.

    experiment
        An instantiation of :class:`psynet.experiment.Experiment`,
        corresponding to the current experiment.

    propagate_failure
        If ``True``, the failure of a trial is propagated to other
        parts of the experiment (the nature of this propagation is left up
        to the implementation).

    participant
        Optional participant with which to associate the node.

    Attributes
    ----------

    degree
        See the ``__init__`` function.

    child_id
        See the ``__init__`` function.

    seed
        See the ``__init__`` function.

    definition
        This is the core information that represents the current state of the node.
        In a transmission chain of drawings, this might be an (encoded) drawing;
        in a Markov Chain Monte Carlo with People paradigm, this might be the current state
        from the proposal is sampled.
        It is set by the :meth:`~psynet.trial.chain.ChainNode:create_definition_from_seed` method.

    propagate_failure
        See the ``__init__`` function.

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    child
        The node's child (i.e. direct descendant) in the chain, or
        ``None`` if no child exists.

    target_num_trials
        The target number of trials for the node,
        set from :attr:`psynet.trial.chain.ChainNetwork.trials_per_node`.

    ready_to_spawn
        Returns ``True`` if the node is ready to spawn a child.
        Not intended for overriding.

    complete_and_processed_trials
        Returns all completed trials associated with the node,
        excluding those that are awaiting some asynchronous processing.
        excludes failed nodes.

    completed_trials
        Returns all completed trials associated with the node.
        Excludes failed nodes and repeat trials.

    num_completed_trials
        Counts the number of completed trials associated with the node.
        Excludes failed nodes and repeat_trials.

    viable_trials
        Returns all viable trials associated with the node,
        i.e. all trials that have not failed.
    """

    __extra_vars__ = TrialNode.__extra_vars__.copy()

    key = Column(String, index=True)
    degree = Column(Integer)
    child_id = Column(Integer, ForeignKey("node.id"))
    parent_id = Column(Integer, ForeignKey("node.id"))
    seed = Column(PythonObject, default=lambda: {})
    definition = Column(PythonObject, default=lambda: {})
    participant_group = (Column(String),)
    block = Column(String)
    propagate_failure = Column(Boolean)

    child = relationship(
        "ChainNode", foreign_keys=[child_id], uselist=False, post_update=True
    )
    parent = relationship(
        "ChainNode", foreign_keys=[parent_id], uselist=False, post_update=True
    )

    def __init__(
        self,
        *,
        definition=None,
        seed=None,
        parent=None,
        participant_group=None,
        block=None,
        assets=None,
        degree=None,
        module_id=None,
        network=None,
        experiment=None,
        participant=None,
        propagate_failure=False,
    ):
        super().__init__(network=network, participant=participant)

        assert not (definition and seed)

        if parent:
            parent.child = self
            self.parent = parent

        if participant_group is None:
            if parent:
                self.participant_group = parent.participant_group
            else:
                self.participant_group = "default"

        if block is None:
            if parent:
                self.block = parent.block
            else:
                self.block = "default"

        if degree is None:
            if parent:
                self.degree = parent.degree + 1
            else:
                self.degree = 0

        if module_id is None:
            if parent:
                self.module_id = parent.module_id
            else:
                self.module_id = None

        self.seed = seed
        self.propagate_failure = propagate_failure

        if not definition and not seed:
            seed = self.create_initial_seed(experiment, participant)

        if not definition:
            self.definition = self.create_definition_from_seed(
                seed, experiment, participant
            )

        if assets is None:
            assets = {}
        self._staged_assets = assets

    def create_initial_seed(self, experiment, participant):
        raise NotImplementedError

    def stage_assets(self, experiment):
        self.assets = {**self.network.assets}

        for label, asset in self._staged_assets.items():
            if asset.label is None:
                asset.label = label

            asset.parent = self

            if not asset.has_key:
                asset.generate_key()

            asset.receive_node_definition(self.definition)

            # asset.deposit()  # defer this so it can be done in parallel later on

            experiment.assets.stage(asset)
            self.assets[label] = asset

        db.session.commit()

    def create_definition_from_seed(self, seed, experiment, participant):
        """
        Creates a node definition from a seed.
        The seed comes from the previous node in the chain.
        In many cases (e.g. iterated reproduction) the definition
        will be trivially equal to the seed,
        but in some cases we may introduce some kind of stochastic alteration
        to produce the definition.

        Parameters
        ----------

        seed : object
            The seed, passed from the previous state in the chain.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            The participant who initiated the creation of the node.

        Returns
        -------

        object
            The derived definition. Should be suitable for serialisation to JSON.
        """
        raise NotImplementedError

    def summarize_trials(self, trials: list, experiment, participant):
        """
        Summarizes the trials at the node to produce a seed that can
        be passed to the next node in the chain.

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
        raise NotImplementedError

    def create_seed(self, experiment, participant):
        trials = self.completed_and_processed_trials
        return self.summarize_trials(trials, experiment, participant)

    @property
    def var(self):
        return VarStore(self)

    @property
    def target_num_trials(self):
        return self.network.trials_per_node

    @property
    def ready_to_spawn(self):
        return self.reached_target_num_trials()

    @property
    def completed_and_processed_trials(self):
        return [
            t
            for t in self.trials
            if (not t.failed and t.complete and t.finalized and not t.is_repeat_trial)
        ]

    @property
    def viable_trials(self):
        return [t for t in self.trials if (not t.failed and not t.is_repeat_trial)]

    def reached_target_num_trials(self):
        return len(self.completed_and_processed_trials) >= self.target_num_trials

    @property
    def failure_cascade(self):
        to_fail = []
        if self.propagate_failure:
            to_fail.append(self.infos)
            if self.child:
                to_fail.append(lambda: [self.child])
        return to_fail


UniqueConstraint(ChainNode.module_id, ChainNode.key)


class ChainTrial(Trial):
    """
    Represents a trial in a :class:`~psynet.trial.chain.ChainNetwork`.
    The user is expected to override the following methods:

    * :meth:`~psynet.trial.chain.ChainTrial.make_definition`,
      responsible for deciding on the content of the trial.
    * :meth:`~psynet.trial.chain.ChainTrial.show_trial`,
      determines how the trial is turned into a webpage for presentation to the participant.
    * :meth:`~psynet.trial.chain.ChainTrial.show_feedback`.
      defines an optional feedback page to be displayed after the trial.

    The user must also override the ``time_estimate`` class attribute,
    providing the estimated duration of the trial in seconds.
    This is used for predicting the participant's bonus payment
    and for constructing the progress bar.

    The user may also wish to override the
    :meth:`~psynet.trial.chain.ChainTrial.async_post_trial` method
    if they wish to implement asynchronous trial processing.

    This class subclasses the `~psynet.trial.main.Trial` class,
    which in turn subclasses the :class:`~dallinger.models.Info` class from Dallinger,
    hence it can be found in the ``Info`` table in the database.
    It inherits these class's methods, which the user is welcome to use
    if they seem relevant.

    Instances can be retrieved using *SQLAlchemy*; for example, the
    following command retrieves the ``ChainTrial`` object with an ID of 1:

    ::

        ChainTrial.query.filter_by(id=1).one()

    Parameters
    ----------

    experiment:
        An instantiation of :class:`psynet.experiment.Experiment`,
        corresponding to the current experiment.

    node:
        An object of class :class:`dallinger.models.Node` to which the
        :class:`~dallinger.models.Trial` object should be attached.
        Complex experiments are often organised around networks of nodes,
        but in the simplest case one could just make one :class:`~dallinger.models.Network`
        for each type of trial and one :class:`~dallinger.models.Node` for each participant,
        and then assign the :class:`~dallinger.models.Trial`
        to this :class:`~dallinger.models.Node`.
        Ask us if you want to use this simple use case - it would be worth adding
        it as a default to this implementation, but we haven't done that yet,
        because most people are using more complex designs.

    participant:
        An instantiation of :class:`psynet.participant.Participant`,
        corresponding to the current participant.

    propagate_failure : bool
        Whether failure of a trial should be propagated to other
        parts of the experiment depending on that trial
        (for example, subsequent parts of a transmission chain).

    run_async_post_trial : bool
        Set this to ``True`` if you want the :meth:`~psynet.trial.main.Trial.async_post_trial`
        method to run after the user responds to the trial.

    Attributes
    ----------

    time_estimate : numeric
        The estimated duration of the trial (including any feedback), in seconds.
        This should generally correspond to the (sum of the) ``time_estimate`` parameters in
        the page(s) generated by ``show_trial``, plus the ``time_estimate`` parameter in
        the page generated by ``show_feedback`` (if defined).
        This is used for predicting the participant's bonus payment
        and for constructing the progress bar.

    node
        The class:`dallinger.models.Node` to which the :class:`~dallinger.models.Trial`
        belongs.

    participant_id : int
        The ID of the associated participant.
        The user should not typically change this directly.
        Stored in ``property1`` in the database.

    complete : bool
        Whether the trial has been completed (i.e. received a response
        from the participant). The user should not typically change this directly.
        Stored in ``property2`` in the database.

    answer : Object
        The response returned by the participant. This is serialised
        to JSON, so it shouldn't be too big.
        The user should not typically change this directly.
        Stored in ``details`` in the database.

    awaiting_async_process : bool
        Whether the trial is waiting for some asynchronous process
        to complete (e.g. to synthesise audiovisual material).

    earliest_async_process_start_time : Optional[datetime]
        Time at which the earliest pending async process was called.

    propagate_failure : bool
        Whether failure of a trial should be propagated to other
        parts of the experiment depending on that trial
        (for example, subsequent parts of a transmission chain).

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    definition : Object
        An arbitrary Python object that somehow defines the content of
        a trial. Often this will be a dictionary comprising a few
        named parameters.
        The user should not typically change this directly,
        as it is instead determined by
        :meth:`~psynet.trial.main.Trial.make_definition`.

    """

    # pylint: disable=abstract-method
    __extra_vars__ = Trial.__extra_vars__.copy()

    @property
    @extra_var(__extra_vars__)
    def degree(self):
        return self.node.degree

    @property
    def node(self):
        return self.origin

    @property
    def failure_cascade(self):
        to_fail = []
        if self.propagate_failure:
            if self.node.child:
                to_fail.append(lambda: [self.node.child])
        return to_fail


class ChainTrialMaker(NetworkTrialMaker):
    """
    Administers a sequence of trials in a chain-based paradigm.
    This trial maker is suitable for implementing paradigms such as
    Markov Chain Monte Carlo with People, iterated reproduction, and so on.
    It is intended for use with the following helper classes,
    which should be customised for the particular paradigm:

    * :class:`~psynet.trial.chain.ChainNetwork`;
      a special type of :class:`~psynet.trial.main.TrialNetwork`

    * :class:`~psynet.trial.chain.ChainNode`;
      a special type of :class:`~dallinger.models.Node`

    * :class:`~psynet.trial.chain.ChainTrial`;
      a special type of :class:`~psynet.trial.main.NetworkTrial`

    A chain is initialized with a :class:`~psynet.trial.chain.ChainSource` object.
    This :class:`~psynet.trial.chain.ChainSource` object provides
    the initial seed to the chain.
    The :class:`~psynet.trial.chain.ChainSource` object is followed
    by a series of :class:`~psynet.trial.chain.ChainNode` objects
    which are generated through the course of the experiment.
    The last :class:`~psynet.trial.chain.ChainNode` in the chain
    represents the current state of the chain, and it determines the
    properties of the next trials to be drawn from that chain.
    A new :class:`~psynet.trial.chain.ChainNode` object is generated once
    sufficient :class:`~psynet.trial.chain.ChainTrial` objects
    have been created for that :class:`~psynet.trial.chain.ChainNode`.
    There can be multiple chains in an experiment, with these chains
    either being owned by individual participants ("within-participant" designs)
    or shared across participants ("across-participant" designs).

    Parameters
    ----------

    network_class
        The class object for the networks used by this maker.
        This should subclass :class:`~psynet.trial.chain.ChainNetwork`.

    node_class
        The class object for the networks used by this maker.
        This should subclass :class:`~psynet.trial.chain.ChainNode`.

    source_class
        The class object for sources
        (should subclass :class:`~psynet.trial.chain.ChainSource`).

    trial_class
        The class object for trials administered by this maker
        (should subclass :class:`~psynet.trial.chain.ChainTrial`).

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
        only relevant if ``chain_type="across"``.

    num_iterations_per_chain
        Specifies chain length in terms of the
        number of data-collection iterations that are required to complete a chain.
        The number of successful participant trials required to complete the chain then
        corresponds to ``trials_per_node * num_iterations_per_chain``.
        Previously chain length was specified using the now-deprecated argument ``num_nodes_per_chain``.

    num_nodes_per_chain
        [DEPRECATED; new code should use ``num_iterations_per_chain`` and leave this argument empty.]
        Maximum number of nodes in the chain before the chain is marked as full and no more nodes will be added.
        The final node receives no participant trials, but instead summarizes the state of the network.
        So, ``num_nodes_per_chain`` is equal to ``1 + num_iterations_per_chain``.

    trials_per_node
        Number of satisfactory trials to be received by the last node
        in the chain before another chain will be added.
        Most paradigms have this equal to 1.

    balance_across_chains
        Whether trial selection should be actively balanced across chains,
        such that trials are preferentially sourced from chains with
        fewer valid trials.

    balance_strategy
        A two-element list that determines how balancing occurs, if ``balance_across_chains`` is ``True``.
        If the list contains "across", then the balancing will take into account trials from other participants.
        If it contains "within", then the balancing will take into account trials from the present participant.
        If both are selected, then the balancing strategy will prioritize balancing within the current participant,
        but will use counts from other participants as a tie breaker.

    check_performance_at_end
        If ``True``, the participant's performance
        is evaluated at the end of the series of trials.

    check_performance_every_trial
        If ``True``, the participant's performance
        is evaluated after each trial.

    recruit_mode
        Selects a recruitment criterion for determining whether to recruit
        another participant. The built-in criteria are ``"num_participants"``
        and ``"num_trials"``, though the latter requires overriding of
        :attr:`~psynet.trial.main.TrialMaker.num_trials_still_required`.

    target_num_participants
        Target number of participants to recruit for the experiment. All
        participants must successfully finish the experiment to count
        towards this quota. This target is only relevant if
        ``recruit_mode="num_participants"``.

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

    num_repeat_trials
        Number of repeat trials to present to the participant. These trials
        are typically used to estimate the reliability of the participant's
        responses.
        Defaults to ``0``.

    wait_for_networks
        If ``True``, then the participant will be made to wait if there are
        still more networks to participate in, but these networks are pending asynchronous processes.

    allow_revisiting_networks_in_across_chains : bool
        If this is set to ``True``, then participants can revisit the same network
        in across-participant chains. The default is ``False``.

    Attributes
    ----------

    check_timeout_interval_sec : float
        How often to check for trials that have timed out, in seconds (default = 30).
        Users are invited to override this.

    response_timeout_sec : float
        How long until a trial's response times out, in seconds (default = 60)
        (i.e. how long PsyNet will wait for the participant's response to a trial).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval_sec`.
        Users are invited to override this.

    async_timeout_sec : float
        How long until an async process times out, in seconds (default = 300).
        This is a lower bound on the actual timeout
        time, which depends on when the timeout daemon next runs,
        which in turn depends on :attr:`~psynet.trial.main.TrialMaker.check_timeout_interval_sec`.
        Users are invited to override this.

    network_query : sqlalchemy.orm.Query
        An SQLAlchemy query for retrieving all networks owned by the current trial maker.
        Can be used for operations such as the following: ``self.network_query.count()``.

    num_networks : int
        Returns the number of networks owned by the trial maker.

    networks : list
        Returns the networks owned by the trial maker.

    performance_check_threshold : float
        Score threshold used by the default performance check method, defaults to 0.0.
        By default, corresponds to the minimum proportion of non-failed trials that
        the participant must achieve to pass the performance check.

    end_performance_check_waits : bool
        If ``True`` (default), then the final performance check waits until all trials no
        longer have any pending asynchronous processes.
    """

    def __init__(
        self,
        *,
        id_,
        start_nodes: List,
        network_class: Type[ChainNetwork],
        node_class: Type[ChainNode],
        trial_class: Type[ChainTrial],
        chain_type: str,
        num_trials_per_participant: int,
        num_chains_per_participant: Optional[int],
        num_chains_per_experiment: Optional[int],
        trials_per_node: int,
        balance_across_chains: bool,
        max_trials_per_block: Optional[int] = None,
        balance_strategy: Set[str] = {"within", "across"},
        check_performance_at_end: bool = False,
        check_performance_every_trial: bool = False,
        recruit_mode: str = "num_participants",
        target_num_participants: Optional[int] = None,
        num_iterations_per_chain: Optional[int] = None,
        num_nodes_per_chain: Optional[int] = None,
        fail_trials_on_premature_exit: bool = False,
        fail_trials_on_participant_performance_check: bool = False,
        propagate_failure: bool = True,
        num_repeat_trials: int = 0,
        wait_for_networks: bool = False,
        allow_revisiting_networks_in_across_chains: bool = False,
    ):
        assert chain_type in ["within", "across"]

        if (
            chain_type == "across"
            and num_trials_per_participant
            and num_trials_per_participant > num_chains_per_experiment
            and not allow_revisiting_networks_in_across_chains
        ):
            raise ValueError(
                "In across-chain experiments, <num_trials_per_participant> "
                "cannot exceed <num_chains_per_experiment> unless ``allow_revisiting_networks_in_across_chains`` "
                "is ``True``."
            )

        if chain_type == "within" and recruit_mode == "num_trials":
            raise ValueError(
                "In within-chain experiments the 'num_trials' recruit method is not available."
            )

        if (num_nodes_per_chain is not None) and (num_iterations_per_chain is not None):
            raise ValueError(
                "num_nodes_per_chain and num_iterations_per_chain cannot both be provided"
            )
        elif num_nodes_per_chain is not None:
            num_iterations_per_chain = num_nodes_per_chain - 1
            warnings.simplefilter("always", DeprecationWarning)
            warnings.warn(
                "num_nodes_per_chain is deprecated, use num_iterations_per_chain instead",
                DeprecationWarning,
            )
        elif num_iterations_per_chain is not None:
            pass
        elif (num_nodes_per_chain is None) and (num_iterations_per_chain is None):
            raise ValueError(
                "one of num_nodes_per_chain and num_iterations_per_chain must be provided"
            )

        assert start_nodes is None or callable(start_nodes)
        self.start_nodes = start_nodes

        assert len(balance_strategy) <= 2
        assert all([x in ["across", "within"] for x in balance_strategy])

        self.node_class = node_class
        self.trial_class = trial_class
        self.chain_type = chain_type
        self.num_trials_per_participant = num_trials_per_participant
        self.max_trials_per_block = max_trials_per_block
        self.num_chains_per_participant = num_chains_per_participant
        self.num_chains_per_experiment = num_chains_per_experiment
        self.num_iterations_per_chain = num_iterations_per_chain
        self.num_nodes_per_chain = num_iterations_per_chain + 1
        self.trials_per_node = trials_per_node
        self.balance_across_chains = balance_across_chains
        self.balance_strategy = balance_strategy
        self.check_performance_at_end = check_performance_at_end
        self.check_performance_every_trial = check_performance_every_trial
        self.propagate_failure = propagate_failure
        self.allow_revisiting_networks_in_across_chains = (
            allow_revisiting_networks_in_across_chains
        )

        super().__init__(
            id_=id_,
            trial_class=trial_class,
            network_class=network_class,
            expected_num_trials=num_trials_per_participant + num_repeat_trials,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants,
            num_repeat_trials=num_repeat_trials,
            wait_for_networks=wait_for_networks,
        )

    def init_participant(self, experiment, participant):
        super().init_participant(experiment, participant)
        self.init_participated_networks(participant)
        if self.chain_type == "within":
            networks = self.create_networks_within(experiment, participant)
        else:
            networks = self.networks
        blocks = set([network.block for network in networks])
        self.init_block_order(experiment, participant, blocks)

    def init_block_order(self, experiment, participant, blocks):
        call_function_with_context(
            self.choose_block_order,
            experiment=experiment,
            participant=participant,
            blocks=blocks,
        )
        self.set_block_order(
            participant,
            self.choose_block_order(experiment=experiment, participant=participant),
        )

    def choose_block_order(self, experiment, participant, blocks):
        # pylint: disable=unused-argument
        """
        Determines the order of blocks for the current participant.
        By default this function shuffles the blocks randomly for each participant.
        The user is invited to override this function for alternative behaviour.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        Returns
        -------

        list
            A list of blocks in order of presentation,
            where each block is identified by a string label.
        """
        return random.sample(blocks, len(blocks))

    def init_blocks(self, experiment, participant):
        block_order = (
            self.choose_block_order(experiment=experiment, participant=participant),
        )
        self.set_block_order(participant, block_order)
        self.set_current_block_position(participant, 0)

    @property
    def block_order_var_id(self):
        return self.with_namespace("block_order")

    def set_block_order(self, participant, block_order):
        participant.var.new(self.block_order_var_id, block_order)

    def get_block_order(self, participant):
        return participant.var.get(self.with_namespace("block_order"))

    def get_current_block(self, participant):
        block_order = self.get_block_order(participant)
        index = self.get_current_block_position(participant)
        return block_order[index]

    def set_current_block_position(self, participant, block_position):
        participant.var.set(
            self.with_namespace("current_block_position"), block_position
        )

    def get_current_block_position(self, participant):
        return participant.var.get(self.with_namespace("current_block_position"))

    def go_to_next_block(self, participant):
        current = self.get_current_block_position(participant)
        self.set_current_block_position(participant, current + 1)

    def _should_finish_block(self, participant):
        current_block = self.get_current_block(participant)
        current_block_position = self.get_current_block_position(participant)
        trials_in_block = [
            trial
            for trial in participant.trials
            if trial.block_position == current_block_position
        ]
        return self.should_finish_block(
            participant, current_block, current_block_position, trials_in_block
        )

    def should_finish_block(
        self,
        participant,
        current_block,
        current_block_position,
        participant_trials_in_block,
    ):  # noqa
        return (
            len(participant_trials_in_block) >= self.max_trials_per_block
            or self.num_trials_per_participant >= self.num_trials_per_participant
        )

    @property
    def introduction(self):
        if self.chain_type == "within":
            return wait_while(
                negate(self.all_participant_networks_ready),
                expected_wait=5.0,
                log_message="Waiting for participant networks to be ready.",
            )
        return None

    def all_participant_networks_ready(self, participant):
        networks = self.network_class.query.filter_by(
            participant_id=participant.id, trial_maker_id=self.id
        ).all()
        return all([not x.awaiting_async_process for x in networks])

    @property
    def num_trials_still_required(self):
        assert self.chain_type == "across"
        return sum([network.num_trials_still_required for network in self.networks])

    #########################
    # Participated networks #
    #########################

    def init_participated_networks(self, participant):
        participant.var.set(self.with_namespace("participated_networks"), [])

    def get_participated_networks(self, participant):
        return participant.var.get(self.with_namespace("participated_networks"))

    def add_to_participated_networks(self, participant, network_id):
        networks = self.get_participated_networks(participant)
        networks.append(network_id)
        participant.var.set(self.with_namespace("participated_networks"), networks)

    def pre_deploy_routine(self, experiment):
        if self.chain_type == "across":
            self.create_networks_across(experiment)

    def create_networks_within(self, experiment, participant):
        if self.start_nodes:
            nodes = call_function_with_context(
                self.start_nodes, experiment=experiment, participant=participant
            )
            assert len(nodes) == self.num_chains_per_participant, (
                f"Problem with trial maker {self.id}: "
                f"The number of nodes generated by start_nodes ({len(nodes)} did not equal "
                f"num_chains_per_participant ({self.num_chains_per_participant})."
            )
        else:
            nodes = [None for _ in range(self.num_chains_per_participant)]

        networks = []
        for i in range(self.num_chains_per_participant):
            network = self.create_network(
                experiment, participant, id_within_participant=i, start_node=nodes[i]
            )
            self._grow_network(network, experiment)
            networks.append(network)

        return networks

    def create_networks_across(self, experiment):
        if self.start_nodes:
            nodes = call_function(
                self.start_nodes,
                experiment=experiment,
            )
            assert len(nodes) == self.num_chains_per_experiment, (
                f"Problem with trial maker {self.id}: "
                f"The number of nodes created by start_nodes ({len(nodes)}) did not equal 0 or "
                f"num_chains_per_experiment ({self.num_chains_per_experiment})."
            )
        else:
            nodes = [None for _ in range(self.num_chains_per_experiment)]
        for node in nodes:  # type: ChainNode
            self.create_network(experiment, start_node=node)
            node.stage_assets(experiment)

    def create_network(
        self, experiment, participant=None, id_within_participant=None, start_node=None
    ):
        if not start_node:
            start_node = self.node_class(
                network=None, experiment=experiment, participant=participant
            )

        network = self.network_class(
            trial_maker_id=self.id,
            start_node=start_node,
            experiment=experiment,
            chain_type=self.chain_type,
            trials_per_node=self.trials_per_node,
            target_num_nodes=self.num_nodes_per_chain,
            participant=participant,
            id_within_participant=id_within_participant,
        )
        db.session.add(network)
        db.session.commit()
        return network

    def find_networks(self, participant, experiment):
        """

        Parameters
        ----------
        participant
        experiment

        Returns
        -------

        Either "exit", "wait", or a list of networks.

        """
        logger.info(
            "Looking for networks for participant %i.",
            participant.id,
        )
        n_completed_trials = self.get_num_completed_trials(participant)
        if n_completed_trials >= self.num_trials_per_participant:
            logger.info(
                "N completed trials (%i) >= N trials per participant (%i), skipping forward",
                n_completed_trials,
                self.num_trials_per_participant,
            )
            return "exit"

        if self._should_finish_block(participant):
            if (
                self.get_current_block_position(participant)
                >= len(self.get_block_order(participant)) + 1
            ):
                return "exit"
            else:
                self.go_to_next_block(participant)

        networks = self.network_class.query.filter_by(
            trial_maker_id=self.id, full=False
        )

        logger.info(
            "There are %i non-full networks for trialmaker %s.",
            networks.count(),
            self.id,
        )

        if self.chain_type == "within":
            networks = self.filter_by_participant_id(networks, participant)
        elif (
            self.chain_type == "across"
            and not self.allow_revisiting_networks_in_across_chains
        ):
            networks = self.exclude_participated(networks, participant)

        participant_group = participant.get_participant_group(self.id)
        networks = networks.filter_by(participant_group=participant_group)

        logger.info(
            "%i of these networks match the current participant group (%s).",
            networks.count(),
            participant_group,
        )

        networks = networks.all()

        networks = self.custom_network_filter(
            candidates=networks, participant=participant
        )

        logger.info("%i remain after applying custom network filters.", len(networks))

        if not isinstance(networks, list):
            return TypeError("custom_network_filter must return a list of networks")

        def has_pending_process(network):
            return network.awaiting_async_process or network.head.awaiting_async_process

        networks_without_pending_processes = [
            n for n in networks if not has_pending_process(n)
        ]

        logger.info(
            "%i out of %i networks are awaiting async processes (or have nodes awaiting async processes).",
            len(networks) - len(networks_without_pending_processes),
            len(networks),
        )

        if (
            len(networks_without_pending_processes) == 0
            and len(networks) > 0
            and self.wait_for_networks
        ):
            logger.info("Will wait for a network to become available.")
            return "wait"

        networks = networks_without_pending_processes

        networks_with_head_space = [
            n for n in networks if len(n.head.viable_trials) < self.trials_per_node
        ]

        if len(networks) > 0 and len(networks_with_head_space) == 0:
            logger.info(
                "All of these chains have head nodes that have already received their full complement of trials. "
                "They need to grow before a new participant can join them."
            )
            if self.wait_for_networks:
                return "wait"
            else:
                return "exit"

        networks = networks_with_head_space

        if len(networks) == 0:
            return "exit"

        random.shuffle(networks)

        if self.balance_across_chains:
            if "across" in self.balance_strategy:
                networks.sort(key=lambda network: network.num_completed_trials)
            if "within" in self.balance_strategy:
                networks.sort(
                    key=lambda network: len(
                        [
                            t
                            for t in network.trials
                            if t.participant_id == participant.id
                        ]
                    )
                )

        current_block = self.get_current_block(participant)
        current_block_position = self.get_current_block_position(participant)
        remaining_blocks = self.get_block_order(participant)[current_block_position:]
        networks.sort(key=lambda network: remaining_blocks.index(network.block))

        chosen = networks[0]
        if chosen.block != current_block:
            logger.info(
                f"Advanced from block '{current_block}' to '{chosen.block}' "
                "because there weren't any spots available in the former."
            )

        return [chosen]

    def custom_network_filter(self, candidates, participant):
        """
        Override this function to define a custom filter for choosing the participant's next network.

        Parameters
        ----------
        candidates:
            The current list of candidate networks as defined by the built-in chain procedure.

        participant:
            The current participant.

        Returns
        -------

        An updated list of candidate networks. The default implementation simply returns the original list.
        The experimenter might alter this function to remove certain networks from the list.
        """
        return candidates

    @staticmethod
    def filter_by_participant_id(networks, participant):
        query = networks.filter_by(participant_id=participant.id)
        logger.info(
            "%i of these belong to participant %i.",
            query.count(),
            participant.id,
        )
        return query

    def exclude_participated(self, networks, participant):
        query = networks.filter(
            not_(self.network_class.id.in_(self.get_participated_networks(participant)))
        )
        logger.info(
            "%i of these are available once you exclude already-visited networks.",
            query.count(),
        )
        return query

    def grow_network(self, network, experiment):
        # We set participant = None because of Dallinger's constraint of not allowing participants
        # to create nodes after they have finished working.
        participant = None
        head = network.head
        if head.ready_to_spawn:
            seed = head.create_seed(experiment, participant)
            node = self.node_class(
                seed=seed,
                parent=head,
                network=network,
                experiment=experiment,
                propagate_failure=self.propagate_failure,
                participant=participant,
            )
            db.session.add(node)
            network.add_node(node)
            db.session.commit()
            return True
        return False

    def find_node(self, network, participant, experiment):
        assert (
            not network.awaiting_async_process
            and not network.head.awaiting_async_process
        )
        return network.head

    def finalize_trial(self, answer, trial, experiment, participant):
        super().finalize_trial(answer, trial, experiment, participant)
        self.add_to_participated_networks(participant, trial.network_id)
