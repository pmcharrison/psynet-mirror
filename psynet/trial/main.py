# pylint: disable=unused-argument

import datetime
import random
from math import isnan
from typing import List, Optional, Union

import dallinger.experiment
import dallinger.models
import dallinger.nodes
from dallinger import db
from dallinger.models import Info, Network
from dominate import tags
from flask import Markup
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, func, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import column_property, deferred, relationship
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.collections import attribute_mapped_collection

from psynet import field

from ..asset import AssetNetwork, AssetNode, AssetTrial
from ..data import SQLMixinDallinger
from ..field import PythonDict, PythonObject, VarStore, extra_var, register_extra_var
from ..page import InfoPage, UnsuccessfulEndPage, WaitPage, wait_while
from ..participant import Participant
from ..process import AsyncProcess, WorkerAsyncProcess
from ..timeline import (
    CodeBlock,
    DatabaseCheck,
    Module,
    ModuleState,
    PageMaker,
    ParticipantFailRoutine,
    PreDeployRoutine,
    RecruitmentCriterion,
    RegisterTrialMaker,
    conditional,
    join,
    switch,
    while_loop,
)
from ..utils import (
    NoArgumentProvided,
    call_function,
    call_function_with_context,
    corr,
    get_logger,
    is_method_overridden,
    log_time_taken,
)

logger = get_logger()


def with_trial_maker_namespace(trial_maker_id: str, x: Optional[str] = None):
    if x is None:
        return trial_maker_id
    return f"{trial_maker_id}__{x}"


# Patch the missing foreign_keys argument for the Info.origin relationship
Info.origin = relationship("dallinger.models.Node", foreign_keys=[Info.origin_id])


class Trial(SQLMixinDallinger, Info):
    """
    Represents a trial in the experiment.
    The user is expected to override the following methods:

    * :meth:`~psynet.trial.main.Trial.make_definition`,
      responsible for deciding on the content of the trial.
    * :meth:`~psynet.trial.main.Trial.show_trial`,
      determines how the trial is turned into a webpage for presentation to the participant.
    * :meth:`~psynet.trial.main.Trial.show_feedback`,
      defines an optional feedback page to be displayed after the trial.

    The user must also override the ``time_estimate`` class attribute,
    providing the estimated duration of the trial in seconds.
    This is used for predicting the participant's bonus payment
    and for constructing the progress bar.

    The user may also wish to override the
    :meth:`~psynet.trial.main.Trial.async_post_trial` method
    if they wish to implement asynchronous trial processing.

    They may also override the
    :meth:`~psynet.trial.main.Trial.score_answer` method
    if they wish to implement trial-level scoring;
    for scoring methods that work by analyzing multiple trials at the same time
    (e.g., test-retest correlations), see the trial maker method
    :meth:`~psynet.trial.main.TrialMaker.performance_check`.

    This class subclasses the :class:`~dallinger.models.Info` class from Dallinger,
    hence can be found in the ``Info`` table in the database.
    It inherits this class's methods, which the user is welcome to use
    if they seem relevant.

    Instances can be retrieved using *SQLAlchemy*; for example, the
    following command retrieves the ``Trial`` object with an ID of 1:

    ::

        Trial.query.filter_by(id=1).one()

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

    Attributes
    ----------

    time_estimate : numeric
        The estimated duration of the trial (including any feedback), in seconds.
        This should generally correspond to the (sum of the) ``time_estimate`` parameters in
        the page(s) generated by ``show_trial``, plus the ``time_estimate`` parameter in
        the page generated by ``show_feedback`` (if defined).
        This is used for predicting the participant's bonus payment
        and for constructing the progress bar.

    participant_id : int
        The ID of the associated participant.
        The user should not typically change this directly.
        Stored in ``property1`` in the database.

    node
        The :class:`dallinger.models.Node` to which the :class:`~dallinger.models.Trial`
        belongs.

    complete : bool
        Whether the trial has been completed (i.e. received a response
        from the participant). The user should not typically change this directly.

    finalized : bool
        Whether the trial has been finalized. This is a stronger condition than ``complete``;
        in particular, a trial is only marked as finalized once its async processes
        have completed (if it has any).
        One day we might extend this to include arbitrary conditions,
        for example waiting for another user to evaluate that trial, or similar.

    answer : Object
        The response returned by the participant. This is serialised
        to JSON, so it shouldn't be too big.
        The user should not typically change this directly.
        Stored in ``details`` in the database.

    parent_trial_id : int
        If the trial is a repeat trial, this attribute corresponds to the ID
        of the trial from which that repeat trial was cloned.

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

    run_async_post_trial : bool
        Set this to ``False`` if you want to disable :meth:`~psynet.trial.main.Trial.async_post_trial`.
        This is only included for back-compatibility.

    wait_for_feedback : bool
        Set this class attribute to ``False`` if you don't want to wait for asynchronous processes
        to complete before giving feedback. The default is to wait.

    accumulate_answers : bool
        Set this class attribute to ``True`` if the trial contains multiple pages and you want
        the answers to all of these pages to be stored as a dict in ``participant.answer``.
        Otherwise, the default behaviour is to only store the answer from the final page.

    time_credit_before_trial: float
        Reports the amount of time credit that the participant had before they started the trial (in seconds).

    time_credit_after_trial: float
        Reports the amount of time credit that the participant had after they finished the trial (in seconds).

    time_credit_from_trial: float
        Reports the amount of time credit that was allocated to the participant on the basis of this trial (in seconds).
        This should be equal to ``time_credit_after_trial - time_credit_before_trial``.

    check_time_credit_received : bool
        If ``True`` (default), PsyNet will check at the end of the trial whether the participant received
        the expected amount of time credit. If the received amount is inconsistent with the amount
        specified by ``time_estimate``, then a warning message will be delivered,
        suggesting a revised value for ``time_estimate``.

    response_id : int
        ID of the associated :class:`~psynet.timeline.Response` object.
        Equals ``None`` if no such object has been created yet.

    response :
        The associated :class:`~psynet.timeline.Response` object,
        which records in detail the response received from the participant's web browser.
        Equals ``None`` if no such object has been created yet.
    """

    # pylint: disable=unused-argument
    __extra_vars__ = SQLMixinDallinger.__extra_vars__.copy()

    node_id = Column(Integer, ForeignKey("node.id"), index=True)
    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    # module_id = Column(String)
    module_id = association_proxy("module_state", "module_id")
    module_state_id = Column(Integer, ForeignKey("module_state.id"), index=True)
    module_state = relationship("ModuleState", foreign_keys=[module_state_id])
    trial_maker_id = Column(String, index=True)
    definition = Column(PythonObject)
    complete = Column(Boolean)
    finalized = Column(Boolean)
    is_repeat_trial = Column(Boolean)
    score = Column(Float)
    bonus = Column(Float)
    parent_trial_id = Column(Integer, ForeignKey("info.id"), index=True)
    answer = Column(PythonObject)
    propagate_failure = Column(Boolean)
    response_id = Column(Integer, ForeignKey("response.id"), index=True)
    repeat_trial_index = Column(Integer)
    n_repeat_trials = Column(Integer)
    time_taken = Column(Float)
    _initial_assets = deferred(Column(PythonDict))
    time_credit_before_trial = Column(Float)
    time_credit_after_trial = Column(Float)
    time_credit_from_trial = Column(Float)

    node = relationship(
        "TrialNode", foreign_keys=[node_id], back_populates="all_trials"
    )
    participant = relationship(
        "psynet.participant.Participant",
        foreign_keys=[participant_id],
        backref="all_trials",
        post_update=True,
    )
    parent_trial = relationship(
        "psynet.trial.main.Trial", foreign_keys=[parent_trial_id]
    )
    response = relationship("psynet.timeline.Response")

    async_processes = relationship("AsyncProcess")
    awaiting_async_process = column_property(
        select(AsyncProcess.trial_id, AsyncProcess.pending)
        .where(AsyncProcess.trial_id == Info.id, AsyncProcess.pending)
        .exists()
    )
    register_extra_var(__extra_vars__, "awaiting_async_process")

    asset_links = relationship(
        "AssetTrial",
        collection_class=attribute_mapped_collection("label"),
        cascade="all, delete-orphan",
    )

    assets = association_proxy(
        "asset_links", "asset", creator=lambda k, v: AssetTrial(label=k, asset=v)
    )

    errors = relationship("ErrorRecord")

    time_estimate = None
    check_time_credit_received = True

    wait_for_feedback = True  # determines whether feedback waits for async_post_trial
    accumulate_answers = False

    @property
    def var(self):
        return VarStore(self)

    @property
    def position(self):
        """
        Returns the position of the current trial within that participant's current trial maker (0-indexed).
        This can be used, for example, to display how many trials the participant has taken so far.
        """
        trials = self.get_for_participant(
            self.participant_id, self.network.trial_maker_id
        )
        trial_ids = [t.id for t in trials]
        return trial_ids.index(self.id)

    @classmethod
    def get_for_participant(cls, participant_id: int, trial_maker_id: int = None):
        """
        Returns all trials for a given participant.
        """
        query = (
            db.session.query(cls)
            .join(TrialNetwork)
            .filter(Trial.participant_id == participant_id)
        )
        if trial_maker_id is not None:
            query = query.filter(TrialNetwork.trial_maker_id == trial_maker_id)
        return query.order_by(Trial.id).all()

    @property
    def visualization_html(self):
        experiment = dallinger.experiment.load()
        participant = self.participant
        page = self.show_trial(experiment=experiment, participant=participant)
        return page.visualize(trial=self)

    def fail(self, reason=None):
        if not self.failed:
            super().fail(reason=reason)

    @property
    def ready_for_feedback(self):
        """
        Determines whether a trial is ready to give feedback to the participant.
        """
        if not self.complete:
            return False
        if self.wait_for_feedback:
            if self.awaiting_async_process:
                logger.info(
                    "Waiting for async process to complete for trial %i", self.id
                )
                return False
            if self.awaiting_asset_deposit:
                logger.info(
                    "Waiting for asset deposit to complete for trial %i", self.id
                )
                return False
        return True

    @property
    def awaiting_asset_deposit(self):
        db.session.commit()
        for asset in self.assets.values():
            if (
                isinstance(asset.parent, Trial)
                and asset.parent.id == self.id
                and not asset.deposited
            ):
                return True
        return False

    #################

    def __init__(
        self,
        experiment,
        node,
        participant,
        propagate_failure,  # If the trial fails, should its failure be propagated to its descendants?
        is_repeat_trial,  # Is the trial a repeat trial?
        parent_trial=None,  # If the trial is a repeat trial, what is its parent?
        repeat_trial_index=None,  # Only relevant if the trial is a repeat trial
        n_repeat_trials=None,  # Only relevant if the trial is a repeat trial
        assets=None,
        definition=NoArgumentProvided,  # If provided, overrides make definition
    ):
        super().__init__(origin=node)
        self.node = node
        # self.node_id = node.id
        self.complete = False
        self.finalized = False
        self.participant_id = participant.id
        self.propagate_failure = propagate_failure
        self.is_repeat_trial = is_repeat_trial
        self.parent_trial_id = None if parent_trial is None else parent_trial.id
        self.repeat_trial_index = repeat_trial_index
        self.n_repeat_trials = n_repeat_trials
        self.score = None
        self.response_id = None
        self.time_taken = None
        self.trial_maker_id = node.trial_maker_id
        self.module_state = participant.module_state
        # self.module_id = node.module_id

        if assets is None:
            assets = {}

        if is_repeat_trial:
            self.definition = parent_trial.definition
            for k, v in parent_trial._initial_assets.items():
                self.assets[k] = v
        else:
            self.assets = {
                **node.assets,
                **assets,
            }
            if definition == NoArgumentProvided:
                self.definition = self.make_definition(experiment, participant)
                assert self.definition is not None

                self.definition = self.finalize_definition(
                    self.definition, experiment, participant
                )
                flag_modified(self, "definition")

                assert self.definition is not None
            else:
                self.definition = definition

            db.session.add(self)
            db.session.commit()

            self._finalize_assets()

    def to_dict(self):
        x = super().to_dict()
        field.json_unpack_answer(x)
        return x

    @property
    def trial_maker(self):
        from ..experiment import get_trial_maker

        if self.trial_maker_id:
            return get_trial_maker(self.trial_maker_id)

    @property
    def contents(self):
        return self.answer

    @contents.setter
    def contents(self, x):
        self.answer = x

    def _allocate_bonus(self):
        bonus = self.compute_bonus(score=self.score)
        assert isinstance(bonus, (float, int))
        self._log_bonus(bonus)
        self.bonus = bonus
        self.participant.inc_performance_bonus(bonus)

    def _log_bonus(self, bonus):
        logger.info(
            "Allocating a performance bonus of $%.2f to participant %i for trial %i.",
            bonus,
            self.participant.id,
            self.id,
        )

    def add_assets(self, assets: dict):
        for label, asset in assets.items():
            self.add_asset(label, asset)

    def add_asset(self, label, asset):
        db.session.add(self)
        db.session.commit()

        if not asset.parent:
            asset.parent = self

        asset.receive_node_definition(self.definition)

        if not asset.has_key:
            asset.label = label
            asset.set_keys()

        db.session.add(asset)

        self.assets[label] = asset

        db.session.commit()

        if not asset.deposited:
            asset.deposit()

    def score_answer(self, answer, definition):
        """
        Scores the participant's answer. At the point that this method is called,
        any pending asynchronous processes should already have been completed.

        Parameters
        ----------
        answer :
            The answer provided to the trial.

        definition :
            The trial's definition

        Returns
        -------

        A numeric score quantifying the participant's success.
        The experimenter is free to decide the directionality
        (whether high scores are better than low scores, or vice versa).
        Alternatively, ``None`` indicating no score.
        """
        return None

    def compute_bonus(self, score):
        """
        Computes a bonus to allocate to the participant as a reward for the current trial.
        By default, no bonus is given.
        Note: this trial-level bonus system is complementary to the trial-maker-level bonus system,
        which computes an overall bonus for the participant at the end of a trial maker.
        It is possible to use these two bonus systems independently or simultaneously.
        See :meth:`~psynet.trial.main.TrialMaker.compute_bonus` for more details.

        Parameters
        ----------

        score:
            The score achieved by the participant, as computed by :meth:`~psynet.trial.main.Trial.score_answer`.

        Returns
        -------

        The resulting bonus, typically in dollars.
        """
        return 0.0

    def json_data(self):
        x = super().json_data()
        x["participant_id"] = self.participant_id
        return x

    def make_definition(self, experiment, participant):
        """
        Creates and returns a definition for the trial,
        which will be later stored in the ``definition`` attribute.
        This can be an arbitrary object as long as it
        is serialisable to JSON.

        Parameters
        ----------

        experiment:
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant:
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """
        raise NotImplementedError

    def finalize_definition(self, definition, experiment, participant):
        """
        This can be overridden to add additional randomized trial properties.
        For example:

        ::

            definition["bass_note"] = random.sample(10)

        It can also be used to add FastFunctionAssets:

        ::

            self.add_assets({
                "audio": FastFunctionAsset(
                    function=synth_stimulus,
                    extension=".wav",
                )
        """
        return definition

    def _finalize_assets(self):
        db.session.commit()
        assert self.id is not None
        for _, asset in self.assets.items():
            asset.receive_node_definition(self.definition)
            if not asset.deposited:
                asset.deposit()
        db.session.commit()

    def show_trial(self, experiment, participant):
        """
        Returns a :class:`~psynet.timeline.Page` object,
        or alternatively a list of such objects,
        that solicits an answer from the participant.

        Parameters
        ----------

        experiment:
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant:
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """
        raise NotImplementedError

    def show_feedback(self, experiment, participant):
        """
        Returns a Page object displaying feedback
        (or None, which means no feedback).

        Parameters
        ----------

        experiment:
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant:
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """
        return None

    def _show_feedback(self, experiment, participant):
        return self.show_feedback(experiment=experiment, participant=participant)

    def gives_feedback(self, experiment, participant):
        return is_method_overridden(self, Trial, "show_feedback")
        # return (
        #     self._show_feedback(experiment=experiment, participant=participant)
        #     is not None
        # )

    run_async_post_trial = None

    def async_post_trial(self):
        """
        Optional function to be run after a trial is completed by the participant.
        Will only run if :attr:`~psynet.trial.main.Trial.run_async_post_trial`
        is set to ``True``.
        """
        raise NotImplementedError

    def call_async_post_trial(self):
        dallinger.experiment.load()
        db.session.commit()
        self.async_post_trial()
        self.check_if_can_mark_as_finalized()

    def fail_async_processes(self, reason):
        super().fail_async_processes(reason)
        self.fail(reason="fail_async_processes")

    def new_repeat_trial(self, experiment, repeat_trial_index, n_repeat_trials):
        repeat_trial = self.__class__(
            experiment=experiment,
            node=self.origin,
            participant=self.participant,
            propagate_failure=False,
            is_repeat_trial=True,
            parent_trial=self,
            repeat_trial_index=repeat_trial_index,
            n_repeat_trials=n_repeat_trials,
        )
        return repeat_trial

    def check_if_can_mark_as_finalized(self):
        if self.failed:
            logger.info("Cannot mark as finalized because the trial is failed.")
        elif self.awaiting_asset_deposit:
            logger.info(
                "Cannot mark as finalized yet because the trial is awaiting an asset deposit."
            )
        elif self.awaiting_async_process:
            logger.info(
                "Cannot mark as finalized yet because the trial is awaiting an async process."
            )
        else:
            self.finalized = True
            db.session.commit()
            self.on_finalized()

    def check_if_can_run_async_post_trial(self):
        logger.info("Checking if can run async_post_trial.")
        db.session.commit()
        if self.run_async_post_trial is not None and not self.run_async_post_trial:
            logger.info(
                "run_async_post_trial is False, so we won't run async_post_trial."
            )
        elif self.awaiting_asset_deposit:
            logger.info(
                "The trial is awaiting an asset deposit, so we won't run async_post_trial."
            )
        elif not is_method_overridden(self, Trial, "async_post_trial"):
            logger.info("No async_post_trial method is defined, skipping.")
        else:
            logger.info(
                "All conditions seem to be satisfied, calling call_async_post_trial if it hasn't been called already."
            )
            WorkerAsyncProcess(
                self.call_async_post_trial,
                label="post_trial",
                timeout=self.trial_maker.async_timeout_sec,
                trial=self,
                unique=True,
                unique_violation_raises_error=False,  # Pass silently if the process has already been started
            )

    def on_finalized(self):
        self.score = self.score_answer(answer=self.answer, definition=self.definition)
        self._allocate_bonus()

        db.session.commit()

        if self.trial_maker:
            from psynet.experiment import get_experiment

            experiment = get_experiment()
            self.trial_maker._grow_network(self.network, experiment)

    @classmethod
    def cue(cls, definition, assets=None):
        """
        Use this method to add a trial directly into a timeline,
        without needing to create a corresponding trial maker.

        Parameters
        ----------

        definition :
            This can be a ``dict`` object, which will then be saved to the trial's ``definition`` slot.
            Alternatively, it can be a ``Node`` object, in which case the ``Node`` object
            will be saved to ``trial.node``, and ``node.definition`` will be saved
            to ``trial.definition``.

        assets :
            Optional dictionary of assets to add to the trial (in addition to any provided by
            providing a ``Source`` containing assets to the ``definition`` parameter).
        """
        from psynet.trial.chain import ChainNode

        if isinstance(definition, ChainNode):
            node = definition
            cls.check_node_is_valid(node)
            definition = node.definition
        elif isinstance(definition, dict):
            node = None
        else:
            raise TypeError(f"Invalid definition type: {type(definition)}")

        def _register_trial(experiment, participant):
            nonlocal node

            if not node:
                node = cls.get_default_parent_node(participant, experiment)

            trial = cls(
                experiment,
                node,
                participant,
                propagate_failure=False,
                is_repeat_trial=False,
                definition=definition,
            )
            db.session.add(trial)
            participant.current_trial = trial
            db.session.commit()

            if assets:
                trial.add_assets(assets)

        return join(
            CodeBlock(_register_trial),
            cls.trial_logic(),
        )

    @classmethod
    def get_default_parent_node(cls, participant, experiment):
        module_id = participant.module_id
        try:
            return TrialNode.query.filter_by(
                module_id=module_id,
            ).one()
        except NoResultFound:
            node = GenericTrialNode(module_id, experiment)
            db.session.add(node)
            db.session.commit()
            node.check_on_create()
            node.check_on_deploy()
            return node

    @classmethod
    def check_node_is_valid(cls, source):
        from sqlalchemy import inspect

        if not inspect(source).persistent:
            raise ValueError(
                f"The node with definition {source.definition} looks like it hasn't "
                "been registered in the database. This normally means that you are trying to "
                "access the node object in the wrong way. You should access it by writing "
                "(within a PageMaker or CodeBlock) "
                "lambda nodes: nodes['your_node_key'], "
                "or by writing a SQLAlchemy query, e.g. Node.query.filter_by(...).one()."
            )

    @classmethod
    def trial_logic(cls, trial_maker=None):
        time_estimate = cls._get_trial_time_estimate(trial_maker)

        return join(
            CodeBlock(cls._log_time_credit_before_trial),
            PageMaker(
                lambda experiment, participant: participant.current_trial._show_trial(
                    experiment, participant
                ),
                time_estimate=time_estimate,
                accumulate_answers=cls.accumulate_answers,
            ),
            cls._finalize_trial(trial_maker),
            cls._construct_feedback_logic(trial_maker),
            CodeBlock(cls._log_time_credit_after_trial),
        )

    @classmethod
    def _get_trial_time_estimate(cls, trial_maker):
        if cls.time_estimate is not None:
            return cls.time_estimate
        elif trial_maker.time_estimate_per_trial is not None:
            return trial_maker.time_estimate_per_trial
        else:
            raise AttributeError(
                f"You need to provide either time_estimate as a class attribute of {cls.__name__} "
                "or time_estimate_per_trial as a class/instance attribute of the corresponding trial maker."
            )

    def _show_trial(self, experiment, participant):
        return call_function_with_context(
            self.show_trial,
            experiment=experiment,
            participant=participant,
            trial_maker=self.trial_maker,
        )

    @classmethod
    def _get_current_time_credit(cls, participant):
        return participant.time_credit.confirmed_credit

    @classmethod
    def _log_time_credit_before_trial(cls, participant):
        trial = participant.current_trial
        trial.time_credit_before_trial = cls._get_current_time_credit(participant)

    @classmethod
    def _log_time_credit_after_trial(cls, participant):
        trial = participant.current_trial
        trial.time_credit_after_trial = cls._get_current_time_credit(participant)
        trial.time_credit_from_trial = (
            trial.time_credit_after_trial - trial.time_credit_before_trial
        )
        if trial.check_time_credit_received:
            original_estimate = cls._get_trial_time_estimate(
                trial_maker=trial.trial_maker
            )
            actual = trial.time_credit_from_trial
            if actual != original_estimate:
                logger.info(
                    f"Warning: Trial {trial.id} received an unexpected amount of time credit "
                    f"(expected = {original_estimate} seconds; "
                    f"actual = {actual} seconds). "
                    f"Consider setting the trial's `time_estimate` parameter to {trial.time_credit_from_trial}."
                    "You can disable this warning message by setting `Trial.check_time_credit_received = False`."
                )

    @classmethod
    def _finalize_trial(cls, trial_maker=None):
        def f(participant, experiment):
            logger.info("Calling _finalize_trial.")

            trial = participant.current_trial
            answer = participant.answer

            trial.answer = answer
            trial.complete = True
            trial.response_id = participant.last_response_id
            trial.time_taken = trial.response.metadata["time_taken"]

            if trial_maker:
                trial_maker.finalize_trial(
                    answer=trial.answer,
                    trial=trial,
                    experiment=experiment,
                    participant=participant,
                )

            db.session.commit()

            logger.info(
                "Calling check_if_can_run_async_post_trial as part of _finalize_trial."
            )
            trial.check_if_can_run_async_post_trial()

            trial.check_if_can_mark_as_finalized()

        return CodeBlock(f)

    @classmethod
    def _construct_feedback_logic(cls, trial_maker):
        if trial_maker:
            label = trial_maker.with_namespace("feedback")
        else:
            label = f"{cls.__name__}__feedback"

        return conditional(
            label=label,
            condition=lambda experiment, participant: (
                participant.current_trial.gives_feedback(experiment, participant)
            ),
            logic_if_true=join(
                wait_while(
                    lambda participant: not participant.current_trial.ready_for_feedback,
                    expected_wait=0,
                    log_message="Waiting for feedback to be ready.",
                    check_interval=1.0,
                ),
                PageMaker(
                    lambda experiment, participant: (
                        participant.current_trial.show_feedback(
                            experiment=experiment, participant=participant
                        )
                    ),
                    time_estimate=0,
                ),
            ),
            fix_time_credit=False,
            log_chosen_branch=False,
        )


class TrialMakerState(ModuleState):
    participant_group = Column(String)
    in_repeat_phase = Column(Boolean)
    performance_check = Column(PythonDict)
    trials_to_repeat = Column(PythonObject)
    repeat_trial_index = Column(Integer)
    n_completed_trials = Column(Integer, default=0, server_default="0")


class TrialMaker(Module):
    """
    Generic trial generation module, to be inserted
    in an experiment timeline. It is responsible for organising
    the administration of trials to the participant.

    Users are invited to override the following abstract methods/attributes:

    * :meth:`~psynet.trial.main.TrialMaker.prepare_trial`,
      which prepares the next trial to administer to the participant.

    * :meth:`~psynet.trial.main.TrialMaker.pre_deploy_routine`
      (optional), which defines a routine that sets up the experiment
      in advance of deployment (for example initialising and seeding networks).

    * :meth:`~psynet.trial.main.TrialMaker.init_participant`
      (optional), a function that is run when the participant begins
      this sequence of trials, intended to initialize the participant's state.
      Make sure you call ``super().init_participant`` when overriding this.

    * :meth:`~psynet.trial.main.TrialMaker.finalize_trial`
      (optional), which finalizes the trial after the participant
      has given their response.

    * :meth:`~psynet.trial.main.TrialMaker.on_complete`
      (optional), run once the sequence of trials is complete.

    * :meth:`~psynet.trial.main.TrialMaker.performance_check`
      (optional), which checks the performance of the participant
      with a view to rejecting poor-performing participants.

    * :meth:`~psynet.trial.main.TrialMaker.compute_bonus`;
      computes the final performance bonus to assign to the participant.

    * :attr:`~psynet.trial.main.TrialMaker.n_trials_still_required`
      (optional), which is used to estimate how many more participants are
      still required in the case that ``recruit_mode="n_trials"``.

    * :attr:`~psynet.trial.main.TrialMaker.give_end_feedback_passed`
      (default = ``False``); if ``True``, then participants who pass the
      final performance check will be given feedback. This feedback can
      be customised by overriding
      :meth:`~psynet.trial.main.TrialMaker.get_end_feedback_passed_page`.

    Users are also invited to add new recruitment criteria for selection with
    the ``recruit_mode`` argument. This may be achieved using a custom subclass
    of :class:`~psynet.trial.main.TrialMaker` as follows:

    ::

        class CustomTrialMaker(TrialMaker):
            def new_recruit(self, experiment):
                if experiment.my_condition:
                    return True # True means recruit more
                else:
                    return False # False means don't recruit any more (for now)

            recruit_criteria = {
                **TrialMaker.recruit_criteria,
                "new_recruit": new_recruit
            }

    With the above code, you'd then be able to use ``recruit_mode="new_recruit"``.
    If you're subclassing a subclass of :class:`~psynet.trial.main.TrialMaker`,
    then just replace that subclass wherever :class:`~psynet.trial.main.TrialMaker`
    occurs in the above code.

    Parameters
    ----------

    trial_class
        The class object for trials administered by this maker.

    expected_trials_per_participant
        Expected number of trials that the participant will take,
        including repeat trials
        (used for progress estimation).

    check_performance_at_end
        If ``True``, the participant's performance
        is evaluated at the end of the series of trials.

    check_performance_every_trial
        If ``True``, the participant's performance
        is evaluated after each trial.

    fail_trials_on_premature_exit
        If ``True``, a participant's trials are marked as failed
        if they leave the experiment prematurely.

    fail_trials_on_participant_performance_check
        If ``True``, a participant's trials are marked as failed
        if the participant fails a performance check.

    propagate_failure
        If ``True``, the failure of a trial is propagated to other
        parts of the experiment (the nature of this propagation is left up
        to the implementation).

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

    n_repeat_trials
        Number of repeat trials to present to the participant. These trials
        are typically used to estimate the reliability of the participant's
        responses.
        Defaults to ``0``.

    Attributes
    ----------

    check_timeout_interval_sec : float
        How often to check for timeouts, in seconds (default = 30).
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

    introduction
        An optional event or list of elts to execute prior to beginning the trial loop.

    give_end_feedback_passed : bool
        If ``True``, then participants who pass the final performance check
        are given feedback. This feedback can be customised by overriding
        :meth:`~psynet.trial.main.TrialMaker.get_end_feedback_passed_page`.

    performance_check_threshold : float
        Score threshold used by the default performance check method, defaults to 0.0.
        By default, corresponds to the minimum proportion of non-failed trials that
        the participant must achieve to pass the performance check.

    end_performance_check_waits : bool
        If ``True`` (default), then the final performance check waits until all trials no
        longer have any pending asynchronous processes.
    """

    state_class = TrialMakerState

    def __init__(
        self,
        id_: str,
        trial_class,
        expected_trials_per_participant: Union[int, float],
        check_performance_at_end: bool,
        check_performance_every_trial: bool,
        fail_trials_on_premature_exit: bool,
        fail_trials_on_participant_performance_check: bool,
        propagate_failure: bool,
        recruit_mode: str,
        target_n_participants: Optional[int],
        n_repeat_trials: int,
        assets: List,
    ):
        if recruit_mode == "n_participants" and target_n_participants is None:
            raise ValueError(
                "If <recruit_mode> == 'n_participants', then <target_n_participants> must be provided."
            )

        if recruit_mode == "n_trials" and target_n_participants is not None:
            raise ValueError(
                "If <recruit_mode> == 'n_trials', then <target_n_participants> must be None."
            )

        self.trial_class = trial_class
        self.id = id_
        self.expected_trials_per_participant = expected_trials_per_participant
        self.check_performance_at_end = check_performance_at_end
        self.check_performance_every_trial = check_performance_every_trial
        self.fail_trials_on_premature_exit = fail_trials_on_premature_exit
        self.fail_trials_on_participant_performance_check = (
            fail_trials_on_participant_performance_check
        )
        self.propagate_failure = propagate_failure
        self.recruit_mode = recruit_mode
        self.target_n_participants = target_n_participants
        self.n_repeat_trials = n_repeat_trials

        elts = self.compile_elts()

        self.check_time_estimates()

        super().__init__(id_, elts, assets=assets)

    participant_progress_threshold = 0.1

    performance_check_threshold = 0.0

    time_estimate_per_trial = None

    introduction = None

    def compile_elts(self):
        return join(
            RegisterTrialMaker(self),
            self._setup_core,
            self._setup_extra,
            self.introduction,
            self._trial_loop(),
            self._wrapup_core,
            self._check_performance_logic(type="end")
            if self.check_performance_at_end
            else None,
        )

    def custom(self, *args, assets=None, nodes=None):
        return Module(
            self.id,
            join(
                RegisterTrialMaker(self),
                CodeBlock(lambda participant: participant.select_module(self.id)),
                self._setup_core,
                *args,
                CodeBlock(lambda participant: participant.select_module(self.id)),
                self._wrapup_core,
            ),
            assets=assets,
            nodes=nodes,
            state_class=self.state_class,
        )

    @property
    def _setup_core(self):
        return join(
            PreDeployRoutine(self.with_namespace(), self.pre_deploy_routine),
            ParticipantFailRoutine(
                self.with_namespace(), self.participant_fail_routine
            ),
            self.check_timeout_task,
            CodeBlock(self.init_participant),
        )

    @property
    def _setup_extra(self):
        return join(
            RecruitmentCriterion(self.with_namespace(), self.selected_recruit_criterion)
        )

    @property
    def _wrapup_core(self):
        return join(
            CodeBlock(self.on_complete),
        )

    @property
    def n_complete_participants(self):
        return Participant.query.filter_by(complete=True).count()

    @property
    def n_working_participants(self):
        return Participant.query.filter_by(status="working", failed=False).count()

    @property
    def n_viable_participants(self):
        return

    def prepare_trial(self, experiment, participant):
        """
        Prepares and returns a trial to administer the participant.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.


        Returns
        _______

        A tuple of (:class:`~psynet.trial.main.Trial`, ``str``), where the first is a Trial object,
        and the second is a status string.
        """
        raise NotImplementedError

    def pre_deploy_routine(self, experiment):
        """
        Defines a routine for setting up the experiment prior to deployment.
        This is a good place to prepare networks etc.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        """
        pass

    check_timeout_interval_sec = 30
    response_timeout_sec = 60 * 5
    async_timeout_sec = 300
    end_performance_check_waits = True

    def participant_fail_routine(self, participant, experiment):
        if (
            self.fail_trials_on_participant_performance_check
            and "performance_check" in participant.failure_tags
        ) or (
            self.fail_trials_on_premature_exit
            and "premature_exit" in participant.failure_tags
        ):
            self.fail_participant_trials(
                participant, reason=", ".join(participant.failure_tags)
            )

    @property
    def check_timeout_task(self):
        return DatabaseCheck(self.with_namespace("check_timeout"), self.check_timeout)

    def check_timeout(self):
        # pylint: disable=no-member
        self.check_old_trials()
        WorkerAsyncProcess.check_timeouts()
        db.session.commit()

    def selected_recruit_criterion(self, experiment):
        if self.recruit_mode not in self.recruit_criteria:
            raise ValueError(
                f"Invalid recruitment mode: {self.recruit_mode}. Valid options: f{self.recruit_criteria}"
            )
        function = self.recruit_criteria[self.recruit_mode]
        return call_function(function, self=self, experiment=experiment)

    def null_criterion(self, experiment):
        logger.info("Recruitment is disabled for this module.")
        return False

    def n_participants_criterion(self, experiment):
        logger.info(
            "Target number of participants = %i, number of completed participants = %i, number of working participants = %i.",
            self.target_n_participants,
            self.n_complete_participants,
            self.n_working_participants,
        )
        return (
            self.n_complete_participants + self.n_working_participants
        ) < self.target_n_participants

    def n_trials_criterion(self, experiment):
        n_trials_still_required = self.n_trials_still_required
        n_trials_pending = self.n_trials_pending
        logger.info(
            "Number of trials still required = %i, number of pending trials = %i.",
            n_trials_still_required,
            n_trials_pending,
        )
        return n_trials_still_required > n_trials_pending

    recruit_criteria = {
        None: null_criterion,
        "n_participants": n_participants_criterion,
        "n_trials": n_trials_criterion,
    }

    give_end_feedback_passed = False

    def get_end_feedback_passed_page(self, score):
        """
        Defines the feedback given to participants who pass the final performance check.
        This feedback is only given if :attr:`~psynet.trial.main.TrialMaker.give_end_feedback_passed`
        is set to ``True``.

        Parameters
        ----------

        score :
            The participant's score on the performance check.

        Returns
        -------

        :class:`~psynet.timeline.Page` :
            A feedback page.
        """
        score_to_display = "NA" if score is None else f"{(100 * score):.0f}"

        return InfoPage(
            Markup(
                f"Your performance score was <strong>{score_to_display}&#37;</strong>."
            ),
            time_estimate=5,
        )

    def _get_end_feedback_passed_logic(self):
        if self.give_end_feedback_passed:

            def f(participant):
                score = participant.module_state.performance_check["score"]
                return self.get_end_feedback_passed_page(score)

            return PageMaker(f, time_estimate=5)
        else:
            return []

    def visualize(self):
        rendered_div = super().visualize()

        div = tags.div()
        with div:
            with tags.ul(cls="details"):
                if (
                    hasattr(self, "expected_trials_per_participant")
                    and self.expected_trials_per_participant is not None
                ):
                    tags.li(
                        f"Expected number of trials: {self.expected_trials_per_participant}"
                    )
                if (
                    hasattr(self, "target_n_participants")
                    and self.target_n_participants is not None
                ):
                    tags.li(
                        f"Target number of participants: {self.target_n_participants}"
                    )
                if hasattr(self, "recruit_mode") and self.recruit_mode is not None:
                    tags.li(f"Recruitment mode: {self.recruit_mode}")

        return rendered_div + div.render()

    def get_progress_info(self):
        return super().get_progress_info()

    def visualize_tooltip(self):
        return super().visualize_tooltip()

    @property
    def n_trials_pending(self):
        return sum(
            [
                self.estimate_n_pending_trials(p)
                for p in self._established_working_participants
            ]
        )

    @property
    def n_trials_still_required(self):
        raise NotImplementedError

    def estimate_n_pending_trials(self, participant: Participant):
        assert participant.status == "working"
        assert not participant.failed

        module_states = participant.module_states.get(self.id, [])
        n_completed_trials = sum(
            [module_state.n_completed_trials for module_state in module_states]
        )

        # This will be an underestimate in the unusual case of a trial maker inside a while loop.
        # Ideally we'd multiply it by the number of repetitions of the while loop but that's hard to get at from here.
        # It shouldn't really matter though because all that'll happen is we'll recruit a few too many participants.
        expected_total_n_trials = self.expected_trials_per_participant

        return expected_total_n_trials - n_completed_trials

    @property
    def _working_participants(self):
        # Looks across the whole experiment, not just that trial maker.
        # Should migrate this to the experiment class eventually.
        return Participant.query.filter_by(status="working", failed=False)

    @property
    def _established_working_participants(self):
        # Returns the number of established working participants across the whole
        # experiment (not just that trial maker!). Should migrate this to the
        # Experiment class eventually.
        return [
            p
            for p in self._working_participants
            if p.progress > self.participant_progress_threshold
        ]

    def check_old_trials(self):
        time_threshold = datetime.datetime.now() - datetime.timedelta(
            seconds=self.response_timeout_sec
        )
        trials_to_fail = (
            self.trial_class.query.filter_by(complete=False, failed=False)
            .filter(self.trial_class.creation_time < time_threshold)
            .all()
        )
        logger.info("Found %i old trial(s) to fail.", len(trials_to_fail))
        for trial in trials_to_fail:
            trial.fail(reason="response_timeout")
        db.session.commit()

    def init_participant(self, experiment, participant):
        # pylint: disable=unused-argument
        """
        Initializes the participant at the beginning of the sequence of trials.
        If you override this, make sure you call ``super().init_particiant(...)``
        somewhere in your new method.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """
        participant.select_module(self.id)
        participant.module_state.n_completed_trials = 0
        participant.module_state.in_repeat_phase = False
        self.init_participant_group(experiment, participant)

    def init_participant_group(self, experiment, participant):
        if not participant.module_state.participant_group:
            if self.choose_participant_group is None:
                group = "default"
            else:
                group = self.choose_participant_group(
                    participant=participant,
                )
            participant.module_state.participant_group = group

    def on_complete(self, experiment, participant):
        """
        An optional function run once the participant completes their
        sequence of trials.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """

    def finalize_trial(self, answer, trial, experiment, participant):
        # pylint: disable=unused-argument,no-self-use
        """
        This function is run after the participant completes the trial.
        It can be optionally customised, for example to add some more postprocessing.
        If you override this, make sure you call ``super().finalize_trial(...)``
        somewhere in your new method.


        Parameters
        ----------

        answer
            The ``answer`` object provided by the trial.

        trial
            The :class:`~psynet.trial.main.Trial` object representing the trial.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.
        """
        participant.module_state.n_completed_trials += 1

    def performance_check(self, experiment, participant, participant_trials):
        # pylint: disable=unused-argument
        """
        Defines an automated check for evaluating the participant's
        current performance. The default behaviour is to take the sum of
        the trial 'scores' (as computed by the Trial.score_answer),
        but this can be overridden if desired.

        Parameters
        ----------

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        participant_trials
            A list of all trials completed so far by the participant.


        Returns
        -------

        dict
            The dictionary should include the following values:

            - ``score``, expressed as a ``float`` or ``None``.
            - ``passed`` (Boolean), identifying whether the participant passed the check.

        """
        score = sum(
            [trial.score for trial in participant_trials if trial.score is not None]
        )
        passed = score > self.performance_threshold
        return {"score": score, "passed": passed}

    def with_namespace(self, x=None):
        return with_trial_maker_namespace(self.id, x=x)

    def fail_participant_trials(self, participant, reason=None):
        trials_to_fail = (
            db.session.query(Trial)
            .filter_by(participant_id=participant.id, failed=False)
            .join(TrialNetwork)
            .filter_by(trial_maker_id=self.id)
        )
        for trial in trials_to_fail:
            trial.fail(reason=reason)

    def check_fail_logic(self):
        """
        Determines the timeline logic for when a participant fails
        the performance check.
        By default, the participant is shown an :class:`~psynet.timeline.UnsuccessfulEndPage`.

        Returns
        -------

        An :class:`~psynet.timeline.Elt` or a list of :class:`~psynet.timeline.Elt` s.
        """
        return join(UnsuccessfulEndPage(failure_tags=["performance_check"]))

    def _check_performance_logic(self, type):
        assert type in ["trial", "end"]

        def eval_checks(experiment, participant):
            participant_trials = self.get_participant_trials(participant)
            results = self.performance_check(
                experiment=experiment,
                participant=participant,
                participant_trials=participant_trials,
            )

            assert isinstance(results["passed"], bool)
            participant.module_state.performance_check = results

            if type == "end":
                bonus = self.compute_bonus(**results)
                participant.module_state.performance_bonus = bonus
                participant.inc_performance_bonus(bonus)

            return results["passed"]

        logic = switch(
            "performance_check",
            function=eval_checks,
            branches={
                True: [] if type == "trial" else self._get_end_feedback_passed_logic(),
                False: self.check_fail_logic(),
            },
            fix_time_credit=False,
            log_chosen_branch=False,
        )

        if type == "end" and self.end_performance_check_waits:
            return join(
                wait_while(
                    self.any_pending_async_trials,
                    expected_wait=5,
                    log_message="Waiting for pending async trials.",
                ),
                logic,
            )
        else:
            return logic

    def get_all_participant_performance_check_results(self):
        records = (
            db.session.query(self.state_class.performance_check)
            .filter_by(module_id=self.id)
            .filter(self.state_class.performance_check.isnot(None))
            .all()
        )
        return [record[0] for record in records]

    def any_pending_async_trials(self, participant):
        trials = self.get_participant_trials(participant)
        return any([t.awaiting_async_process for t in trials])

    def get_participant_trials(self, participant):
        """
        Returns all trials (complete and incomplete) owned by the current participant,
        including repeat trials. Not intended for overriding.

        Parameters
        ----------

        participant:
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        """
        all_participant_trials = self.trial_class.query.filter_by(
            participant_id=participant.id
        ).all()
        return [t for t in all_participant_trials if t.trial_maker_id == self.id]

    # def _wait_for_prepared_trial(self, experiment, participant):
    #     while_loop(
    #         self.with_namespace("wait_for_prepared_trial"),
    #         lambda participant, experiment:
    #     )

    @log_time_taken
    def _prepare_trial(self, experiment, participant):
        if not participant.module_state.in_repeat_phase:
            trial, trial_status = self.prepare_trial(
                experiment=experiment, participant=participant
            )
            if trial_status == "exit" and self.n_repeat_trials > 0:
                participant.module_state.in_repeat_phase = True

        if participant.module_state.in_repeat_phase:
            trial, trial_status = self._prepare_repeat_trial(
                experiment=experiment, participant=participant
            )

        return trial, trial_status

    def _prepare_repeat_trial(self, experiment, participant):
        if not participant.module_state.trials_to_repeat:
            self._init_trials_to_repeat(participant)

        trials_to_repeat = participant.module_state.trials_to_repeat
        repeat_trial_index = participant.module_state.repeat_trial_index

        trial_status = "available"

        try:
            trial_to_repeat_id = trials_to_repeat[repeat_trial_index]
            trial_to_repeat = self.trial_class.query.filter_by(
                id=trial_to_repeat_id
            ).one()
            trial = trial_to_repeat.new_repeat_trial(
                experiment, repeat_trial_index, len(trials_to_repeat)
            )
            participant.module_state.repeat_trial_index += 1
            db.session.add(trial)
            # db.session.commit()
        except IndexError:
            trial = None
            trial_status = "exit"

        return trial, trial_status

    def _init_trials_to_repeat(self, participant):
        completed_trial_ids = [t.id for t in self.get_participant_trials(participant)]
        actual_n_repeat_trials = min(len(completed_trial_ids), self.n_repeat_trials)
        participant.module_state.trials_to_repeat = random.sample(
            completed_trial_ids, actual_n_repeat_trials
        )
        participant.module_state.repeat_trial_index = 0

    def cue_trial(self):
        """
        You can use this in combination with init_participant to administer trials
        outside of a trialmaker.
        """
        return join(
            CodeBlock(lambda participant: participant.select_module(self.id)),
            self._wait_for_trial(),
            conditional(
                "is_trial_available",
                condition=lambda participant: participant.trial_status != "exit",
                logic_if_true=self.trial_class.trial_logic(trial_maker=self),
                logic_if_false=CodeBlock(
                    lambda: logger.info("No trial found, skipping")
                ),
                fix_time_credit=False,
                log_chosen_branch=False,
            ),
        )

    def _trial_loop(self):
        return join(
            self._wait_for_trial(),
            while_loop(
                self.with_namespace("trial_loop"),
                condition=lambda participant: participant.trial_status != "exit",
                logic=join(
                    self.trial_class.trial_logic(trial_maker=self),
                    (
                        self._check_performance_logic(type="trial")
                        if self.check_performance_every_trial
                        else None
                    ),
                    self._wait_for_trial(),
                ),
                expected_repetitions=self.expected_trials_per_participant,
                fix_time_credit=False,
            ),
        )

    def _wait_for_trial(self):
        def _try_to_prepare_trial(experiment, participant):
            trial, trial_status = self._prepare_trial(experiment, participant)
            if trial is None:
                assert trial_status in ["wait", "exit"]
            else:
                assert isinstance(trial, Trial)
                assert trial_status == "available"
            participant.current_trial = trial
            participant.trial_status = trial_status

        def try_to_prepare_trial():
            return CodeBlock(_try_to_prepare_trial)

        return join(
            try_to_prepare_trial(),
            while_loop(
                "Waiting for trial",
                lambda participant: participant.trial_status == "wait",
                logic=join(
                    try_to_prepare_trial(),
                    WaitPage(wait_time=2.0),
                ),
                expected_repetitions=0,
            ),
        )

    def check_time_estimates(self):
        if (
            self.trial_class.time_estimate is None
            and self.time_estimate_per_trial is None
        ):
            raise AttributeError(
                f"You need to provide either time_estimate as a class attribute of {self.trial_class.__name__} "
                f"or time_estimate_per_trial as an instance or class attribute of trial maker {self.id}."
            )


class NetworkTrialMakerState(TrialMakerState):
    pass


class NetworkTrialMaker(TrialMaker):
    """
    Trial maker for network-based experiments.
    These experiments are organised around networks
    in an analogous way to the network-based experiments in Dallinger.
    A :class:`~dallinger.models.Network` comprises a collection of
    :class:`~dallinger.models.Node` objects organised in some kind of structure.
    Here the role of :class:`~dallinger.models.Node` objects
    is to generate :class:`~dallinger.models.Trial` objects.
    Typically the :class:`~dallinger.models.Node` object represents some
    kind of current experiment state, such as the last datum in a transmission chain.
    In some cases, a :class:`~dallinger.models.Network` or a :class:`~dallinger.models.Node`
    will be owned by a given participant; in other cases they will be shared
    between participants.

    An important feature of these networks is that their structure can change
    over time. This typically involves adding new nodes that somehow
    respond to the trials that have been submitted previously.

    The present class facilitates this behaviour by providing
    a built-in :meth:`~psynet.trial.main.TrialMaker.prepare_trial`
    implementation that comprises the following steps:

    1. Find the available networks from which to source the next trial,
       ordered by preference
       (:meth:`~psynet.trial.main.NetworkTrialMaker.find_networks`).
       These may be created on demand, or alternatively pre-created by
       :meth:`~psynet.trial.main.NetworkTrialMaker.pre_deploy_routine`.
    2. Give these networks an opportunity to grow (i.e. update their structure
       based on the trials that they've received so far)
       (:meth:`~psynet.trial.main.NetworkTrialMaker.grow_network`).
    3. Iterate through these networks, and find the first network that has a
       node available for the participant to attach to.
       (:meth:`~psynet.trial.main.NetworkTrialMaker.find_node`).
    4. Create a trial from this node
       (:meth:`psynet.trial.main.Trial.__init__`).

    The trial is then administered to the participant, and a response elicited.
    Once the trial is finished, the network is given another opportunity to grow.

    The implementation also provides support for asynchronous processing,
    for example to prepare the stimuli available at a given node,
    or to postprocess trials submitted to a given node.
    There is some sophisticated logic to make sure that a
    participant is not assigned to a :class:`~dallinger.models.Node` object
    if that object is still waiting for an asynchronous process,
    and likewise a trial won't contribute to a growing network if
    it is still pending the outcome of an asynchronous process.

    The user is expected to override the following abstract methods/attributes:

    * :meth:`~psynet.trial.main.NetworkTrialMaker.pre_deploy_routine`,
      (optional), which defines a routine that sets up the experiment
      (for example initialising and seeding networks).

    * :meth:`~psynet.trial.main.NetworkTrialMaker.find_networks`,
      which finds the available networks from which to source the next trial,
      ordered by preference.

    * :meth:`~psynet.trial.main.NetworkTrialMaker.grow_network`,
      which give these networks an opportunity to grow (i.e. update their structure
      based on the trials that they've received so far).

    * :meth:`~psynet.trial.main.NetworkTrialMaker.find_node`,
      which takes a given network and finds a node which the participant can
      be attached to, if one exists.

    Do not override prepare_trial.

    Parameters
    ----------

    trial_class
        The class object for trials administered by this maker.

    network_class
        The class object for the networks used by this maker.
        This should subclass :class`~psynet.trial.main.TrialNetwork`.

    expected_trials_per_participant
        Expected number of trials that the participant will take,
        including repeat trials
        (used for progress estimation).

    check_performance_at_end
        If ``True``, the participant's performance
        is evaluated at the end of the series of trials.

    check_performance_every_trial
        If ``True``, the participant's performance
        is evaluated after each trial.

    fail_trials_on_premature_exit
        If ``True``, a participant's trials are marked as failed
        if they leave the experiment prematurely.

    fail_trials_on_participant_performance_check
        If ``True``, a participant's trials are marked as failed
        if the participant fails a performance check.

    propagate_failure
        If ``True``, the failure of a trial is propagated to other
        parts of the experiment (the nature of this propagation is left up
        to the implementation).

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

    n_repeat_trials
        Number of repeat trials to present to the participant. These trials
        are typically used to estimate the reliability of the participant's
        responses.
        Defaults to ``0``.

    wait_for_networks
        If ``True``, then the participant will be made to wait if there are
        still more networks to participate in, but these networks are pending asynchronous processes.


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

    performance_threshold : float (default = -1.0)
        The performance threshold that is used in the
        :meth:`~psynet.trial.main.NetworkTrialMaker.performance_check` method.
    """

    state_class = NetworkTrialMakerState

    def __init__(
        self,
        id_,
        trial_class,
        network_class,
        expected_trials_per_participant,
        check_performance_at_end,
        check_performance_every_trial,
        fail_trials_on_premature_exit,
        fail_trials_on_participant_performance_check,
        # latest performance check is saved in as a participant variable (value, success)
        propagate_failure,
        recruit_mode,
        target_n_participants,
        n_repeat_trials: int,
        wait_for_networks: bool,
        assets=None,
    ):
        super().__init__(
            id_=id_,
            trial_class=trial_class,
            expected_trials_per_participant=expected_trials_per_participant,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            recruit_mode=recruit_mode,
            target_n_participants=target_n_participants,
            n_repeat_trials=n_repeat_trials,
            assets=assets,
        )
        self.network_class = network_class
        self.wait_for_networks = wait_for_networks

    @classmethod
    @log_time_taken
    def grow_all_networks(cls, experiment):
        # A bit of a hack that we only grow ChainNetworks here, we might need to extend this to
        # cover other types of networks in the future.
        from psynet.trial.chain import ChainNetwork

        db.session.commit()  # Introduced to try and avoid deadlocks we were seeing

        networks = ChainNetwork.query.filter_by(ready_to_spawn=True).all()
        if len(networks) > 0:
            logger.info("Growing %i networks...", len(networks))
            for n in networks:
                n.grow(experiment=experiment)
            db.session.commit()
        # networks = ChainTrialNetwork.query.filter_by(trial_maker_id=self.id)
        # for network in networks:
        #     self.grow_network(network, experiment)

    @log_time_taken
    def prepare_trial(self, experiment, participant):
        logger.info("Preparing trial for participant %i.", participant.id)
        self.grow_all_networks(experiment)
        networks = self.find_networks(participant=participant, experiment=experiment)

        if networks in ["wait", "exit"]:
            logger.info("Outcome of find_networks: %s", networks)
            trial = None
            trial_status = networks
            return trial, trial_status

        logger.info(
            "Outcome: found %i candidate network(s) for participant %i.",
            len(networks),
            participant.id,
        )

        assert len(networks) > 0

        for network in networks:
            node = self.find_node(
                network=network, participant=participant, experiment=experiment
            )
            if node is not None and node.ready_for_trials:
                logger.info(
                    "Selected node %i from network %i to give to participant %i.",
                    node.id,
                    node.network.id,
                    participant.id,
                )
                trial = self._create_trial(
                    node=node, participant=participant, experiment=experiment
                )
                trial_status = "available"
                return trial, trial_status
        logger.info(
            "Failed to create any nodes from these networks for participant %i, exiting.",
            participant.id,
        )
        trial = None
        trial_status = "exit"
        return trial, trial_status

    ####

    def find_networks(self, participant, experiment):
        """
        Returns a list of all available networks for the participant's next trial, ordered
        in preference (most preferred to least preferred).

        Parameters
        ----------

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.
        """
        raise NotImplementedError

    def grow_network(self, network, experiment):
        """
        Extends the network if necessary by adding one or more nodes.
        Returns ``True`` if any nodes were added.

        Parameters
        ----------

        network
            The network to be potentially extended.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.
        """
        raise NotImplementedError

    def find_node(self, network, participant, experiment):
        """
        Finds the node to which the participant should be attached for the next trial.

        Parameters
        ----------

        network
            The network to be potentially extended.

        participant
            An instantiation of :class:`psynet.participant.Participant`,
            corresponding to the current participant.

        experiment
            An instantiation of :class:`psynet.experiment.Experiment`,
            corresponding to the current experiment.
        """
        raise NotImplementedError

    @log_time_taken
    def _create_trial(self, node, participant, experiment):
        trial = self.trial_class(
            experiment=experiment,
            node=node,
            participant=participant,
            propagate_failure=self.propagate_failure,
            is_repeat_trial=False,
        )
        trial._initial_assets = dict(trial.assets)
        db.session.add(trial)
        db.session.commit()
        return trial

    def _grow_network(self, network, experiment):
        # pylint: disable=no-member
        grown = self.grow_network(network, experiment)
        assert isinstance(grown, bool)
        if grown:
            self._check_run_async_post_grow_network(network)
            db.session.commit()

    def _check_run_async_post_grow_network(self, network):
        if (
            network.run_async_post_grow_network is not None
            and not network.run_async_post_grow_network
        ):
            return
        elif not is_method_overridden(network, TrialNetwork, "async_post_grow_network"):
            return
        else:
            WorkerAsyncProcess(
                network.async_post_grow_network,
                label="post_grow_network",
                timeout=self.async_timeout_sec,
                network=network,
            )

    @property
    def network_query(self):
        return self.network_class.query.filter_by(trial_maker_id=self.id)

    @property
    def n_networks(self):
        return self.network_query.count()

    @property
    def networks(self):
        return self.network_query.all()

    performance_threshold = -1.0
    min_nodes_for_performance_check = 2
    performance_check_type = "consistency"
    consistency_check_type = "spearman_correlation"

    def compute_bonus(self, score, passed):
        """
        Computes the bonus to allocate to the participant at the end of a trial maker
        on the basis of the results of the final performance check.
        Note: if `check_performance_at_end = False`, then this function will not be run
        and the bonus will not be assigned.
        """
        return 0.0

    def performance_check(self, experiment, participant, participant_trials):
        if self.performance_check_type == "consistency":
            return self.performance_check_consistency(
                experiment, participant, participant_trials
            )
        elif self.performance_check_type == "performance":
            return self.performance_check_accuracy(
                experiment, participant, participant_trials
            )
        elif self.performance_check_type == "score":
            return self.performance_check_score(
                experiment, participant, participant_trials
            )
        else:
            raise NotImplementedError

    def performance_check_accuracy(self, experiment, participant, participant_trials):
        n_trials = len(participant_trials)
        if n_trials == 0:
            p = None
            passed = True
        else:
            n_failed_trials = len([t for t in participant_trials if t.failed])
            p = 1 - n_failed_trials / n_trials
            passed = p >= self.performance_check_threshold
        return {"score": p, "passed": passed}

    def performance_check_score(self, experiment, participant, participant_trials):
        score = sum(t.score for t in participant_trials)
        passed = score >= self.performance_check_threshold
        return {"score": score, "passed": passed}

    def get_answer_for_consistency_check(self, trial):
        # Must return a number
        return float(trial.answer)

    def performance_check_consistency(
        self, experiment, participant, participant_trials
    ):
        trials_by_id = {trial.id: trial for trial in participant_trials}

        repeat_trials = [t for t in participant_trials if t.is_repeat_trial]
        parent_trials = [trials_by_id[t.parent_trial_id] for t in repeat_trials]

        repeat_trial_answers = [
            self.get_answer_for_consistency_check(t) for t in repeat_trials
        ]
        parent_trial_answers = [
            self.get_answer_for_consistency_check(t) for t in parent_trials
        ]

        assert self.min_nodes_for_performance_check >= 2

        if len(repeat_trials) < self.min_nodes_for_performance_check:
            logger.info(
                "min_nodes_for_performance_check was not reached, so consistency score cannot be calculated."
            )
            score = None
            passed = True
        else:
            consistency = self.get_consistency(
                repeat_trial_answers, parent_trial_answers
            )
            if isnan(consistency):
                logger.info(
                    """
                    get_consistency returned 'nan' in the performance check.
                    This commonly indicates that the participant gave the same response
                    to all repeat trials. The participant will be failed.
                    """
                )
                score = None
                passed = False
            else:
                score = float(consistency)
                passed = bool(score >= self.performance_threshold)
        logger.info(
            "Performance check for participant %i: consistency = %s, passed = %s",
            participant.id,
            "NA" if score is None else f"{score:.3f}",
            passed,
        )
        return {"score": score, "passed": passed}

    def get_consistency(self, x, y):
        if self.consistency_check_type == "pearson_correlation":
            return corr(x, y)
        elif self.consistency_check_type == "spearman_correlation":
            return corr(x, y, method="spearman")
        elif self.consistency_check_type == "percent_agreement":
            n_cases = len(x)
            n_agreements = sum([a == b for a, b in zip(x, y)])
            return n_agreements / n_cases
        else:
            raise NotImplementedError

    @staticmethod
    def group_trials_by_parent(trials):
        res = {}
        for trial in trials:
            parent_id = trial.parent_trial_id
            if parent_id not in res:
                res[parent_id] = []
            res[parent_id].append(trial)
        return res


class TrialNetwork(SQLMixinDallinger, Network):
    """
    A network class to be used by :class:`~psynet.trial.main.NetworkTrialMaker`.
    The user must override the abstract method :meth:`~psynet.trial.main.TrialNetwork.add_node`.
    The user may also wish to override the
    :meth:`~psynet.trial.main.TrialNetwork.async_post_grow_network` method
    if they wish to implement asynchronous network processing.

    Parameters
    ----------

    experiment
        An instantiation of :class:`psynet.experiment.Experiment`,
        corresponding to the current experiment.

    Attributes
    ----------

    target_n_trials : int or None
        Indicates the target number of trials for that network.
        Left empty by default, but can be set by custom ``__init__`` functions.
        Stored as the field ``property2`` in the database.

    awaiting_async_process : bool
        Whether the network is currently closed and waiting for an asynchronous process to complete.

    participant : Optional[Participant]
        Returns the network's :class:`~psynet.participant.Participant`,
        or ``None`` if none can be found.

    n_alive_nodes : int
        Returns the number of non-failed nodes in the network.

    n_completed_trials : int
        Returns the number of completed and non-failed trials in the network
        (irrespective of asynchronous processes, but excluding repeat trials).

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.

    run_async_post_grow_network : bool
        Set this to ``True`` if you want the :meth:`~psynet.trial.main.TrialNetwork.async_post_grow_network`
        method to run after the network is grown.
    """

    __extra_vars__ = {
        **SQLMixinDallinger.__extra_vars__.copy(),
    }

    def __repr__(self):
        return ("<Network-{}-{} with {} nodes>").format(
            self.id, self.type, len(self.alive_nodes)
        )

    trial_maker_id = Column(String)
    module_id = Column(String)
    target_n_trials = Column(Integer)
    participant_group = Column(String)

    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    participant = relationship(Participant, foreign_keys=[participant_id])

    id_within_participant = Column(Integer)

    all_trials = relationship("psynet.trial.main.Trial")
    # all_nodes = relationship("psynet.trial.main.TrialNode")

    @property
    @extra_var(__extra_vars__)
    def n_all_nodes(self):
        return len(self.all_nodes)

    @property
    @extra_var(__extra_vars__)
    def n_alive_nodes(self):
        return len(self.alive_nodes)

    @property
    @extra_var(__extra_vars__)
    def n_failed_nodes(self):
        return len(self.failed_nodes)

    @property
    def alive_nodes(self):
        return [node for node in self.all_nodes if not self.failed]

    @property
    def failed_nodes(self):
        return [node for node in self.all_nodes if self.failed]

    @property
    @extra_var(__extra_vars__)
    def n_all_trials(self):
        return len(self.all_trials)

    @property
    @extra_var(__extra_vars__)
    def n_alive_trials(self):
        return len(self.alive_trials)

    @property
    @extra_var(__extra_vars__)
    def n_failed_trials(self):
        return len(self.failed_trials)

    @property
    def alive_trials(self):
        return [t for t in self.all_trials if not t.failed]

    @property
    def failed_trials(self):
        return [t for t in self.all_trials if t.failed]

    async_processes = relationship("AsyncProcess")

    asset_links = relationship(
        "AssetNetwork",
        collection_class=attribute_mapped_collection("label"),
        cascade="all, delete-orphan",
    )

    assets = association_proxy(
        "asset_links", "asset", creator=lambda k, v: AssetNetwork(label=k, asset=v)
    )

    errors = relationship("ErrorRecord")

    def grow(self, experiment):
        if self.trial_maker:
            self.trial_maker._grow_network(self, experiment=experiment)

    @property
    def trial_maker(self):
        from ..experiment import get_trial_maker

        if self.trial_maker_id:
            return get_trial_maker(self.trial_maker_id)

    def calculate_full(self):
        db.session.commit()
        self.full = len(self.alive_nodes) > (self.max_size or 0)

    def add_node(self, node):
        """
        Adds a node to the network. This method is responsible for setting
        ``self.full = True`` if the network is full as a result.
        """
        raise NotImplementedError

    def fail(self, reason=None):
        if not self.failed:
            super().fail(reason=reason)

    # vars = Column(PythonObject)

    @property
    def var(self):
        return VarStore(self)

    awaiting_async_process = column_property(
        select(AsyncProcess.network_id, AsyncProcess.pending)
        .where(
            AsyncProcess.network_id == dallinger.models.Network.id, AsyncProcess.pending
        )
        .exists()
    )
    register_extra_var(__extra_vars__, "awaiting_async_process")

    ####

    def __init__(
        self,
        trial_maker_id: str,
        experiment,  # noqa
        module_id: Optional[str] = None,
    ):
        # pylint: disable=unused-argument
        self.trial_maker_id = trial_maker_id
        self.assets = {}

        if not module_id:
            module_id = trial_maker_id

        self.module_id = module_id

    run_async_post_grow_network = None

    def async_post_grow_network(self):
        """
        Optional function to be run after the network is grown.
        Will only run if :attr:`~psynet.trial.main.TrialNetwork.run_async_post_grow_network`
        is set to ``True``.
        """

    def call_async_post_grow_network(self):
        # Currently this function is redundant, but it's there in case we want to
        # add wrapping logic one day.
        self.async_post_grow_network()


TrialNetwork.n_completed_trials = column_property(
    select(func.count(Trial.id))
    .where(
        Trial.network_id == TrialNetwork.id,
        ~Trial.failed,
        Trial.complete,
        ~Trial.is_repeat_trial,
    )
    .scalar_subquery()
)


# This column_property has to be defined outside the class main definition because of a quirk with
# SQLAlchemy. From the documentation:
#
# > If import issues prevent the column_property() from being defined inline with the class, it can be assigned to the
# > class after both are configured. When using mappings that make use of a declarative_base() base class,
# > this attribute assignment has the effect of calling Mapper.add_property() to add an additional property after the
# > fact.
TrialMakerState.n_completed_trials = column_property(
    select(func.count(Trial.id))
    .where(
        Trial.module_state_id == TrialMakerState.id,
        Trial.complete,
        ~Trial.is_repeat_trial,
        ~Trial.failed,
    )
    .scalar_subquery()
)


class TrialNode(SQLMixinDallinger, dallinger.models.Node):
    __extra_vars__ = {
        **SQLMixinDallinger.__extra_vars__.copy(),
    }

    trial_maker_id = Column(String)
    module_id = Column(String)
    _on_create_called = Column(Boolean, default=False)
    _on_deploy_called = Column(Boolean, default=False)
    ready_for_trials = Column(Boolean, default=False)

    # network = relationship(
    #     "psynet.trial.main.TrialNetwork",
    #     foreign_keys=[dallinger.models.Node.network_id],
    #     back_populates="all_nodes",
    # )

    async_processes = relationship("AsyncProcess")

    awaiting_async_process = column_property(
        select(AsyncProcess.node_id, AsyncProcess.pending)
        .where(AsyncProcess.node_id == dallinger.models.Node.id, AsyncProcess.pending)
        .exists()
    )
    register_extra_var(__extra_vars__, "awaiting_async_process")

    asset_links = relationship(
        "AssetNode",
        collection_class=attribute_mapped_collection("label"),
        cascade="all, delete-orphan",
    )

    assets = association_proxy(
        "asset_links", "asset", creator=lambda k, v: AssetNode(label=k, asset=v)
    )

    errors = relationship("ErrorRecord")

    all_trials = relationship("psynet.trial.main.Trial", foreign_keys=[Trial.node_id])

    @property
    def alive_trials(self):
        return [t for t in self.all_trials if not t.failed]

    @property
    def failed_trials(self):
        return [t for t in self.all_trials if t.failed]

    # assets = Column(PythonDict)

    # @property
    # def assets(self):
    #     assets_from_trials = Asset.query.filter(Asset.node_id == self.id, Asset.trial_id != None).all()
    #     assets_not_from_trials = Asset.query.filter(Asset.node_id == self.id, Asset.trial_id == None).all()
    #
    #     assets = {}
    #     for asset in assets_not_from_trials:
    #         assets[asset.label_or_key] = asset
    #
    #     return {
    #         organize_by_key(assets_from_trials, lambda asset: asset.label_or_key)
    #         **assets,
    #     }

    def __init__(self, network=None, participant=None, module_id=None):
        # Note: We purposefully do not call super().__init__(), because this parent constructor
        # requires the prior existence of the node's parent network, which is impractical for us.
        self.module_id = module_id

        if network is not None:
            self.set_network(network)

        if participant is not None:
            self.participant = participant
            self.participant_id = participant.id

    def check_on_create(self):
        if not self._on_create_called:
            self.on_create()
            self._on_create_called = True

    def check_on_deploy(self):
        from psynet.experiment import in_deployment_package

        if in_deployment_package() and not self._on_deploy_called:
            self.on_deploy()
            self._on_deploy_called = True

    def on_create(self):
        """
        To be called when the instance is added to the database. Can be overridden with custom logic.
        Note: this function is called both on nodes that are created on the remote server
        and on nodes that are initialized on the local machine when preparing for deployment
        (e.g. the nodes in a static experiment). Synthesizing stimuli in dynamic experiments
        (e.g. iterated reproduction) is best done by overriding the async_on_deploy function instead,
        which only runs on the remote server.
        """
        pass

    def on_deploy(self):
        if is_method_overridden(self, TrialNode, "async_on_deploy"):
            WorkerAsyncProcess(
                function=self._async_on_deploy,
                node=self,
                timeout=self.trial_maker.async_timeout_sec,
                unique=True,
            )
        else:
            self.ready_for_trials = True

    def _async_on_deploy(self):
        self.async_on_deploy()
        self.ready_for_trials = True

    def async_on_deploy(self):
        """
        Called when the node is deployed to the remote server. This includes both
        deploying nodes from the local machine to the remote machine
        (e.g. when we have static stimuli that are preregistered in the database)
        and creating new nodes on the remote machine (e.g. when we have a chain experiment).
        """
        pass

    def set_network(self, network):
        self.network = network
        self.trial_maker_id = network.trial_maker_id

        if not self.module_id:
            self.module_id = network.module_id

        if not self.participant:
            self.participant = network.participant

    @property
    def trial_maker(self):
        from ..experiment import get_trial_maker

        if self.trial_maker_id:
            return get_trial_maker(self.trial_maker_id)

    def fail(self, reason=None):
        if not self.failed:
            super().fail(reason=reason)

    def add_default_network(self):
        from psynet.experiment import get_experiment

        network = GenericTrialNetwork(
            experiment=get_experiment(), module_id=self.module_id
        )
        db.session.add(network)
        self.set_network(network)
        db.session.commit()


class GenericTrialNetwork(TrialNetwork):
    def __init__(self, module_id, experiment):
        super().__init__(
            trial_maker_id=None,
            module_id=module_id,
            experiment=experiment,
        )

    def grow(self, experiment):
        pass


class GenericTrialNode(TrialNode):
    def __init__(self, module_id, experiment):
        super().__init__(
            network=self.get_default_network(module_id, experiment),
            participant=None,
        )

    def get_default_network(self, module_id, experiment):
        network = GenericTrialNetwork(module_id, experiment)
        db.session.add(network)
        return network
