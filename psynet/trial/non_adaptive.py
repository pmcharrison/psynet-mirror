import random
import operator

import os
import shutil

from statistics import mean
from typing import Optional
from collections import Counter
from functools import reduce
from progress.bar import Bar


from sqlalchemy.sql.expression import not_

import dallinger.models
import dallinger.nodes

from ..media import (
    bucket_exists,
    create_bucket,
    make_bucket_public,
    read_string_from_s3,
    write_string_to_s3,
    delete_bucket_dir,
    upload_to_s3
)

from ..field import claim_field
from ..utils import DisableLogger, hash_object
from .main import Trial, TrialNetwork, NetworkTrialMaker

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

# pylint: disable=unused-import
import rpdb

class Stimulus(dallinger.models.Node):
    """
    A stimulus class for non-adaptive experiments.
    Subclasses the Dallinger :class:`dallinger.models.Node` class.
    Should not be directly instantiated by the user,
    but instead specified indirectly through an instance
    of :class:`~psynet.trial.non_adaptive.StimulusSpec`.

    Attributes
    ----------

    definition : dict
        A dictionary containing the parameter values for the stimulus.
        This excludes any parameters defined by the
        :class:`~psynet.trial.non_adaptive.StimulusVersion` class.

    phase : str
        The phase of the experiment, e.g ``"practice"``, ``"main"``.

    participant_group : str
        The associated participant group.

    block : str
        The associated block.

    num_completed_trials : int
        The number of completed trials that this stimulus has received,
        exluding failed trials.

    num_trials_still_required : int
        The number of trials still required for this stimulus before the experiment
        can complete, if such a quota exists.
    """

    __mapper_args__ = {"polymorphic_identity": "stimulus"}

    target_num_trials = claim_field(1, int)

    @property
    def definition(self):
        return self.details.copy()

    @definition.setter
    def definition(self, definition):
        self.details = definition

    @property
    def phase(self):
        return self.network.phase

    @property
    def participant_group(self):
        return self.network.participant_group

    @property
    def block(self):
        return self.network.block

    @property
    def _query_completed_trials(self):
        return (
            NonAdaptiveTrial
                .query
                .filter_by(stimulus_id=self.id, failed=False, complete=True)
        )

    @property
    def num_completed_trials(self):
        return self._query_completed_trials.count()

    @property
    def num_trials_still_required(self):
        if self.target_num_trials is None:
            raise RuntimeError("<num_trials_still_required> is not defined when <target_num_trials> is None.")
        return self.target_num_trials - self.num_completed_trials

    def __init__(self, stimulus_spec, network, source, target_num_trials, stimulus_set):
        assert network.phase == stimulus_spec.phase
        assert network.participant_group == stimulus_spec.participant_group
        assert network.block == stimulus_spec.block

        super().__init__(network=network)
        self.definition = stimulus_spec.definition
        source.connect(whom=self)
        self.target_num_trials = target_num_trials

class StimulusSpec():
    """
    Defines a stimulus for a non-adaptive experiment.
    Will be translated to a database-backed
    :class:`~psynet.trial.non_adaptive.Stimulus` instance.

    Parameters
    ----------

    definition
        A dictionary of parameters defining the stimulus.

    phase
        The associated phase of the experiment,
        e.g. ``"practice"`` or ``"main"``.

    version_specs
        A list of
        :class:`~psynet.trial.non_adaptive.StimulusVersionSpec`
        objects, defining different forms that the stimulus can take.

    participant_group
        The associated participant group.
        Defaults to a common participant group for all participants.

    block
        The associated block.
        Defaults to a single block for all trials.
    """
    def __init__(
        self,
        definition: dict,
        phase: str,
        version_specs: list,
        participant_group="default",
        block="default"
    ):
        assert isinstance(definition, dict)
        assert isinstance(version_specs, list)
        assert len(version_specs) > 0
        for version_spec in version_specs:
            assert isinstance(version_spec, StimulusVersionSpec)

        self.definition = definition
        self.version_specs = version_specs
        self.phase = phase
        self.participant_group = participant_group
        self.block = block

    def add_stimulus_to_network(self, network, source, experiment, target_num_trials, stimulus_set):
        stimulus = Stimulus(self, network=network, source=source, target_num_trials=target_num_trials, stimulus_set=stimulus_set)
        experiment.session.add(stimulus)

        for version_spec in self.version_specs:
            version = StimulusVersion(version_spec, stimulus, network, stimulus_set)
            experiment.session.add(version)

    @property
    def has_media(self):
        return any([s.has_media for s in self.version_specs])

    @property
    def hash(self):
        return hash_object({
            "definition": self.definition,
            "versions": [x.hash for x in self.version_specs]
        })

    def cache_media(self, local_media_cache_dir):
        for s in self.version_specs:
            s.cache_media(local_media_cache_dir)

    def upload_media(self, s3_bucket, local_media_cache_dir, remote_media_dir):
        for s in self.version_specs:
            s.upload_media(s3_bucket, local_media_cache_dir, remote_media_dir)

class StimulusVersion(dallinger.models.Node):
    """
    A stimulus version class for non-adaptive experiments.
    Subclasses the Dallinger :class:`dallinger.models.Node` class;
    intended to be nested within the
    :class:`~psynet.trial.non_adaptive.Stimulus` class.
    Should not be directly instantiated by the user,
    but instead specified indirectly through an instance
    of :class:`~psynet.trial.non_adaptive.StimulusVersionSpec`.

    Attributes
    ----------

    definition : dict
        A dictionary containing the parameter values for the stimulus version.
        This excludes any parameters defined by the parent
        :class:`~psynet.trial.non_adaptive.Stimulus` class.

    stimulus : Stimulus
        The parent :class:`~psynet.trial.non_adaptive.Stimulus` object.

    stimulus_id : int
        The ID of the parent stimulus object. Stored as ``property1`` in the database.

    phase : str
        The phase of the experiment, e.g ``"practice"``, ``"main"``.

    participant_group : str
        The associated participant group.

    block : str
        The associated block.
    """

    __mapper_args__ = {"polymorphic_identity": "stimulus_version"}

    stimulus_id = claim_field(1, int)
    has_media = claim_field(2, bool)
    s3_bucket = claim_field(3, str)
    remote_media_dir = claim_field(4, str)
    media_file_name = claim_field(5, str)

    @property
    def definition(self):
        return self.details.copy()

    @definition.setter
    def definition(self, definition):
        self.details = definition


    @property
    def media_url(self):
        if not self.has_media:
            return None
        return os.path.join(
            "https://s3.amazonaws.com",
            self.s3_bucket,
            self.remote_media_dir,
            self.media_file_name
        )


    @property
    def stimulus(self):
        return Stimulus.query.filter_by(id=self.stimulus_id).one()

    @property
    def phase(self):
        return self.stimulus.phase

    @property
    def participant_group(self):
        return self.stimulus.participant_group

    @property
    def block(self):
        return self.stimulus.block

    def __init__(self, stimulus_version_spec, stimulus, network, stimulus_set):
        super().__init__(network=network)
        self.stimulus_id = stimulus.id
        self.has_media = stimulus_version_spec.has_media
        self.s3_bucket = stimulus_set.s3_bucket
        self.remote_media_dir = stimulus_set.remote_media_dir
        self.media_file_name = stimulus_version_spec.media_file_name
        self.definition = stimulus_version_spec.definition
        self.connect_to_parent(stimulus)

    def connect_to_parent(self, parent):
        self.connect(parent, direction="from")

class StimulusVersionSpec():
    """
    Defines a stimulus version for a non-adaptive experiment.
    Will be translated to a database-backed
    :class:`~psynet.trial.non_adaptive.StimulusVersion` instance,
    which will be nested within a
    :class:`~psynet.trial.non_adaptive.Stimulus` instance.

    Parameters
    ----------

    definition
        A dictionary of parameters defining the stimulus version.
        Should not include any parameters already defined in
        the parent :class:`~psynet.trial.non_adaptive.StimulusSpec` instance.
    """
    def __init__(self, definition):
        assert isinstance(definition, dict)
        self.definition = definition

    has_media = False
    media_ext = ""

    @classmethod
    def generate_media(cls, definition, output_path):
        pass

    @property
    def hash(self):
        return hash_object(self.definition)

    @property
    def media_file_name(self):
        if not self.has_media:
            return None
        return self.hash + self.media_ext

    def cache_media(self, local_media_cache_dir):
        if self.has_media:
            path = os.path.join(local_media_cache_dir, self.media_file_name)
            self.generate_media(self.definition, path)

    def upload_media(self, s3_bucket, local_media_cache_dir, remote_media_dir):
        if self.has_media:
            local_path = os.path.join(local_media_cache_dir, self.media_file_name)
            remote_key = os.path.join(remote_media_dir, self.media_file_name)
            if not os.path.isfile(local_path):
                raise IOError(
                    f"Couldn't find local media cache file '{local_path}'. "
                    "Try deleting your cache and starting again?"
                )
            with DisableLogger():
                upload_to_s3(local_path, s3_bucket, remote_key, public_read=True)


class StimulusSet():
    """
    Defines a stimulus set for a non-adaptive experiment.
    This stimulus set is defined as a collection of
    :class:`~psynet.trial.non_adaptive.StimulusSpec`
    and :class:`~psynet.trial.non_adaptive.StimulusVersionSpec`
    objects, which are translated to database-backed
    :class:`~psynet.trial.non_adaptive.Stimulus`
    and :class:`~psynet.trial.non_adaptive.StimulusVersion`
    objects respectively.

    Parameters
    ----------

    stimulus_specs: list
        A list of :class:`~psynet.trial.non_adaptive.StimulusSpec` objects,
        with these objects potentially containing
        :class:`~psynet.trial.non_adaptive.StimulusVersionSpec` objects.
        This list may contain stimuli for several experiment phases,
        as long as these phases are specified in the ``phase`` parameters
        for the :class:`~psynet.trial.non_adaptive.StimulusSpec` objects.
    """
    def __init__(self, stimulus_specs, version: str = "default", s3_bucket: Optional[str] = None):
        assert isinstance(stimulus_specs, list)
        assert isinstance(version, str)

        self.stimulus_specs = stimulus_specs
        self.version = version
        self.s3_bucket = s3_bucket

        network_specs = set()
        blocks = set()
        participant_groups = set()
        self.num_stimuli = dict()

        for s in stimulus_specs:
            assert isinstance(s, StimulusSpec)
            network_specs.add((
                s.phase,
                s.participant_group,
                s.block
            ))

            blocks.add(s.block)
            participant_groups.add(s.participant_group)

            # This logic could be refactored by defining a special dictionary class
            if s.participant_group not in self.num_stimuli:
                self.num_stimuli[s.participant_group] = dict()
            if s.block not in self.num_stimuli[s.participant_group]:
                self.num_stimuli[s.participant_group][s.block] = 0

            self.num_stimuli[s.participant_group][s.block] += 1

        self.network_specs = [
            NetworkSpec(
                phase=x[0],
                participant_group=x[1],
                block=x[2],
                stimulus_set=self
            )
            for x in network_specs
        ]

        self.blocks = sorted(list(blocks))
        self.participant_groups = sorted(list(participant_groups))

    @property
    def hash(self):
        return hash_object({
            "version": self.version,
            "stimulus_specs": [x.hash for x in self.stimulus_specs]
        })

    local_media_cache_parent_dir = "cache"

    @property
    def local_media_cache_dir(self):
        return os.path.join(self.local_media_cache_parent_dir, self.version)

    @property
    def remote_media_dir(self):
        if self.s3_bucket is None:
            return None
        return self.version

    @property
    def has_media(self):
        return any([s.has_media for s in self.stimulus_specs])

    def prepare_media(self):
        if self.has_media:
            if self.remote_media_is_up_to_date:
                logger.info("Remote media seems to be up-to-date, no media preparation necessary.")
            else:
                self.cache_media()
                self.upload_media()
        else:
            logger.info("No media found to prepare.")

    def cache_media(self):
        if os.path.exists(self.local_media_cache_dir):
            if self.get_local_media_cache_hash() == self.hash:
                logger.info("Local media cache appears to be up-to-date.")
                return None
            else:
                logger.info("Local media cache appears to be out-of-date, removing.")
                shutil.rmtree(self.local_media_cache_dir)

        os.makedirs(self.local_media_cache_dir)

        with Bar("Caching media", max=len(self.stimulus_specs)) as bar:
            for s in self.stimulus_specs:
                s.cache_media(self.local_media_cache_dir)
                bar.next()

        self.write_local_media_cache_hash()
        logger.info("Finished caching local media.")

    def upload_media(self):
        self.prepare_s3_bucket()

        with Bar("Uploading media", max=len(self.stimulus_specs)) as bar:
            for s in self.stimulus_specs:
                s.upload_media(self.s3_bucket, self.local_media_cache_dir, self.remote_media_dir)
                bar.next()

        self.write_remote_media_hash()
        logger.info("Finished uploading media.")

    def prepare_s3_bucket(self):
        if not bucket_exists(self.s3_bucket):
            create_bucket(self.s3_bucket)

        make_bucket_public(self.s3_bucket)

        delete_bucket_dir(self.s3_bucket, self.remote_media_dir)

    @property
    def path_to_local_cache_hash(self):
        return os.path.join(self.local_media_cache_dir, "hash")

    def get_local_media_cache_hash(self):
        if os.path.isfile(self.path_to_local_cache_hash):
            with open(self.path_to_local_cache_hash, "r") as file:
                return file.read()
        else:
            return None

    def write_local_media_cache_hash(self):
        os.makedirs(self.local_media_cache_dir, exist_ok=True)
        with open(self.path_to_local_cache_hash, "w") as file:
            file.write(self.hash)

    @property
    def remote_media_is_up_to_date(self):
        return self.get_remote_media_hash() == self.hash

    @property
    def path_to_remote_cache_hash(self):
        return os.path.join(self.remote_media_dir, "hash")

    def get_remote_media_hash(self):
        # Returns None if the cache doesn't exist
        if not bucket_exists(self.s3_bucket):
            return None
        return read_string_from_s3(self.s3_bucket, self.path_to_remote_cache_hash)

    def write_remote_media_hash(self):
        write_string_to_s3(self.hash, bucket_name=self.s3_bucket, key=self.path_to_remote_cache_hash)


class NetworkSpec():
    def __init__(self, phase, participant_group, block, stimulus_set):
        self.phase = phase
        self.participant_group = participant_group
        self.block = block
        self.stimulus_set = stimulus_set # note: this includes stimuli outside this network too!

    def create_network(self, trial_type, experiment, target_num_trials_per_stimulus):
        network = NonAdaptiveNetwork(
            trial_type=trial_type,
            phase=self.phase,
            participant_group=self.participant_group,
            block=self.block,
            stimulus_set=self.stimulus_set,
            experiment=experiment,
            target_num_trials_per_stimulus=target_num_trials_per_stimulus
        )
        experiment.session.add(network)

class NonAdaptiveTrial(Trial):
    """
    A Trial class for non-adaptive experiments.

    Attributes
    ----------

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
        Stored in ``property3`` in the database.

    awaiting_process : bool
        Whether the trial is waiting for some asynchronous process
        to complete (e.g. to synthesise audiovisual material).
        The user should not typically change this directly.
        Stored in ``property4`` in the database.

    definition
        A dictionary of parameters defining the trial.
        This dictionary combines the dictionaries of the
        respective
        :class:`~psynet.trial.non_adaptive.StimulusSpec`
        and
        :class:`~psynet.trial.non_adaptive.StimulusVersionSpec`
        objects.

    stimulus_version
        The corresponding :class:`~psynet.trial.non_adaptive.StimulusVersion`
        object.

    stimulus
        The corresponding :class:`~psynet.trial.non_adaptive.Stimulus`
        object.

    phase
        The phase of the experiment, e.g. ``"training"`` or ``"main"``.

    participant_group
        The associated participant group.

    block
        The block in which the trial is situated.
    """
    __mapper_args__ = {"polymorphic_identity": "non_adaptive_trial"}

    stimulus_id = claim_field(5, int)

    def __init__(self, experiment, node, participant, propagate_failure):
        super().__init__(experiment, node, participant, propagate_failure)
        self.stimulus_id = self.stimulus_version.stimulus_id

    def show_trial(self, experiment, participant):
        raise NotImplementedError

    @property
    def media_url(self):
        return self.stimulus_version.media_url

    @property
    def stimulus_version(self):
        return self.origin

    @property
    def stimulus(self):
        return self.origin.stimulus

    @property
    def phase(self):
        return self.stimulus.phase

    @property
    def participant_group(self):
        return self.stimulus.participant_group

    @property
    def block(self):
        return self.stimulus.block

    def make_definition(self, experiment, participant):
        """
        Combines the definitions of the associated
        :class:`~psynet.trial.non_adaptive.Stimulus`
        and :class:`~psynet.trial.non_adaptive.StimulusVersion`
        objects.
        """
        return {
            **self.stimulus.definition,
            **self.stimulus_version.definition
        }

    def summarise(self):
        return {
            "participant_group": self.participant_group,
            "phase": self.phase,
            "block": self.block,
            "definition": self.definition,
            "media_url": self.media_url,
            "trial_id": self.id,
            "stimulus_id": self.stimulus.id,
            "stimulus_version_id": self.stimulus_version.id
        }

class NonAdaptiveTrialMaker(NetworkTrialMaker):
    """
    Administers a sequence of trials in a non-adaptive experiment.
    The class is intended for use with the
    :class:`~psynet.trial.non_adaptive.NonAdaptiveTrial` helper class.
    which should be customised to show the relevant stimulus
    for the experimental paradigm.
    The user must also define their stimulus set
    using the following built-in classes:

    * :class:`~psynet.trial.non_adaptive.StimulusSet`;

    * :class:`~psynet.trial.non_adaptive.StimulusSpec`;

    * :class:`~psynet.trial.non_adaptive.StimulusVersionSpec`;

    In particular, a :class:`~psynet.trial.non_adaptive.StimulusSet`
    contains a list of :class:`~psynet.trial.non_adaptive.StimulusSpec` objects,
    which in turn contains a list of
    :class:`~psynet.trial.non_adaptive.StimulusVersionSpec` objects.

    The user may also override the following methods, if desired:

    * :meth:`~psynet.trial.non_adaptive.NonAdaptiveTrialMaker.choose_block_order`;
      chooses the order of blocks in the experiment. By default the blocks
      are ordered randomly.

    * :meth:`~psynet.trial.non_adaptive.NonAdaptiveTrialMaker.choose_participant_group`;
      assigns the participant to a group. By default the participant is assigned
      to a random group.

    * :meth:`~psynet.trial.main.TrialMaker.on_complete`,
      run once the the sequence of trials is complete.

    * :meth:`~psynet.trial.main.TrialMaker.performance_check`,
      which checks the performance of the participant
      with a view to rejecting poor-performing participants.

    Further customisable options are available in the constructor's parameter list,
    documented below.

    Parameters
    ----------

    trial_class
        The class object for trials administered by this maker
        (should subclass :class:`~psynet.trial.non_adaptive.NonAdaptiveTrial`).

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".

    stimulus_set
        The stimulus set to be administered.

    time_estimate_per_trial
        Time estimated for each trial (seconds).

    recruit_mode
        Selects a recruitment criterion for determining whether to recruit
        another participant. The built-in criteria are ``"num_participants"``
        and ``"num_trials"``.

    target_num_participants
        Target number of participants to recruit for the experiment. All
        participants must successfully finish the experiment to count
        towards this quota. This target is only relevant if
        ``recruit_mode="num_participants"``.

    target_num_trials_per_stimulus
        Target number of trials to recruit for each stimulus in the experiment
        (as opposed to for each stimulus version). This target is only relevant if
        ``recruit_mode="num_trials"``.

    new_participant_group
        If ``True``, :meth:`~psynet.non_adaptive.NonAdaptiveTrialMaker.choose_participant_group`
        is run to assign the participant to a new participant group.
        Unless overridden, a given participant's participant group will persist
        for all phases of the experiment,
        except if switching to a :class:`~psynet.non_adaptive.NonAdaptiveTrialMaker`
        where the trial class (:class:`~psynet.non_adaptive.NonAdaptiveTrial`)
        has a different name.
        Only set this to ``False`` if the participant is taking a subsequent phase
        of a non-adaptive experiment.

    max_trials_per_block
        Determines the maximum number of trials that a participant will be allowed to experience in each block.

    allow_repeated_stimuli
        Determines whether the participant can be administered the same stimulus more than once.

    max_unique_stimuli_per_block
        Determines the maximum number of unique stimuli that a participant will be allowed to experience
        in each block. Once this quota is reached, the participant will be forced to repeat
        previously experienced stimuli.

    active_balancing_within_participants
        If ``True`` (default), active balancing within participants is enabled, meaning that
        stimulus selection always favours the stimuli that have been presented fewest times
        to that participant so far.

    active_balancing_across_participants
        If ``True`` (default), active balancfing across participants is enabled, meaning that
        stimulus selection favours stimuli that have been presented fewest times to any participant
        in the experiment, excluding failed trials.
        This criterion defers to ``active_balancing_within_participants``;
        if both ``active_balancing_within_participants=True``
        and ``active_balancing_across_participants=True``,
        then the latter criterion is only used for tie breaking.

    check_performance_at_end
        If ``True``, the participant's performance is
        is evaluated at the end of the series of trials.
        Defaults to ``False``.
        See :meth:`~psynet.trial.main.TrialMaker.performance_check`
        for implementing performance checks.

    check_performance_every_trial
        If ``True``, the participant's performance is
        is evaluated after each trial.
        Defaults to ``False``.
        See :meth:`~psynet.trial.main.TrialMaker.performance_check`
        for implementing performance checks.

    fail_trials_on_premature_exit
        If ``True``, a participant's trials are marked as failed
        if they leave the experiment prematurely.
        Defaults to ``True``.

    fail_trials_on_participant_performance_check
        If ``True``, a participant's trials are marked as failed
        if the participant fails a performance check.
        Defaults to ``True``.

    async_post_trial
        Optional function to be run after a trial is completed by the participant.
        This should be specified as a fully qualified string, for example
        ``"psynet.trial.async_example.async_update_trial"``.
        This function should take one argument, ``trial_id``, corresponding to the
        ID of the relevant trial to process.
        ``trial.awaiting_process`` is set to ``True`` when the asynchronous process is
        initiated; the present method is responsible for setting ``trial.awaiting_process = False``
        once it is finished. It is also responsible for committing to the database
        using ``db.session.commit()`` once processing is complete
        (``db`` can be imported using ``from dallinger import db``).
        See the source code for ``~psynet.trial.async_example.async_update_trial``
        for an example.

    Returns
    -------

    list
        A sequence of events suitable for inclusion in a
        :class:`~psynet.timeline.Timeline`
    """
    def __init__(
        self,
        *,
        trial_class,
        phase: str,
        stimulus_set: StimulusSet,
        time_estimate_per_trial: int,
        new_participant_group: bool,
        recruit_mode: Optional[str] = None,
        target_num_participants: Optional[int] = None,
        target_num_trials_per_stimulus: Optional[int] = None,
        max_trials_per_block: Optional[int] = None,
        allow_repeated_stimuli: bool = False,
        max_unique_stimuli_per_block: Optional[int]=None,
        active_balancing_within_participants: bool = True,
        active_balancing_across_participants: bool = True,
        check_performance_at_end: bool = False,
        check_performance_every_trial: bool = False,
        fail_trials_on_premature_exit: bool = True,
        fail_trials_on_participant_performance_check: bool = True,
        async_post_trial: Optional[str] = None
    ):
        if (recruit_mode == "num_participants" and target_num_participants is None):
            raise ValueError("<target_num_participants> cannot be None if recruit_mode == 'num_participants'.")
        if (recruit_mode == "num_trials" and target_num_trials_per_stimulus is None):
            raise ValueError("<target_num_trials_per_stimulus> cannot be None if recruit_mode == 'num_trials'.")
        if (target_num_participants is not None) and (target_num_trials_per_stimulus is not None):
            raise ValueError("<target_num_participants> and <target_num_trials_per_stimulus> cannot both be provided.")

        self.stimulus_set = stimulus_set
        self.target_num_participants = target_num_participants
        self.target_num_trials_per_stimulus = target_num_trials_per_stimulus
        self.new_participant_group = new_participant_group
        self.max_trials_per_block = max_trials_per_block
        self.allow_repeated_stimuli = allow_repeated_stimuli
        self.max_unique_stimuli_per_block = max_unique_stimuli_per_block
        self.active_balancing_within_participants = active_balancing_within_participants
        self.active_balancing_across_participants = active_balancing_across_participants

        expected_num_trials = self.estimate_num_trials()
        super().__init__(
            trial_class,
            network_class=NonAdaptiveNetwork,
            phase=phase,
            time_estimate_per_trial=time_estimate_per_trial,
            expected_num_trials=expected_num_trials,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=False,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants,
            async_post_trial=async_post_trial
        )

    @property
    def num_trials_still_required(self):
        return sum([stimulus.num_trials_still_required for stimulus in self.stimuli])

    @property
    def stimuli(self):
        return reduce(
            operator.add,
            [n.stimuli for n in self.networks]
        )

    def init_participant(self, experiment, participant):
        """
        Initialises the participant at the beginning of the sequence of trials.
        This includes choosing the block order, choosing the participant group
        (if relevant), and initialising a record of the participant's completed
        stimuli.
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
        super().init_participant(experiment, participant)
        self.init_block_order(experiment, participant)
        self.init_participant_group(experiment, participant)
        self.init_completed_stimuli_in_phase(participant)

    def estimate_num_trials_in_block(self, num_stimuli_in_block):
        if self.allow_repeated_stimuli:
            return self.max_trials_per_block
        else:
            if self.max_trials_per_block is None:
                return num_stimuli_in_block
            else:
                return min(num_stimuli_in_block, self.max_trials_per_block)

    def estimate_num_trials(self):
        return mean([
            sum([
                self.estimate_num_trials_in_block(num_stimuli_in_block)
                for num_stimuli_in_block in num_stimuli_by_block.values()
            ])
            for participant_group, num_stimuli_by_block
            in self.stimulus_set.num_stimuli.items()
        ])

    def finalise_trial(self, answer, trial, experiment, participant):
        """
        This calls the base class's ``finalise_trial`` method,
        then increments the number of completed stimuli in the phase and the block.
        """
        super().finalise_trial(answer, trial, experiment, participant)
        self.increment_completed_stimuli_in_phase_and_block(participant, trial.block, trial.stimulus_id)
        # trial.stimulus.num_completed_trials += 1

    def init_block_order(self, experiment, participant):
        self.set_block_order(
            participant,
            self.choose_block_order(experiment=experiment, participant=participant)
        )

    def init_participant_group(self, experiment, participant):
        if self.new_participant_group:
            self.set_participant_group(
                participant,
                self.choose_participant_group(experiment=experiment, participant=participant)
            )
        elif not self.has_participant_group(participant):
            raise ValueError("<new_participant_group> was False but the participant hasn't yet been assigned to a group.")

    @property
    def block_order_var_id(self):
        return self.with_namespace("block_order")

    def set_block_order(self, participant, block_order):
        participant.var.new(self.block_order_var_id, block_order)

    def get_block_order(self, participant):
        return participant.var.get(self.with_namespace("block_order"))


    @property
    def participant_group_var_id(self):
        return self.with_namespace("participant_group", shared_between_phases=True)

    def set_participant_group(self, participant, participant_group):
        participant.var.new(self.participant_group_var_id, participant_group)

    def get_participant_group(self, participant):
        return participant.var.get(self.participant_group_var_id)

    def has_participant_group(self, participant):
        return participant.var.has(self.participant_group_var_id)


    def init_completed_stimuli_in_phase(self, participant):
        participant.var.set(
            self.with_namespace("completed_stimuli_in_phase"),
            {
                block: Counter()
                for block in self.stimulus_set.blocks
            }
        )

    def get_completed_stimuli_in_phase(self, participant):
        all_counters = participant.var.get(self.with_namespace("completed_stimuli_in_phase"))
        return {
            block: Counter(counter)
            for block, counter in all_counters.items()
        }

    def get_completed_stimuli_in_phase_and_block(self, participant, block):
        all_counters = self.get_completed_stimuli_in_phase(participant)
        return all_counters[block]

    def increment_completed_stimuli_in_phase_and_block(self, participant, block, stimulus_id):
        all_counters = self.get_completed_stimuli_in_phase(participant)
        all_counters[block][stimulus_id] += 1
        participant.var.set(self.with_namespace("completed_stimuli_in_phase"), all_counters)

    # def append_completed_stimuli_in_phase(self, participant, block, stimulus_id):
    #     assert isinstance(value, int)
    #     counter = self.get_completed_stimuli_in_phase(participant, block)
    #     counter[value] += 1
    #     self.set_completed_stimuli_in_phase(participant, block, counter)

    def on_complete(self, experiment, participant):
        pass

    def experiment_setup_routine(self, experiment):
        """
        All networks for the non-adaptive experiment are set up at the beginning of
        data collection.
        """
        if self.num_networks == 0:
            self.create_networks(experiment)

    def choose_block_order(self, experiment, participant):
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
        blocks = self.stimulus_set.blocks
        random.shuffle(blocks)
        return blocks

    def choose_participant_group(self, experiment, participant):
        # pylint: disable=unused-argument
        """
        Determines the participant group assigned to the current participant.
        By default this function randomly chooses from the available participant groups.
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

        A string label identifying the selected participant group.
        """
        participant_groups = self.stimulus_set.participant_groups
        return random.choice(participant_groups)

    def create_networks(self, experiment):
        for network_spec in self.stimulus_set.network_specs:
            network_spec.create_network(
                trial_type=self.trial_type,
                experiment=experiment,
                target_num_trials_per_stimulus=self.target_num_trials_per_stimulus
            )
        experiment.save()

    def find_networks(self, participant, experiment):
        # pylint: disable=protected-access
        block_order = participant.var.get(self.with_namespace("block_order"))
        networks = (
            NonAdaptiveNetwork.query
                              .filter_by(
                                  trial_type=self.trial_type,
                                  participant_group=self.get_participant_group(participant),
                                  phase=self.phase,
                                  awaiting_process=False
                              )
                              .filter(NonAdaptiveNetwork.block.in_(block_order))
                              .all()
        )
        networks.sort(key=lambda network: block_order.index(network.block))
        return networks

    def grow_network(self, network, participant, experiment):
        """
        Does nothing, because networks never get expanded in a non-adaptive experiment.
        """
        return False

    def find_node(self, network, participant, experiment):
        stimulus = self.find_stimulus(network, participant, experiment)
        if stimulus is None:
            return None
        return self.find_stimulus_version(stimulus, participant, experiment)

    def count_completed_trials_in_network(self, network, participant):
        return (
            self.trial_class
                .query
                .filter_by(
                    network_id=network.id,
                    participant_id=participant.id,
                    failed=False,
                    complete=True
                )
                .count()
        )

    def find_stimulus(self, network, participant, experiment):
        # pylint: disable=unused-argument,protected-access
        if (
            self.max_trials_per_block is not None and
            self.count_completed_trials_in_network(network, participant) >= self.max_trials_per_block
        ):
            return None
        completed_stimuli = self.get_completed_stimuli_in_phase_and_block(participant, block=network.block)
        allow_new_stimulus = self.check_allow_new_stimulus(completed_stimuli)
        candidates = Stimulus.query.filter_by(network_id=network.id) # networks are guaranteed to be from the correct phase
        if not self.allow_repeated_stimuli:
            candidates = self.filter_out_repeated_stimuli(candidates, completed_stimuli)
        if not allow_new_stimulus:
            candidates = self.filter_out_new_stimuli(candidates, completed_stimuli)
        candidates = candidates.all()
        if self.active_balancing_within_participants:
            candidates = self.balance_within_participants(candidates, completed_stimuli)
        if self.active_balancing_across_participants:
            candidates = self.balance_across_participants(candidates)
        if len(candidates) == 0:
            return None
        return random.choice(candidates)

    def check_allow_new_stimulus(self, completed_stimuli):
        if self.max_unique_stimuli_per_block is None:
            return True
        num_unique_completed_stimuli = len(completed_stimuli)
        return num_unique_completed_stimuli < self.max_unique_stimuli_per_block

    @staticmethod
    def filter_out_repeated_stimuli(candidates, completed_stimuli):
        return candidates.filter(not_(Stimulus.id.in_(list(completed_stimuli.keys()))))

    @staticmethod
    def filter_out_new_stimuli(candidates, completed_stimuli):
        return candidates.filter(Stimulus.id.in_(list(completed_stimuli.keys())))

    @staticmethod
    def balance_within_participants(candidates, completed_stimuli):
        candidate_counts_within = [completed_stimuli[candidate.id] for candidate in candidates]
        min_count_within = 0 if len(candidate_counts_within) == 0 else min(candidate_counts_within)
        return [
            candidate for candidate, candidate_count_within in zip(candidates, candidate_counts_within)
            if candidate_count_within == min_count_within
        ]

    @staticmethod
    def balance_across_participants(candidates):
        candidate_counts_across = [candidate.num_completed_trials for candidate in candidates]
        min_count_across = 0 if len(candidate_counts_across) == 0 else min(candidate_counts_across)
        return [
            candidate for candidate, candidate_count_across in zip(candidates, candidate_counts_across)
            if candidate_count_across == min_count_across
        ]

    @staticmethod
    def find_stimulus_version(stimulus, participant, experiment):
        # pylint: disable=unused-argument
        candidates = (
            StimulusVersion.query
                           .filter_by(stimulus_id=stimulus.id)
                           .all()
        )
        assert len(candidates) > 0
        return random.choice(candidates)

class NonAdaptiveNetwork(TrialNetwork):
    """
    A :class:`~psynet.trial.main.TrialNetwork` class for non-adaptive experiments.
    The user should not have to engage with this class directly,
    except through the network visualisation tool and through
    analysing the resulting data.
    The networks are organised as follows:

    1. At the top level of the hierarchy, different networks correspond to different
       combinations of participant group and block.
       If the same experiment contains many
       :class:`~psynet.trial.non_adaptive.NonAdaptiveTrialMaker` objects
       with different associated :class:`~psynet.trial.non_adaptive.NonAdaptiveTrial`
       classes,
       then networks will also be differentiated by the names of these
       :class:`~psynet.trial.non_adaptive.NonAdaptiveTrial` classes.

    2. Within a given network, the first level of the hierarchy is the
       :class:`~psynet.trial.non_adaptive.Stimulus` class.
       These objects subclass the Dallinger :class:`~dallinger.models.Node` class,
       and are generated directly from :class:`~psynet.trial.non_adaptive.StimulusSpec` instances.

    3. Nested within :class:`~psynet.trial.non_adaptive.Stimulus` objects
       are :class:`~psynet.trial.non_adaptive.StimulusVersion` objects.
       These also subclass the Dallinger :class:`~dallinger.models.Node` class,
       and are generated directly from :class:`~psynet.trial.non_adaptive.StimulusVersionSpec` instances.

    4. Nested within :class:`~psynet.trial.non_adaptive.StimulusVersion` objects
       are :class:`~psynet.trial.non_adaptive.NonAdaptiveTrial` objects.
       These objects subclass the Dallinger :class:`~dallinger.models.Info` class.

    Attributes
    ----------

    trial_type : str
        A string uniquely identifying the type of trial to be administered,
        typically just the name of the relevant class,
        e.g. ``"MelodyTrial"``.
        The same experiment should not contain multiple TrialMaker objects
        with the same ``trial_type``, unless they correspond to different
        phases of the experiment and are marked as such with the
        ``phase`` parameter.
        Stored as the field ``property1`` in the database.

    target_num_trials : int or None
        Indicates the target number of trials for that network.
        Stored as the field ``property2`` in the database.

    awaiting_process : bool
        Whether the network is currently closed and waiting for an asynchronous process to complete.
        This should always be ``False`` for non-adaptive experiments.
        Stored as the field ``property3`` in the database.

    participant_group : bool
        The network's associated participant group.
        Stored as the field ``property4`` in the database.

    block : str
        The network's associated block.
        Stored as the field ``property5`` in the database.

    phase : str
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".
        Set by default in the ``__init__`` function.
        Stored as the field ``role`` in the database.

    num_nodes : int
        Returns the number of non-failed nodes in the network.

    num_completed_trials : int
        Returns the number of completed and non-failed trials in the network
        (irrespective of asynchronous processes).

    stimuli : list
        Returns the stimuli associated with the network.

    num_stimuli : int
        Returns the number of stimuli associated with the network.

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.
    """
    #pylint: disable=abstract-method

    __mapper_args__ = {"polymorphic_identity": "non_adaptive_network"}

    participant_group = claim_field(4, str)
    block = claim_field(5, str)

    def __init__(self, trial_type, phase, participant_group, block, stimulus_set, experiment, target_num_trials_per_stimulus):
        self.participant_group = participant_group
        self.block = block
        super().__init__(trial_type, phase, experiment)
        if self.num_nodes == 0:
            self.populate(stimulus_set, experiment, target_num_trials_per_stimulus)

    def populate(self, stimulus_set, experiment, target_num_trials_per_stimulus):
        source = dallinger.nodes.Source(network=self)
        experiment.session.add(source)
        stimulus_specs = [
            x for x in stimulus_set.stimulus_specs
            if x.phase == self.phase
            and x.participant_group == self.participant_group
            and x.block == self.block
        ]
        for stimulus_spec in stimulus_specs:
            stimulus_spec.add_stimulus_to_network(
                network=self,
                source=source,
                experiment=experiment,
                target_num_trials=target_num_trials_per_stimulus,
                stimulus_set=stimulus_set
            )
        experiment.save()

    @property
    def stimulus_query(self):
        return Stimulus.query.filter_by(network_id=self.id)

    @property
    def stimuli(self):
        return self.stimulus_query.all()

    @property
    def num_stimuli(self):
        return self.stimulus_query.count()

