import operator
import os
import pickle
import random
import shutil
from collections import Counter
from functools import reduce
from pathlib import Path
from statistics import mean
from typing import Optional

from dallinger import db
from progress.bar import Bar
from sqlalchemy import func

from .. import command_line
from ..field import claim_field, claim_var, extra_var
from ..media import (
    bucket_exists,
    create_bucket,
    delete_bucket_dir,
    get_s3_url,
    make_bucket_public,
    read_string_from_s3,
    upload_to_s3,
    write_string_to_s3,
)
from ..utils import DisableLogger, get_logger, hash_object
from .main import (
    HasDefinition,
    NetworkTrialMaker,
    Trial,
    TrialNetwork,
    TrialNode,
    TrialSource,
)

logger = get_logger()

STIMULUS_SETS = set()  # TODO - remove once storage branch is merged


def filter_for_completed_trials(x):
    return x.filter_by(failed=False, complete=True, is_repeat_trial=False)


def query_all_completed_trials():
    return filter_for_completed_trials(StaticTrial.query)


class Stimulus(TrialNode, HasDefinition):
    """
    A stimulus class for static experiments.
    Subclasses the Dallinger :class:`dallinger.models.Node` class.
    Should not be directly instantiated by the user,
    but instead specified indirectly through an instance
    of :class:`~psynet.trial.static.StimulusSpec`.

    Attributes
    ----------

    definition : dict
        A dictionary containing the parameter values for the stimulus.
        This excludes any parameters defined by the
        :class:`~psynet.trial.static.StimulusVersion` class.

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

    __extra_vars__ = {
        **TrialNode.__extra_vars__.copy(),
        **HasDefinition.__extra_vars__.copy(),
    }

    target_num_trials = claim_field("target_num_trials", __extra_vars__, int)

    @property
    def phase(self):
        return self.network.phase

    @property
    @extra_var(__extra_vars__)
    def participant_group(self):
        return self.network.participant_group

    @property
    @extra_var(__extra_vars__)
    def block(self):
        return self.network.block

    @property
    def _query_completed_trials(self):
        return query_all_completed_trials().filter_by(stimulus_id=self.id)

    @property
    def num_completed_trials(self):
        return self._query_completed_trials.count()

    @property
    def num_trials_still_required(self):
        if self.target_num_trials is None:
            raise RuntimeError(
                "<num_trials_still_required> is not defined when <target_num_trials> is None."
            )
        return self.target_num_trials - self.num_completed_trials

    def __init__(self, stimulus_spec, network, source, target_num_trials, stimulus_set):
        assert network.phase == stimulus_spec.phase
        assert network.participant_group == stimulus_spec.participant_group
        assert network.block == stimulus_spec.block

        super().__init__(network=network)
        self.definition = stimulus_spec.definition
        source.connect(whom=self)
        self.target_num_trials = target_num_trials


class StimulusSpec:
    """
    Defines a stimulus for a static experiment.
    Will be translated to a database-backed
    :class:`~psynet.trial.static.Stimulus` instance.

    Parameters
    ----------

    definition
        A dictionary of parameters defining the stimulus.

    phase
        The associated phase of the experiment,
        e.g. ``"practice"`` or ``"main"``.

    version_specs
        A list of
        :class:`~psynet.trial.static.StimulusVersionSpec`
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
        version_specs=None,
        participant_group="default",
        block="default",
    ):
        assert isinstance(definition, dict)

        if version_specs is None:
            version_specs = [StimulusVersionSpec(definition={})]

        assert isinstance(version_specs, list)
        assert len(version_specs) > 0
        for version_spec in version_specs:
            assert isinstance(version_spec, StimulusVersionSpec)

        self.definition = definition
        self.version_specs = version_specs
        self.phase = phase
        self.participant_group = participant_group
        self.block = block

    def add_stimulus_to_network(self, network, source, target_num_trials, stimulus_set):
        stimulus = Stimulus(
            self,
            network=network,
            source=source,
            target_num_trials=target_num_trials,
            stimulus_set=stimulus_set,
        )
        db.session.add(stimulus)

        for version_spec in self.version_specs:
            version = StimulusVersion(version_spec, stimulus, network, stimulus_set)
            db.session.add(version)

    @property
    def has_media(self):
        return any([s.has_media for s in self.version_specs])

    @property
    def hash(self):
        return hash_object(
            {
                "definition": self.definition,
                "versions": [x.hash for x in self.version_specs],
            }
        )

    def cache_media(self, local_media_cache_dir):
        for s in self.version_specs:
            s.cache_media(self.definition, local_media_cache_dir)

    def upload_media(self, s3_bucket, local_media_cache_dir, remote_media_dir):
        for s in self.version_specs:
            s.upload_media(s3_bucket, local_media_cache_dir, remote_media_dir)


class StimulusVersion(TrialNode, HasDefinition):
    """
    A stimulus version class for static experiments.
    Subclasses the Dallinger :class:`dallinger.models.Node` class;
    intended to be nested within the
    :class:`~psynet.trial.static.Stimulus` class.
    Should not be directly instantiated by the user,
    but instead specified indirectly through an instance
    of :class:`~psynet.trial.static.StimulusVersionSpec`.

    Attributes
    ----------

    definition : dict
        A dictionary containing the parameter values for the stimulus version.
        This excludes any parameters defined by the parent
        :class:`~psynet.trial.static.Stimulus` class.

    stimulus : Stimulus
        The parent :class:`~psynet.trial.static.Stimulus` object.

    stimulus_id : int
        The ID of the parent stimulus object. Stored as ``property1`` in the database.

    phase : str
        The phase of the experiment, e.g ``"practice"``, ``"main"``.

    participant_group : str
        The associated participant group.

    block : str
        The associated block.
    """

    __extra_vars__ = {**TrialNode.__extra_vars__, **HasDefinition.__extra_vars__}

    stimulus_id = claim_field("stimulus_id", __extra_vars__, int)
    phase = claim_field("phase", __extra_vars__, str)
    participant_group = claim_field("participant_group", __extra_vars__, str)
    block = claim_field("block", __extra_vars__, str)
    has_media = claim_field("has_media", __extra_vars__, bool)
    s3_bucket = claim_field("s3_bucket", __extra_vars__, str)
    remote_media_dir = claim_field("remote_media_dir", __extra_vars__, str)
    media_id = claim_field("media_id", __extra_vars__, str)

    @property
    @extra_var(__extra_vars__)
    def media_url(self):
        if not self.has_media:
            return None
        return get_s3_url(
            self.s3_bucket, os.path.join(self.remote_media_dir, self.media_id)
        )

    @property
    def stimulus(self):
        return Stimulus.query.filter_by(id=self.stimulus_id).one()

    def __init__(self, stimulus_version_spec, stimulus, network, stimulus_set):
        super().__init__(network=network)
        self.stimulus_id = stimulus.id
        self.phase = stimulus.phase
        self.participant_group = stimulus.participant_group
        self.block = stimulus.block
        self.has_media = stimulus_version_spec.has_media
        self.s3_bucket = stimulus_set.s3_bucket
        self.remote_media_dir = stimulus_set.remote_media_dir
        self.media_id = stimulus_version_spec.media_id
        self.definition = stimulus_version_spec.definition
        self.connect_to_parent(stimulus)

    def connect_to_parent(self, parent):
        self.connect(parent, direction="from")


class StimulusVersionSpec:
    """
    Defines a stimulus version for a static experiment.
    Will be translated to a database-backed
    :class:`~psynet.trial.static.StimulusVersion` instance,
    which will be nested within a
    :class:`~psynet.trial.static.Stimulus` instance.

    Parameters
    ----------

    definition
        A dictionary of parameters defining the stimulus version.
        Should not include any parameters already defined in
        the parent :class:`~psynet.trial.static.StimulusSpec` instance.
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
    def media_id(self):
        if not self.has_media:
            return None
        return self.hash + self.media_ext

    def cache_media(self, parent_definition, local_media_cache_dir):
        if self.has_media:
            path = os.path.join(local_media_cache_dir, self.media_id)
            definition = {**parent_definition, **self.definition}
            self.generate_media(definition, path)

    def upload_media(self, s3_bucket, local_media_cache_dir, remote_media_dir):
        if self.has_media:
            local_path = os.path.join(local_media_cache_dir, self.media_id)
            remote_key = os.path.join(remote_media_dir, self.media_id)
            if not os.path.exists(local_path):
                raise IOError(
                    f"Couldn't find local media cache at '{local_path}'. "
                    "Try deleting your cache and starting again?"
                )
            with DisableLogger():
                upload_to_s3(local_path, s3_bucket, remote_key, public_read=True)


class StimulusSet:
    """
    Defines a stimulus set for a static experiment.
    This stimulus set is defined as a collection of
    :class:`~psynet.trial.static.StimulusSpec`
    and :class:`~psynet.trial.static.StimulusVersionSpec`
    objects, which are translated to database-backed
    :class:`~psynet.trial.static.Stimulus`
    and :class:`~psynet.trial.static.StimulusVersion`
    objects respectively.

    Parameters
    ----------

    stimulus_specs: list
        A list of :class:`~psynet.trial.static.StimulusSpec` objects,
        with these objects potentially containing
        :class:`~psynet.trial.static.StimulusVersionSpec` objects.
        These objects must all correspond to the same experiment phase
        (se the ``phase`` attribute of the
        :class:`~psynet.trial.static.StimulusSpec` objects).
    """

    def __init__(
        self,
        id_: str,
        stimulus_specs,
        version: str = "default",
        s3_bucket: Optional[str] = None,
    ):
        assert isinstance(stimulus_specs, list)
        assert isinstance(version, str)

        self.stimulus_specs = stimulus_specs
        self.id = id_
        self.version = version
        self.s3_bucket = s3_bucket
        self.phase = None

        network_specs = set()
        blocks = set()
        participant_groups = set()
        self.num_stimuli = dict()

        for s in stimulus_specs:
            assert isinstance(s, StimulusSpec)

            if self.phase is None:
                self.phase = s.phase
            elif self.phase != s.phase:
                raise ValueError(
                    "All stimuli in StimulusSpec must have the same phase "
                    f"(found both '{self.phase}' and '{s.phase}')."
                )

            network_specs.add((s.phase, s.participant_group, s.block))

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
                phase=x[0], participant_group=x[1], block=x[2], stimulus_set=self
            )
            for x in network_specs
        ]

        self.blocks = sorted(list(blocks))
        self.participant_groups = sorted(list(participant_groups))

        STIMULUS_SETS.add(self)

    @property
    def hash(self):
        return hash_object(
            {
                "version": self.version,
                "stimulus_specs": [x.hash for x in self.stimulus_specs],
            }
        )

    local_media_cache_parent_dir = "cache"

    @property
    def local_media_cache_dir(self):
        return os.path.join(self.local_media_cache_parent_dir, self.id, self.version)

    @property
    def remote_media_dir(self):
        if self.s3_bucket is None:
            return None
        return os.path.join(self.id, self.version)

    @property
    def has_media(self):
        return any([s.has_media for s in self.stimulus_specs])

    def load(self):
        return self

    def prepare_media(self, force):
        if self.has_media:
            if not force and self.remote_media_is_up_to_date:
                logger.info(
                    "(%s) Remote media seems to be up-to-date, no media preparation necessary.",
                    self.id,
                )
            else:
                self.cache_media(force=force)
                self.upload_media()
        else:
            logger.info("(%s) No media found to prepare.", self.id)

    def cache_media(self, force):
        if os.path.exists(self.local_media_cache_dir):
            if not force and self.get_local_media_cache_hash() == self.hash:
                logger.info("(%s) Local media cache appears to be up-to-date.", self.id)
                return None
            else:
                if force:
                    logger.info("(%s) Forcing removal of local media cache.", self.id)
                else:
                    logger.info(
                        "(%s) Local media cache appears to be out-of-date, removing.",
                        self.id,
                    )
                shutil.rmtree(self.local_media_cache_dir)

        os.makedirs(self.local_media_cache_dir)

        with Bar("Caching media", max=len(self.stimulus_specs)) as bar:
            for s in self.stimulus_specs:
                s.cache_media(self.local_media_cache_dir)
                bar.next()

        self.write_local_media_cache_hash()
        logger.info("(%s) Finished caching local media.", self.id)

    def upload_media(self):
        self.prepare_s3_bucket()

        with Bar("Uploading media", max=len(self.stimulus_specs)) as bar:
            for s in self.stimulus_specs:
                s.upload_media(
                    self.s3_bucket, self.local_media_cache_dir, self.remote_media_dir
                )
                bar.next()

        self.write_remote_media_hash()
        logger.info("(%s) Finished uploading media.", self.id)

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
        write_string_to_s3(
            self.hash, bucket_name=self.s3_bucket, key=self.path_to_remote_cache_hash
        )


class VirtualStimulusSet:
    def __init__(self, id_: str, version: str, construct):
        self.id = id_
        self.version = version
        self.construct = construct

        if "prepare" in command_line.FLAGS or not self.cache_exists:
            self.build_cache()

        # if len(sys.argv) > 1 and sys.argv[1] == "prepare":
        #     self.prepare_media()

    def build_cache(self):
        # logger.info("(%s) Building stimulus set cache...", self.id)
        stimulus_set = self.construct()
        self.save_to_cache(stimulus_set)

    @property
    def cache_dir(self):
        return os.path.join("_stimulus_sets", self.id)

    @property
    def cache_path(self):
        return os.path.join(self.cache_dir, f"{self.version}.pickle")

    @property
    def cache_exists(self):
        return os.path.isfile(self.cache_path)

    def save_to_cache(self, stimulus_set):
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "wb") as f:
            pickle.dump(stimulus_set, f)

    def load(self):
        with open(self.cache_path, "rb") as f:
            return pickle.load(f)


class NetworkSpec:
    def __init__(self, phase, participant_group, block, stimulus_set):
        self.phase = phase
        self.participant_group = participant_group
        self.block = block
        self.stimulus_set = (
            stimulus_set  # note: this includes stimuli outside this network too!
        )

    def create_network(
        self, trial_maker_id, experiment, target_num_trials_per_stimulus
    ):
        network = StaticNetwork(
            trial_maker_id=trial_maker_id,
            phase=self.phase,
            participant_group=self.participant_group,
            block=self.block,
            stimulus_set=self.stimulus_set,
            experiment=experiment,
            target_num_trials_per_stimulus=target_num_trials_per_stimulus,
        )
        db.session.add(network)
        db.session.commit()


class StaticTrial(Trial):
    """
    A Trial class for static experiments.

    The user must override the ``time_estimate`` class attribute,
    providing the estimated duration of the trial in seconds.
    This is used for predicting the participant's bonus payment
    and for constructing the progress bar.

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
        The user should not typically change this directly.

    earliest_async_process_start_time : Optional[datetime]
        Time at which the earliest pending async process was called.

    definition
        A dictionary of parameters defining the trial.
        This dictionary combines the dictionaries of the
        respective
        :class:`~psynet.trial.static.StimulusSpec`
        and
        :class:`~psynet.trial.static.StimulusVersionSpec`
        objects.

    stimulus_version
        The corresponding :class:`~psynet.trial.static.StimulusVersion`
        object.

    stimulus
        The corresponding :class:`~psynet.trial.static.Stimulus`
        object.

    phase
        The phase of the experiment, e.g. ``"training"`` or ``"main"``.

    participant_group
        The associated participant group.

    block
        The block in which the trial is situated.
    """

    __extra_vars__ = Trial.__extra_vars__.copy()

    stimulus_id = claim_field("stimulus_id", __extra_vars__, int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stimulus_id = self.stimulus_version.stimulus_id

    def show_trial(self, experiment, participant):
        raise NotImplementedError

    @property
    @extra_var(__extra_vars__)
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
        :class:`~psynet.trial.static.Stimulus`
        and :class:`~psynet.trial.static.StimulusVersion`
        objects.
        """
        return {**self.stimulus.definition, **self.stimulus_version.definition}

    def summarize(self):
        return {
            "participant_group": self.participant_group,
            "phase": self.phase,
            "block": self.block,
            "definition": self.definition,
            "media_url": self.media_url,
            "trial_id": self.id,
            "stimulus_id": self.stimulus.id,
            "stimulus_version_id": self.stimulus_version.id,
        }


class StaticTrialMaker(NetworkTrialMaker):
    """
    Administers a sequence of trials in a static experiment.
    The class is intended for use with the
    :class:`~psynet.trial.static.StaticTrial` helper class.
    which should be customised to show the relevant stimulus
    for the experimental paradigm.
    The user must also define their stimulus set
    using the following built-in classes:

    * :class:`~psynet.trial.static.StimulusSet`;

    * :class:`~psynet.trial.static.StimulusSpec`;

    * :class:`~psynet.trial.static.StimulusVersionSpec`;

    In particular, a :class:`~psynet.trial.static.StimulusSet`
    contains a list of :class:`~psynet.trial.static.StimulusSpec` objects,
    which in turn contains a list of
    :class:`~psynet.trial.static.StimulusVersionSpec` objects.

    The user may also override the following methods, if desired:

    * :meth:`~psynet.trial.static.StaticTrialMaker.choose_block_order`;
      chooses the order of blocks in the experiment. By default the blocks
      are ordered randomly.

    * :meth:`~psynet.trial.static.StaticTrialMaker.choose_participant_group`;
      assigns the participant to a group. By default the participant is assigned
      to a random group.

    * :meth:`~psynet.trial.main.TrialMaker.on_complete`,
      run once the sequence of trials is complete.

    * :meth:`~psynet.trial.main.TrialMaker.performance_check`;
      checks the performance of the participant
      with a view to rejecting poor-performing participants.

    * :meth:`~psynet.trial.main.TrialMaker.compute_bonus`;
      computes the final performance bonus to assign to the participant.

    Further customisable options are available in the constructor's parameter list,
    documented below.

    Parameters
    ----------

    trial_class
        The class object for trials administered by this maker
        (should subclass :class:`~psynet.trial.static.StaticTrial`).

    phase
        Arbitrary label for this phase of the experiment, e.g.
        "practice", "train", "test".

    stimulus_set
        The stimulus set to be administered.

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

    max_trials_per_block
        Determines the maximum number of trials that a participant will be allowed to experience in each block,
        including failed trials. Note that this number does not include repeat trials.

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
        If ``True`` (default), active balancing across participants is enabled, meaning that
        stimulus selection favours stimuli that have been presented fewest times to any participant
        in the experiment, excluding failed trials.
        This criterion defers to ``active_balancing_within_participants``;
        if both ``active_balancing_within_participants=True``
        and ``active_balancing_across_participants=True``,
        then the latter criterion is only used for tie breaking.

    check_performance_at_end
        If ``True``, the participant's performance
        is evaluated at the end of the series of trials.
        Defaults to ``False``.
        See :meth:`~psynet.trial.main.TrialMaker.performance_check`
        for implementing performance checks.

    check_performance_every_trial
        If ``True``, the participant's performance
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

    num_repeat_trials
        Number of repeat trials to present to the participant. These trials
        are typically used to estimate the reliability of the participant's
        responses. Repeat trials are presented at the end of the trial maker,
        after all blocks have been completed.
        Defaults to 0.

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
        id_: str,
        trial_class,
        phase: str,
        stimulus_set: StimulusSet,
        recruit_mode: Optional[str] = None,
        target_num_participants: Optional[int] = None,
        target_num_trials_per_stimulus: Optional[int] = None,
        max_trials_per_block: Optional[int] = None,
        allow_repeated_stimuli: bool = False,
        max_unique_stimuli_per_block: Optional[int] = None,
        active_balancing_within_participants: bool = True,
        active_balancing_across_participants: bool = True,
        check_performance_at_end: bool = False,
        check_performance_every_trial: bool = False,
        fail_trials_on_premature_exit: bool = True,
        fail_trials_on_participant_performance_check: bool = True,
        num_repeat_trials: int = 0,
    ):
        if recruit_mode == "num_participants" and target_num_participants is None:
            raise ValueError(
                "<target_num_participants> cannot be None if recruit_mode == 'num_participants'."
            )
        if recruit_mode == "num_trials" and target_num_trials_per_stimulus is None:
            raise ValueError(
                "<target_num_trials_per_stimulus> cannot be None if recruit_mode == 'num_trials'."
            )
        if (target_num_participants is not None) and (
            target_num_trials_per_stimulus is not None
        ):
            raise ValueError(
                "<target_num_participants> and <target_num_trials_per_stimulus> cannot both be provided."
            )

        self.stimulus_set = stimulus_set.load()
        self.target_num_participants = target_num_participants
        self.target_num_trials_per_stimulus = target_num_trials_per_stimulus
        self.max_trials_per_block = max_trials_per_block
        self.allow_repeated_stimuli = allow_repeated_stimuli
        self.max_unique_stimuli_per_block = max_unique_stimuli_per_block
        self.active_balancing_within_participants = active_balancing_within_participants
        self.active_balancing_across_participants = active_balancing_across_participants

        expected_num_trials = self.estimate_num_trials(num_repeat_trials)
        super().__init__(
            id_=id_,
            trial_class=trial_class,
            network_class=StaticNetwork,
            phase=phase,
            expected_num_trials=expected_num_trials,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=False,
            recruit_mode=recruit_mode,
            target_num_participants=target_num_participants,
            num_repeat_trials=num_repeat_trials,
            wait_for_networks=True,
        )

        self.check_stimulus_set()

    def check_stimulus_set(self):
        if self.phase != self.stimulus_set.phase:
            raise ValueError(
                f"Trial-maker '{self.id}' has a chosen phase of '{self.phase}', "
                + f"which contradicts the phase selected in the stimulus set ('{self.stimulus_set.phase}')."
            )

    @property
    def num_trials_still_required(self):
        # Old version:
        # return sum([stimulus.num_trials_still_required for stimulus in self.stimuli])

        stimuli = self.stimuli
        stimulus_actual_counts = self.get_trial_counts(stimuli)
        stimulus_target_counts = [s.target_num_trials for s in stimuli]
        stimulus_remaining_trials = [
            max(0, target - actual)
            for target, actual in zip(stimulus_target_counts, stimulus_actual_counts)
        ]

        return sum(stimulus_remaining_trials)

    @property
    def stimuli(self):
        return reduce(operator.add, [n.stimuli for n in self.networks])

    def init_participant(self, experiment, participant):
        """
        Initializes the participant at the beginning of the sequence of trials.
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
        self.init_completed_stimuli_in_phase(participant)

    def estimate_num_trials_in_block(self, num_stimuli_in_block):
        if self.allow_repeated_stimuli:
            return self.max_trials_per_block
        else:
            if self.max_trials_per_block is None:
                return num_stimuli_in_block
            else:
                return min(num_stimuli_in_block, self.max_trials_per_block)

    def estimate_num_trials(self, num_repeat_trials):
        return (
            mean(
                [
                    sum(
                        [
                            self.estimate_num_trials_in_block(num_stimuli_in_block)
                            for num_stimuli_in_block in num_stimuli_by_block.values()
                        ]
                    )
                    for participant_group, num_stimuli_by_block in self.stimulus_set.num_stimuli.items()
                ]
            )
            + num_repeat_trials
        )

    def finalize_trial(self, answer, trial, experiment, participant):
        """
        This calls the base class's ``finalize_trial`` method,
        then increments the number of completed stimuli in the phase and the block.
        """
        super().finalize_trial(answer, trial, experiment, participant)
        self.increment_completed_stimuli_in_phase_and_block(
            participant, trial.block, trial.stimulus_id
        )
        # trial.stimulus.num_completed_trials += 1

    def init_block_order(self, experiment, participant):
        self.set_block_order(
            participant,
            self.choose_block_order(experiment=experiment, participant=participant),
        )

    @property
    def block_order_var_id(self):
        return self.with_namespace("block_order")

    def set_block_order(self, participant, block_order):
        participant.var.new(self.block_order_var_id, block_order)

    def get_block_order(self, participant):
        return participant.var.get(self.with_namespace("block_order"))

    def init_completed_stimuli_in_phase(self, participant):
        participant.var.set(
            self.with_namespace("completed_stimuli_in_phase"),
            {block: Counter() for block in self.stimulus_set.blocks},
        )

    def get_completed_stimuli_in_phase(self, participant):
        all_counters = participant.var.get(
            self.with_namespace("completed_stimuli_in_phase")
        )

        def load_counter(input):
            return Counter({int(key): value for key, value in input.items()})

        return {block: load_counter(counter) for block, counter in all_counters.items()}

    def get_completed_stimuli_in_phase_and_block(self, participant, block):
        all_counters = self.get_completed_stimuli_in_phase(participant)
        return all_counters[block]

    def increment_completed_stimuli_in_phase_and_block(
        self, participant, block, stimulus_id
    ):
        all_counters = self.get_completed_stimuli_in_phase(participant)
        all_counters[block][stimulus_id] += 1
        participant.var.set(
            self.with_namespace("completed_stimuli_in_phase"), all_counters
        )

    # def append_completed_stimuli_in_phase(self, participant, block, stimulus_id):
    #     assert isinstance(value, int)
    #     counter = self.get_completed_stimuli_in_phase(participant, block)
    #     counter[value] += 1
    #     self.set_completed_stimuli_in_phase(participant, block, counter)

    def on_complete(self, experiment, participant):
        pass

    def experiment_setup_routine(self, experiment):
        """
        All networks for the static experiment are set up at the beginning of
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
        Determines the participant group assigned to the current participant
        (ignored if the participant already has been assigned to a participant group for that trial maker
        using e.g. participant.set_participant_group).
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
                trial_maker_id=self.id,
                experiment=experiment,
                target_num_trials_per_stimulus=self.target_num_trials_per_stimulus,
            )
        experiment.save()

    def find_networks(self, participant, experiment, ignore_async_processes=False):
        # pylint: disable=protected-access
        block_order = participant.var.get(self.with_namespace("block_order"))
        networks = StaticNetwork.query.filter_by(
            trial_maker_id=self.id,
            participant_group=participant.get_participant_group(self.id),
            phase=self.phase,
        ).filter(StaticNetwork.block.in_(block_order))
        if not ignore_async_processes:
            networks = networks.filter_by(awaiting_async_process=False)
        networks = networks.all()
        networks.sort(key=lambda network: block_order.index(network.block))
        return networks

    def grow_network(self, network, participant, experiment):
        """
        Does nothing, because networks never get expanded in a static experiment.
        """
        return False

    def find_node(self, network, participant, experiment):
        stimulus = self.find_stimulus(network, participant, experiment)
        if stimulus is None:
            return None
        return self.find_stimulus_version(stimulus, participant, experiment)

    def count_completed_trials_in_network(self, network, participant):
        return self.trial_class.query.filter_by(
            network_id=network.id,
            participant_id=participant.id,
            complete=True,
            is_repeat_trial=False,
        ).count()

    def find_stimulus(self, network, participant, experiment):
        # pylint: disable=unused-argument,protected-access
        if (
            self.max_trials_per_block is not None
            and self.count_completed_trials_in_network(network, participant)
            >= self.max_trials_per_block
        ):
            return None
        completed_stimuli = self.get_completed_stimuli_in_phase_and_block(
            participant, block=network.block
        )
        allow_new_stimulus = self.check_allow_new_stimulus(completed_stimuli)
        candidates = Stimulus.query.filter_by(
            network_id=network.id
        ).all()  # networks are guaranteed to be from the correct phase
        if not self.allow_repeated_stimuli:
            candidates = self.filter_out_repeated_stimuli(candidates, completed_stimuli)
        if not allow_new_stimulus:
            candidates = self.filter_out_new_stimuli(candidates, completed_stimuli)

        candidates = self.custom_stimulus_filter(
            candidates=candidates, participant=participant
        )
        if not isinstance(candidates, list):
            return ValueError("custom_stimulus_filter must return a list of stimuli")

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

    def custom_stimulus_filter(self, candidates, participant):
        """
        Override this function to define a custom filter for choosing the participant's next stimulus.

        Parameters
        ----------
        candidates:
            The current list of candidate stimuli as defined by the built-in static experiment procedure.

        participant:
            The current participant.

        Returns
        -------

        An updated list of candidate stimuli. The default implementation simply returns the original list.
        The experimenter might alter this function to remove certain stimuli from the list.
        """
        return candidates

    def custom_stimulus_version_filter(self, candidates, participant):
        """
        Override this function to define a custom filter for choosing the participant's next stimulus version.

        Parameters
        ----------
        candidates:
            The current list of candidate stimulus versions as defined by the built-in static experiment procedure.

        participant:
            The current participant.

        Returns
        -------

        An updated list of candidate stimulus versions. The default implementation simply returns the original list.
        The experimenter might alter this function to remove certain stimulus versions from the list.
        """
        return candidates

    @staticmethod
    def filter_out_repeated_stimuli(candidates, completed_stimuli):
        return [x for x in candidates if x.id not in completed_stimuli.keys()]

    @staticmethod
    def filter_out_new_stimuli(candidates, completed_stimuli):
        return [x for x in candidates if x.id in completed_stimuli.keys()]

    @staticmethod
    def balance_within_participants(candidates, completed_stimuli):
        candidate_counts_within = [
            completed_stimuli[candidate.id] for candidate in candidates
        ]
        min_count_within = (
            0 if len(candidate_counts_within) == 0 else min(candidate_counts_within)
        )
        return [
            candidate
            for candidate, candidate_count_within in zip(
                candidates, candidate_counts_within
            )
            if candidate_count_within == min_count_within
        ]

    def get_trial_counts(self, stimuli, new=True):
        # Old inefficient version:
        if not new:
            return [s.num_completed_trials for s in stimuli]

        # New version:
        n_trials_all_stimuli = filter_for_completed_trials(
            db.session.query(
                StaticTrial.stimulus_id, func.count(StaticTrial.id)
            ).group_by(StaticTrial.stimulus_id)
        ).all()
        n_trials_all_stimuli = {x[0]: x[1] for x in n_trials_all_stimuli}

        def get_count(stimulus):
            try:
                return n_trials_all_stimuli[stimulus.id]
            except KeyError:
                return 0

        return [get_count(stim) for stim in stimuli]

    def balance_across_participants(self, candidates):
        # candidate_counts_across = [candidate.num_completed_trials for candidate in candidates]
        candidate_counts_across = self.get_trial_counts(candidates)
        # logger.info("%s", [
        #     (candidate.id, count) for candidate, count in zip(candidates, candidate_counts_across)
        # ])

        min_count_across = (
            0 if len(candidate_counts_across) == 0 else min(candidate_counts_across)
        )
        return [
            candidate
            for candidate, candidate_count_across in zip(
                candidates, candidate_counts_across
            )
            if candidate_count_across == min_count_across
        ]

    def find_stimulus_version(self, stimulus, participant, experiment):
        # pylint: disable=unused-argument
        candidates = StimulusVersion.query.filter_by(stimulus_id=stimulus.id).all()
        assert len(candidates) > 0
        candidates = self.custom_stimulus_version_filter(
            candidates=candidates, participant=participant
        )
        if not isinstance(candidates, list):
            return ValueError(
                "custom_stimulus_version_filter must return a list of stimuli"
            )
        if len(candidates) == 0:
            return ValueError("custom_stimulus_version_filter returned an empty list")

        return random.choice(candidates)


class StaticNetwork(TrialNetwork):
    """
    A :class:`~psynet.trial.main.TrialNetwork` class for static experiments.
    The user should not have to engage with this class directly,
    except through the network visualisation tool and through
    analysing the resulting data.
    The networks are organised as follows:

    1. At the top level of the hierarchy, different networks correspond to different
       combinations of participant group and block.
       If the same experiment contains many
       :class:`~psynet.trial.static.StaticTrialMaker` objects
       with different associated :class:`~psynet.trial.static.StaticTrial`
       classes,
       then networks will also be differentiated by the names of these
       :class:`~psynet.trial.static.StaticTrial` classes.

    2. Within a given network, the first level of the hierarchy is the
       :class:`~psynet.trial.static.Stimulus` class.
       These objects subclass the Dallinger :class:`~dallinger.models.Node` class,
       and are generated directly from :class:`~psynet.trial.static.StimulusSpec` instances.

    3. Nested within :class:`~psynet.trial.static.Stimulus` objects
       are :class:`~psynet.trial.static.StimulusVersion` objects.
       These also subclass the Dallinger :class:`~dallinger.models.Node` class,
       and are generated directly from :class:`~psynet.trial.static.StimulusVersionSpec` instances.

    4. Nested within :class:`~psynet.trial.static.StimulusVersion` objects
       are :class:`~psynet.trial.static.StaticTrial` objects.
       These objects subclass the Dallinger :class:`~dallinger.models.Info` class.

    Attributes
    ----------

    target_num_trials : int or None
        Indicates the target number of trials for that network.
        Stored as the field ``property2`` in the database.

    awaiting_async_process : bool
        Whether the network is currently closed and waiting for an asynchronous process to complete.
        This should always be ``False`` for static experiments.

    earliest_async_process_start_time : Optional[datetime]
        Time at which the earliest pending async process was called.

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
        Returns the number of completed and non-failed trials in the network,
        irrespective of asynchronous processes,
        but excluding end-of-phase repeat trials.

    stimuli : list
        Returns the stimuli associated with the network.

    num_stimuli : int
        Returns the number of stimuli associated with the network.

    var : :class:`~psynet.field.VarStore`
        A repository for arbitrary variables; see :class:`~psynet.field.VarStore` for details.
    """

    # pylint: disable=abstract-method

    __extra_vars__ = TrialNetwork.__extra_vars__.copy()

    participant_group = claim_field("participant_group", __extra_vars__, str)
    block = claim_field("block", __extra_vars__, str)

    creation_started = claim_var("creation_started", __extra_vars__)
    creation_progress = claim_var("creation_progress", __extra_vars__)

    def __init__(
        self,
        *,
        trial_maker_id,
        phase,
        participant_group,
        block,
        stimulus_set,
        experiment,
        target_num_trials_per_stimulus,
    ):
        self.participant_group = participant_group
        self.block = block
        self.creation_started = False
        self.creation_progress = 0.0
        super().__init__(trial_maker_id, phase, experiment)
        db.session.add(self)
        if not self.creation_started:
            self.creation_started = True
            self.queue_async_method(
                "populate",
                stimulus_set=stimulus_set,
                target_num_trials_per_stimulus=target_num_trials_per_stimulus,
            )
        db.session.commit()

    def populate(self, stimulus_set, target_num_trials_per_stimulus):
        source = TrialSource(network=self)
        db.session.add(source)
        stimulus_specs = [
            x
            for x in stimulus_set.stimulus_specs
            if x.phase == self.phase
            and x.participant_group == self.participant_group
            and x.block == self.block
        ]
        N = len(stimulus_specs)
        n = 0
        for i, stimulus_spec in enumerate(stimulus_specs):
            stimulus_spec.add_stimulus_to_network(
                network=self,
                source=source,
                target_num_trials=target_num_trials_per_stimulus,
                stimulus_set=stimulus_set,
            )
            n = i + 1
            if n % 100 == 0:
                logger.info("Populated network %i with %i/%i stimuli...", self.id, n, N)
                self.creation_progress = (1 + i) / N
                db.session.commit()
        logger.info("Finished populating network %i with %i/%i stimuli.", self.id, n, N)
        self.creation_progress = 1.0
        db.session.commit()

    @property
    def stimulus_query(self):
        return Stimulus.query.filter_by(network_id=self.id)

    @property
    def stimuli(self):
        return self.stimulus_query.all()

    @property
    def num_stimuli(self):
        return self.stimulus_query.count()


class LocalMediaStimulusVersionSpec(StimulusVersionSpec):
    has_media = True

    def __init__(self, definition, media_ext):
        super().__init__(definition)
        self.media_ext = media_ext

    @classmethod
    def generate_media(cls, definition, output_path):
        shutil.copyfile(definition["local_media_path"], output_path)


def stimulus_set_from_dir(
    id_: str, input_dir: str, media_ext: str, phase: str, version: str, s3_bucket: str
):
    # example media_ext: .wav

    def construct():
        return compile_stimulus_set_from_dir(
            id_, input_dir, media_ext, phase, version, s3_bucket
        )

    return VirtualStimulusSet(id_, version, construct)


def compile_stimulus_set_from_dir(
    id_: str, input_dir: str, media_ext: str, phase: str, version: str, s3_bucket: str
):
    # example media_ext: .wav
    stimuli = []
    participant_groups = [(f.name, f.path) for f in os.scandir(input_dir) if f.is_dir()]
    for participant_group, group_path in participant_groups:
        blocks = [(f.name, f.path) for f in os.scandir(group_path) if f.is_dir()]
        for block, block_path in blocks:
            media_files = [
                (f.name, f.path)
                for f in os.scandir(block_path)
                if f.is_file() and f.path.endswith(media_ext)
            ]
            for media_name, media_path in media_files:
                stimuli.append(
                    StimulusSpec(
                        definition={
                            "name": media_name,
                        },
                        phase=phase,
                        version_specs=[
                            LocalMediaStimulusVersionSpec(
                                definition={"local_media_path": media_path},
                                media_ext=media_ext,
                            )
                        ],
                        participant_group=participant_group,
                        block=block,
                    )
                )
    return StimulusSet(id_, stimuli, version=version, s3_bucket=s3_bucket)
