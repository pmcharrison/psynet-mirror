import random
from typing import Optional, Type

from dallinger import db
from dallinger.models import Vector
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import column_property, relationship
from sqlalchemy.sql.expression import not_, select

from ..data import SQLMixinDallinger
from ..field import PythonList, PythonObject, VarStore
from ..page import wait_while
from ..timeline import is_list_of
from ..utils import (
    call_function_with_context,
    get_logger,
    log_time_taken,
    negate,
    time_logger,
)
from .main import (
    NetworkTrialMaker,
    NetworkTrialMakerState,
    Trial,
    TrialNetwork,
    TrialNode,
)

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

# Vector.type = Column(String(50))
# Vector.__mapper_args__ = {"polymorphic_on": Vector.type, "polymorphic_identity": "vector"}


class ChainVector(SQLMixinDallinger, Vector):
    def __init__(self, origin, destination):
        """
        Patched version of ``dallinger.models.Vector`` that does not assume that
        ``origin`` or ``destination`` have been committed to the database yet.
        """
        self.origin = origin
        self.destination = destination
        self.network = self.origin.network


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

    target_n_nodes
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

    target_n_trials : int or None
        Indicates the target number of trials for that network.
        Left empty by default, but can be set by custom ``__init__`` functions.

    awaiting_async_process : bool
        Whether the network is currently waiting for an asynchronous process to complete.

    earliest_async_process_start_time : Optional[datetime]
        Time at which the earliest pending async process was called.

    n_alive_nodes : int
        Returns the number of non-failed nodes in the network.

    n_completed_trials : int
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

    chain_type = Column(String)
    head_id = Column(Integer, ForeignKey("node.id"))
    trials_per_node = Column(Integer)
    definition = Column(PythonObject)
    block = Column(String, index=True)

    head = relationship("ChainNode", foreign_keys=[head_id], post_update=True)

    # @hybrid_property
    # def n_viable_trials_at_head(self):
    #     return self.head.n_viable_trials
    #
    # @n_viable_trials_at_head.expression
    # def n_viable_trials_at_head(cls):
    #     return
    #
    #
    #     column_property(
    # ef n_viable_trials_at_head = column_property(
    #
    # )

    def __init__(
        self,
        trial_maker_id: str,
        start_node,
        experiment,
        chain_type: str,
        trials_per_node: int,
        target_n_nodes: int,
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
        self.target_n_nodes = target_n_nodes
        self.target_n_trials = target_n_nodes * trials_per_node

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
        start_node.check_on_create()
        start_node.check_on_deploy()
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
    def target_n_nodes(self):
        return self.max_size

    @target_n_nodes.setter
    def target_n_nodes(self, target_n_nodes):
        self.max_size = target_n_nodes

    @property
    def degree(self):
        if self.n_alive_nodes == 0:
            return 0
        return max([node.degree for node in self.alive_nodes])

    # @property
    # def head(self):
    #     return self.get_node_with_degree(self.degree)

    def get_node_with_degree(self, degree):
        nodes = [n for n in self.alive_nodes if n.degree == degree]
        nodes.sort(key=lambda n: n.id)

        first_node = nodes[0]
        other_nodes = nodes[1:]
        for node in other_nodes:
            node.fail(reason=f"duplicate_node_at_degree_{node.degree}")
        return first_node

    def add_node(self, node):
        node.set_network(self)
        if node.degree > 0:
            # previous_head = self.get_node_with_degree(node.degree - 1)
            previous_head = self.head
            vector = ChainVector(origin=previous_head, destination=node)
            db.session.add(vector)
            previous_head.child = node
            node.parent = previous_head
        if node.degree >= self.max_size:
            # Setting full=True means that no participants will be assigned to the final node,
            # and it'll just be used as a summary of the chain's final state.
            #
            # Note: We avoid calling self.calculate_full because it involves a database query.
            self.full = True
        self.head = node

    @property
    def n_trials_still_required(self):
        assert self.target_n_trials is not None
        if self.full:
            return 0
        else:
            return self.target_n_trials - self.n_completed_trials

    # @hybrid_property
    # def ready_to_spawn(self):
    #     return self.head.ready_to_spawn
    #
    # @ready_to_spawn.expression
    # def ready_to_spawn(cls):
    #     return (
    #         select(ChainNode.ready_to_spawn)
    #         .where(ChainNode.id == cls.head_id)
    #         .scalar_subquery()
    #     )


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

    target_n_trials
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

    n_completed_trials
        Counts the number of completed trials associated with the node.
        Excludes failed nodes and repeat_trials.

    viable_trials
        Returns all viable trials associated with the node,
        i.e. all trials that have not failed.
    """

    __extra_vars__ = TrialNode.__extra_vars__.copy()

    key = Column(String, index=True)
    degree = Column(Integer)
    child_id = Column(Integer, ForeignKey("node.id"), index=True)
    parent_id = Column(Integer, ForeignKey("node.id"), index=True)
    seed = Column(PythonObject, default=lambda: {})
    definition = Column(PythonObject, default=lambda: {})
    context = Column(PythonObject)
    participant_group = Column(String, index=True)
    block = Column(String, index=True)
    propagate_failure = Column(Boolean)

    child = relationship(
        "ChainNode",
        foreign_keys=[child_id],
        remote_side=TrialNode.id,
        uselist=False,
        post_update=True,
    )
    parent = relationship(
        "ChainNode",
        foreign_keys=[parent_id],
        remote_side=TrialNode.id,
        uselist=False,
        post_update=True,
    )

    def __init__(
        self,
        *,
        definition=None,
        context=None,
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

        if participant_group is None:
            if parent:
                participant_group = parent.participant_group
            else:
                participant_group = "default"

        if block is None:
            if parent:
                block = parent.block
            else:
                block = "default"

        if degree is None:
            if parent:
                degree = parent.degree + 1
            else:
                degree = 0

        if module_id is None:
            if parent:
                module_id = parent.module_id

        if context is None:
            if parent:
                context = parent.context

        if not definition and not seed and degree == 0:
            seed = self.create_initial_seed(experiment, participant)

        if not definition:
            definition = self.create_definition_from_seed(seed, experiment, participant)

        if assets is None:
            assets = {}

        self.assets = assets
        self.block = block
        self.participant_group = participant_group
        self.degree = degree
        self.module_id = module_id
        self.seed = seed
        self.definition = definition
        self.context = context
        self.propagate_failure = propagate_failure
        self._staged_assets = assets

        if parent:
            parent.child = self
            self.parent = parent

    def create_initial_seed(self, experiment, participant):
        raise NotImplementedError

    def stage_assets(self, experiment):
        self.assets = {}

        # if self.network:
        #     self.assets.update(**self.network.assets)

        for label, asset in self._staged_assets.items():
            if asset.label is None:
                asset.label = label

            asset.parent = self

            if not asset.has_key:
                asset.set_keys()

            asset.receive_node_definition(self.definition)

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

    @hybrid_property
    def target_n_trials(self):
        return self.network.trials_per_node

    @target_n_trials.expression
    def target_n_trials(cls):
        # Does this produce a correlated subquery? Is it problematic for performance?
        # (https://docs.sqlalchemy.org/en/14/orm/extensions/hybrid.html#correlated-subquery-relationship-hybrid)
        return (
            select(ChainNetwork.trials_per_node)
            .where(ChainNetwork.id == cls.network_id)
            .scalar_subquery()
        )

    # @property
    # def ready_to_spawn(self):
    #     return self.reached_target_n_trials

    @property
    def completed_and_processed_trials(self):
        return [
            t
            for t in self.alive_trials
            if (t.complete and t.finalized and not t.is_repeat_trial)
        ]

    @hybrid_property
    def n_completed_and_processed_trials(self):
        return len(self.completed_and_processed_trials)

    @n_completed_and_processed_trials.expression
    def n_completed_and_processed_trials(cls):
        return (
            select(func.count(Trial.id))
            .where(
                Trial.node_id == cls.id,
                Trial.complete,
                Trial.finalized,
                ~Trial.is_repeat_trial,
            )
            .scalar_subquery()
        )

    # column_property(
    #     # select(Trial.node_id, Trial.complete, Trial.finalized, Trial.is_repeat_trial)
    #     select(func.count(Trial.id))
    #     .where(Trial.node_id == TrialNode.id, Trial.complete, Trial.finalized, ~ Trial.is_repeat_trial)
    # )

    @hybrid_property
    def reached_target_n_trials(self):
        return self.n_completed_and_processed_trials >= self.target_n_trials

    @reached_target_n_trials.expression
    def reached_target_n_trials(cls):
        return cls.n_completed_and_processed_trials >= cls.target_n_trials

    @hybrid_property
    def ready_to_spawn(self):
        return self.reached_target_n_trials

    @ready_to_spawn.expression
    def ready_to_spawn(cls):
        return cls.reached_target_n_trials

    @property
    def viable_trials(self):
        return [t for t in self.alive_trials if not t.is_repeat_trial]

    # def reached_target_n_trials(self):
    #     return len(self.completed_and_processed_trials) >= self.target_n_trials

    def fail(self, reason=None):
        if self.network.head.id == self.id:
            self.network.head = self.parent
        super().fail(reason)

    @property
    def failure_cascade(self):
        to_fail = []
        if self.propagate_failure:
            to_fail.append(self.infos)
            if self.child:
                to_fail.append(lambda: [self.child])
        return to_fail

    # @hybrid_property
    # def n_viable_trials(self):
    #     return len(self.viable_trials)
    #
    # @n_viable_trials.expression
    # def n_viable_trials(cls):
    #     return (
    #         select(func.count(Trial.id))
    #         .where(
    #             Trial.node_id == cls.id,
    #             ~ Trial.is_repeat_trial,
    #             ~ Trial.failed,
    #         )
    #         .scalar_subquery()
    #     )


TrialNode.n_viable_trials = column_property(
    select(func.count(Trial.id))
    .where(
        Trial.node_id == TrialNode.id,
        ~Trial.is_repeat_trial,
        ~Trial.failed,
    )
    .scalar_subquery()
)

ChainNetwork.ready_to_spawn = column_property(
    select(ChainNode.ready_to_spawn)
    .where(ChainNode.id == ChainNetwork.head_id)
    .scalar_subquery()
)

ChainNetwork.n_viable_trials_at_head = column_property(
    select(TrialNode.n_viable_trials)
    .where(TrialNode.id == ChainNetwork.head_id)
    .scalar_subquery()
)

ChainNetwork.head_is_awaiting_async_process = column_property(
    select(TrialNode.awaiting_async_process)
    .where(TrialNode.id == ChainNetwork.head_id)
    .scalar_subquery()
)


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

    participant_group = association_proxy("node", "participant_group")
    degree = association_proxy("node", "degree")
    context = association_proxy("node", "context")

    block_position = Column(Integer, index=True)
    block = Column(String, index=True)

    def __init__(self, experiment, node, participant, *args, **kwargs):
        super().__init__(experiment, node, participant, *args, **kwargs)
        if participant.in_module and hasattr(
            participant.module_state, "block_position"
        ):
            self.block_position = participant.module_state.block_position
            self.block = participant.module_state.block

    # @property
    # @extra_var(__extra_vars__)
    # def degree(self):
    #     return self.node.degree
    #
    # @property
    # def node(self):
    #     return self.origin

    @property
    def failure_cascade(self):
        to_fail = []
        if self.propagate_failure:
            if self.node.child:
                to_fail.append(lambda: [self.node.child])
        return to_fail

    @property
    def trial_maker(self):
        return self.node.trial_maker


class ChainTrialMakerState(NetworkTrialMakerState):
    block_order = Column(PythonList)
    block_position = Column(Integer)
    block = Column(String)
    participated_networks = Column(PythonList, default=lambda: [])

    # @hybrid_property
    # def block(self):
    #     return self.block_order[self.block_position]

    @property
    def n_blocks(self):
        return len(self.block_order)

    @property
    def remaining_blocks(self):
        return self.block_order[self.block_position :]

    def set_block_position(self, i):
        self.block_position = i
        self.block = self.block_order[i]

    def go_to_next_block(self):
        self.set_block_position(self.block_position + 1)


ChainTrialMakerState.n_participant_trials_in_trial_maker = column_property(
    select(func.count(ChainTrial.id))
    .where(ChainTrial.module_state_id == ChainTrialMakerState.id)
    .scalar_subquery()
)

ChainTrialMakerState.n_participant_trials_in_block = column_property(
    select(func.count(ChainTrial.id))
    .where(
        ChainTrial.module_state_id == ChainTrialMakerState.id,
        ChainTrial.block_position == ChainTrialMakerState.block_position,
    )
    .scalar_subquery()
)


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

    max_trials_per_participant
        Maximum number of trials that each participant may complete;
        once this number is reached, the participant will move on
        to the next stage in the timeline.

    chains_per_participant
        Number of chains to be created for each participant;
        only relevant if ``chain_type="within"``.

    chains_per_experiment
        Number of chains to be created for the entire experiment;
        only relevant if ``chain_type="across"``.

    max_nodes_per_chain
        Specifies chain length in terms of the
        number of data-collection iterations that are required to complete a chain.
        The number of successful participant trials required to complete the chain then
        corresponds to ``trials_per_node * max_nodes_per_chain``.

    max_nodes_per_chain
        Maximum number of nodes in the chain before the chain is marked as full and no more nodes will be added.

    trials_per_node
        Number of satisfactory trials to be received by the last node
        in the chain before another chain will be added.
        Most paradigms have this equal to 1.

    balance_across_chains
        Whether trial selection should be actively balanced across chains,
        such that trials are preferentially sourced from chains with
        fewer valid trials.

    # balance_strategy
        #   A two-element list that determines how balancing occurs, if ``balance_across_chains`` is ``True``.
        #   If the list contains "across", then the balancing will take into account trials from other participants.
        #   If it contains "within", then the balancing will take into account trials from the present participant.
        #   If both are selected, then the balancing strategy will prioritize balancing within the current participant,
        #   but will use counts from other participants as a tie breaker.

    check_performance_at_end
        If ``True``, the participant's performance
        is evaluated at the end of the series of trials.

    check_performance_every_trial
        If ``True``, the participant's performance
        is evaluated after each trial.

    recruit_mode
        Selects a recruitment criterion for determining whether to recruit
        another participant. The built-in criteria are ``"n_participants"``
        and ``"n_trials"``, though the latter requires overriding of
        :attr:`~psynet.trial.main.TrialMaker.n_trials_still_required`.

    target_n_participants
        Target number of participants to recruit for the experiment. All
        participants must successfully finish the experiment to count
        towards this quota. This target is only relevant if
        ``recruit_mode="n_participants"``.

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

    n_repeat_trials
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

    choose_participant_group
        Only relevant if the trial maker uses nodes with non-default participant groups.
        In this case the experimenter is expected to supply a function that takes participant as an argument
        and returns the chosen participant group for that trial maker.

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

    n_networks : int
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

    state_class = ChainTrialMakerState

    def __init__(
        self,
        *,
        id_,
        trial_class: Type[ChainTrial],
        node_class: Type[ChainNode],
        network_class: Type[ChainNetwork] = None,
        chain_type: str,
        expected_trials_per_participant: int,
        max_trials_per_participant: Optional[int] = None,
        max_trials_per_block: Optional[int] = None,
        max_nodes_per_chain: Optional[int] = None,
        chains_per_participant: Optional[int] = None,
        chains_per_experiment: Optional[int] = None,
        trials_per_node: int = 1,
        n_repeat_trials: int = 0,
        target_n_participants: Optional[int] = None,
        balance_across_chains: bool = False,
        start_nodes=None,
        # balance_strategy: Set[str] = {"within", "across"},
        check_performance_at_end: bool = False,
        check_performance_every_trial: bool = False,
        recruit_mode: str = "n_participants",
        fail_trials_on_premature_exit: bool = False,
        fail_trials_on_participant_performance_check: bool = False,
        propagate_failure: bool = True,
        wait_for_networks: bool = False,
        allow_revisiting_networks_in_across_chains: bool = False,
        assets=None,
        choose_participant_group: Optional[callable] = None,
    ):
        if network_class is None:
            network_class = self.default_network_class

        assert chain_type in ["within", "across"]

        if (
            chain_type == "across"
            and expected_trials_per_participant
            and chains_per_experiment
            and expected_trials_per_participant > chains_per_experiment
            and not allow_revisiting_networks_in_across_chains
        ):
            raise ValueError(
                "In across-participant chain experiments, <expected_trials_per_participant> "
                "cannot exceed <chains_per_experiment> unless ``allow_revisiting_networks_in_across_chains`` "
                "is ``True``."
            )

        if chain_type == "within" and recruit_mode == "n_trials":
            raise ValueError(
                "In within-chain experiments the 'n_trials' recruit method is not available."
            )

        if chain_type == "within":
            assert start_nodes is None or callable(start_nodes)
            assert not (start_nodes is None and chains_per_participant is None)
            assert (
                max_trials_per_participant is not None
                or max_trials_per_block is not None
                or max_nodes_per_chain is not None
            )
        elif chain_type == "across":
            assert (
                start_nodes is None
                or callable(start_nodes)
                or is_list_of(start_nodes, ChainNode)
            )
            if allow_revisiting_networks_in_across_chains:
                assert (
                    max_trials_per_participant is not None
                    or max_trials_per_block is not None
                )
        else:
            raise ValueError(f"Unrecognized chain type: {chain_type}")

        self.start_nodes = start_nodes

        # assert len(balance_strategy) <= 2
        # assert all([x in ["across", "within"] for x in balance_strategy])

        self.node_class = node_class
        self.trial_class = trial_class
        self.chain_type = chain_type
        self.max_trials_per_participant = max_trials_per_participant
        self.max_trials_per_block = max_trials_per_block
        self.chains_per_participant = chains_per_participant
        self.chains_per_experiment = chains_per_experiment
        self.max_nodes_per_chain = max_nodes_per_chain
        self.trials_per_node = trials_per_node
        self.balance_across_chains = balance_across_chains
        # self.balance_strategy = balance_strategy
        self.check_performance_at_end = check_performance_at_end
        self.check_performance_every_trial = check_performance_every_trial
        self.propagate_failure = propagate_failure
        self.allow_revisiting_networks_in_across_chains = (
            allow_revisiting_networks_in_across_chains
        )
        self.choose_participant_group = choose_participant_group

        super().__init__(
            id_=id_,
            trial_class=trial_class,
            network_class=network_class,
            expected_trials_per_participant=expected_trials_per_participant
            + n_repeat_trials,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            recruit_mode=recruit_mode,
            target_n_participants=target_n_participants,
            n_repeat_trials=n_repeat_trials,
            wait_for_networks=wait_for_networks,
            assets=assets,
        )

        self.check_initialization()

    def check_initialization(self):
        pass

    def check_participant_groups(self, networks):
        for n in networks:
            if (
                n.participant_group != "default"
                and self.choose_participant_group is None
            ):
                raise ValueError(
                    f"Since the Trial Maker's starting nodes contain a non-default participant_group "
                    f"({n.participant_group}), you must provide a value for the choose_participant_groups "
                    "argument. This should be a function that takes 'participant' as an argument and returns "
                    "the participant group chosen for that Trial Maker."
                )

    @property
    def default_network_class(self):
        return ChainNetwork

    def init_participant(self, experiment, participant):
        super().init_participant(experiment, participant)
        participant.module_state.participated_networks = []
        if self.chain_type == "within":
            networks = self.create_networks_within(experiment, participant)
        else:
            networks = self.networks
            if len(self.networks) == 0:
                raise RuntimeError(
                    f"Couldn't find any networks for the trial maker '{participant.module_state.module_id}'. "
                    "A common reason for this is deploying your experiment using 'dallinger deploy' instead of "
                    "'psynet deploy'. "
                    "Another common reason is reloading the experiment in debug mode after adding a new trial maker. "
                    "In the latter case you need to restart the debug session before continuing."
                )
        blocks = set([network.block for network in networks])
        self.init_block_order(experiment, participant, blocks)
        participant.module_state.set_block_position(0)
        self.check_participant_groups(networks)

    def init_block_order(self, experiment, participant, blocks):
        block_order = call_function_with_context(
            self.choose_block_order,
            experiment=experiment,
            participant=participant,
            blocks=blocks,
        )
        participant.module_state.block_order = block_order

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
        return random.sample(list(blocks), len(blocks))

    def _should_finish_block(self, participant):
        state = participant.module_state

        assert state.block is not None
        assert state.block_position is not None

        # Used to pass these for convenience, but it produces unnecessary computation.
        # Keeping the code here though in case people overriding this function want
        # to make use of these.
        #
        # trials_in_trial_maker = [
        #     trial for trial in participant.all_trials if trial.trial_maker_id == self.id
        # ]
        # trials_in_block = [
        #     trial
        #     for trial in trials_in_trial_maker
        #     if trial.block_position == block_position
        # ]

        return self.should_finish_block(
            participant,
            state.block,
            state.block_position,
            state.n_participant_trials_in_block,
            state.n_participant_trials_in_trial_maker,
        )

    def should_finish_block(
        self,
        participant,  # noqa
        block,  # noqa
        block_position,  # noqa
        n_participant_trials_in_block,
        n_participant_trials_in_trial_maker,
    ):  # noqa
        return (
            self.max_trials_per_block is not None
            and n_participant_trials_in_block >= self.max_trials_per_block
        ) or (
            self.max_trials_per_participant is not None
            and n_participant_trials_in_trial_maker >= self.max_trials_per_participant
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
    def n_trials_still_required(self):
        assert self.chain_type == "across"
        return sum([network.n_trials_still_required for network in self.networks])

    #########################
    # Participated networks #
    #########################

    def pre_deploy_routine(self, experiment):
        if self.chain_type == "across":
            self.create_networks_across(experiment)

    def create_networks_within(self, experiment, participant):
        if self.start_nodes:
            nodes = call_function_with_context(
                self.start_nodes, experiment=experiment, participant=participant
            )
            if self.chains_per_participant is not None:
                assert len(nodes) == self.chains_per_participant, (
                    f"Problem with trial maker {self.id}: "
                    f"The number of nodes generated by start_nodes ({len(nodes)} did not equal "
                    f"chains_per_participant ({self.chains_per_participant})."
                )
        else:
            nodes = [None for _ in range(self.chains_per_participant)]

        networks = []
        for i, node in enumerate(nodes):
            network = self.create_network(
                experiment, participant, id_within_participant=i, start_node=nodes[i]
            )
            # self._grow_network(network, experiment)  # not necessary any more!
            networks.append(network)
            if node:
                node.check_on_deploy()

        db.session.commit()

        return networks

    def create_networks_across(self, experiment):
        if self.start_nodes:
            if callable(self.start_nodes):
                nodes = call_function_with_context(
                    self.start_nodes, experiment=experiment
                )
            else:
                nodes = self.start_nodes
                assert isinstance(nodes, list)
            if self.chains_per_experiment:
                assert len(nodes) == self.chains_per_experiment, (
                    f"Problem with trial maker {self.id}: "
                    f"The number of nodes provided by start_nodes ({len(nodes)}) did not equal 0 or "
                    f"chains_per_experiment ({self.chains_per_experiment})."
                )
        else:
            nodes = [None for _ in range(self.chains_per_experiment)]
        for node in nodes:  # type: ChainNode
            self.create_network(experiment, start_node=node)
            if node is not None:
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
            target_n_nodes=self.max_nodes_per_chain,
            participant=participant,
            id_within_participant=id_within_participant,
        )
        db.session.add(network)
        start_node.set_network(network)
        db.session.commit()  # TODO - remove this for efficiency?
        return network

    @log_time_taken
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
        participant.module_state  # type: ChainTrialMakerState

        db.session.commit()
        logger.info(
            "Looking for networks for participant %i.",
            participant.id,
        )
        n_completed_trials = participant.module_state.n_completed_trials
        if (
            self.max_trials_per_participant is not None
            and n_completed_trials >= self.max_trials_per_participant
        ):
            logger.info(
                "N completed trials (%i) >= N trials per participant (%i), skipping forward",
                n_completed_trials,
                self.max_trials_per_participant,
            )
            return "exit"

        if self._should_finish_block(participant):
            if (
                participant.module_state.block_position + 1
                >= participant.module_state.n_blocks
            ):
                return "exit"
            else:
                participant.module_state.go_to_next_block()

        # networks = db.session.query(
        #     self.network_class.chain_type,
        #     self.network_class.head,
        # ,
        # )
        #
        #
        networks = self.network_class.query.filter_by(
            trial_maker_id=self.id, full=False
        )

        # logger.info(
        #     "There are %i non-full networks for trialmaker %s.",
        #     networks.count(),
        #     self.id,
        # )

        if self.chain_type == "within":
            networks = self.filter_by_participant_id(networks, participant)
        elif (
            self.chain_type == "across"
            and not self.allow_revisiting_networks_in_across_chains
        ):
            networks = self.exclude_participated(networks, participant)

        participant_group = participant.module_state.participant_group
        networks = networks.filter_by(participant_group=participant_group)

        # logger.info(
        #     "%i of these networks match the current participant group (%s).",
        #     networks.count(),
        #     participant_group,
        # )

        networks = networks.all()

        networks = self.custom_network_filter(
            candidates=networks, participant=participant
        )

        logger.info("%i remain after applying custom network filters.", len(networks))

        if not isinstance(networks, list):
            return TypeError("custom_network_filter must return a list of networks")

        def has_pending_process(network):
            return (
                network.awaiting_async_process or network.head_is_awaiting_async_process
            )

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
            n for n in networks if n.n_viable_trials_at_head < self.trials_per_node
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
            networks.sort(key=lambda network: network.n_completed_trials)

            # if "across" in self.balance_strategy:
            #     networks.sort(key=lambda network: network.n_completed_trials)
            # if "within" in self.balance_strategy:
            #     networks.sort(
            #         key=lambda network: len(
            #             [
            #                 t
            #                 for t in network.alive_trials
            #                 if t.participant_id == participant.id
            #             ]
            #         )
            #     )

        current_block = participant.module_state.block
        remaining_blocks = participant.module_state.remaining_blocks
        networks = [n for n in networks if n.block in remaining_blocks]
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
        # logger.info(
        #     "%i of these belong to participant %i.",
        #     query.count(),
        #     participant.id,
        # )
        return query

    def exclude_participated(self, networks, participant):
        query = networks.filter(
            not_(
                self.network_class.id.in_(
                    participant.module_state.participated_networks
                )
            )
        )
        # logger.info(
        #     "%i of these are available once you exclude already-visited networks.",
        #     query.count(),
        # )
        return query

    @log_time_taken
    def grow_network(self, network, experiment):
        # We set participant = None because of Dallinger's constraint of not allowing participants
        # to create nodes after they have finished working.
        participant = None
        if network.ready_to_spawn:
            head = network.head
            with time_logger("create seed", indent=4):
                seed = head.create_seed(experiment, participant)
            with time_logger("create node", indent=4):
                node = self.node_class(
                    seed=seed,
                    parent=head,
                    network=network,
                    experiment=experiment,
                    propagate_failure=self.propagate_failure,
                    participant=participant,
                )
            with time_logger("add node to DB", indent=4):
                db.session.add(node)
                network.add_node(node)
                db.session.commit()
            with time_logger("creation checks", indent=4):
                node.check_on_create()
                node.check_on_deploy()
            with time_logger("final commit", indent=4):
                db.session.commit()
            return True
        return False

    @log_time_taken
    def find_node(self, network, participant, experiment):
        return network.head

    def finalize_trial(self, answer, trial, experiment, participant):
        super().finalize_trial(answer, trial, experiment, participant)
        participant.module_state.participated_networks.append(trial.network_id)
