from dallinger import db
from psynet.asset import CachedAsset
from sqlalchemy import Column, String, UniqueConstraint
from sqlalchemy.exc import NoResultFound

from .main import (
    HasDefinition,
    TrialNode,
    GenericTrialNetwork,
)
from ..timeline import NullElt
from ..utils import get_logger

logger = get_logger()


class Source(TrialNode, HasDefinition):
    """
    Parameters
    ----------

    definition
        A dictionary of parameters defining the source.

    participant_group
        The associated participant group.
        Defaults to a common participant group for all participants.

    block
        The associated block.
        Defaults to a single block for all trials.

    key
        Optional key that can be used to access the asset from the timeline.
        If left blank this will be populated automatically so as to be
        unique within a given source collection.

    Attributes
    ----------

    definition : dict
        A dictionary containing the parameter values for the source.

    participant_group : str
        The associated participant group.

    block : str
        The associated block.

    num_completed_trials : int
        The number of completed trials that this source has received,
        excluding failed trials.

    num_trials_still_required : int
        The number of trials still required for this source before the experiment
        can complete, if such a quota exists.
    """
    polymorphic_identity = "TrialSource"

    __extra_vars__ = {
        **TrialNode.__extra_vars__.copy(),
        **HasDefinition.__extra_vars__.copy(),
    }

    module_id = Column(String, index=True)
    participant_group = Column(String)
    block = Column(String)
    key = Column(String, index=True)

    def __init__(
        self,
        definition: dict,
        *,
        participant_group="default",
        block="default",
        assets=None,
        key=None,
    ):
        # Note: We purposefully do not call super().__init__(), because this parent constructor
        # requires the prior existence of the node's parent network, which is impractical for us.
        assert isinstance(definition, dict)

        if assets is None:
            assets = {}

        self.definition = definition
        self.participant_group = participant_group
        self.block = block
        self._staged_assets = assets
        self.key = key

    def stage_assets(self, experiment):
        source_id = self.id
        assert isinstance(source_id, int)

        self.assets = {**self.network.assets}

        for label, asset in self._staged_assets.items():
            if asset.label is None:
                asset.label = label

            if not asset.has_key:
                asset.set_key(
                    f"{self.module_id}/stimuli/source_{source_id}__{asset.label}"
                )

            asset.parent = self

            asset.receive_source_definition(self.definition)
            asset.deposit()

            self.assets[label] = asset

        db.session.commit()
        self.assets = self._staged_assets
        db.session.commit()


UniqueConstraint(Source.module_id, Source.key)


class SourceCollection(NullElt):
    """
    Defines a source collection for a static experiment.
    This source collection is defined as a collection of
    :class:`~psynet.trial.static.Stimulus` objects.

    Parameters
    ----------

    sources: list
        A list of :class:`~psynet.trial.static.Stimulus` objects.
    """

    def __init__(
        self,
        module_id: str,
        sources,
    ):
        assert isinstance(sources, list)
        assert isinstance(id_, str)

        self.sources = sources
        self.module_id = module_id
        self.trial_maker = None

    def __getitem__(self, item):
        try:
            return Source.query.filter_by(
                module_id=self.module_id, key=item
            ).one()
        except NoResultFound:
            return [source for source in self.sources if source.key == item][0]
        except IndexError:
            raise KeyError

    def items(self):
        from psynet.experiment import is_experiment_launched

        if is_experiment_launched():
            sources = Source.query.filter_by(
                module_id=self.module_id,
            ).all()
        else:
            sources = self.sources

        return [(stim.key, stim) for stim in sources]

    def keys(self):
        return [stim[0] for stim in self.items()]

    def values(self):
        return [stim[1] for stim in self.items()]


class SourceRegistry:
    csv_path = "source_registry.csv"

    def __init__(self, experiment):
        self.experiment = experiment
        self.timeline = experiment.timeline
        self.stimuli = {}
        self.compile_source_collections()
        # self.compile_stimuli()

    def __getitem__(self, item):
        try:
            return self.stimuli[item]
        except KeyError:
            raise KeyError(
                f"Can't find the source set '{item}' in the timeline. Are you sure you remembered to add it?"
            )

    # @property
    # def stimuli(self):
    #     return [
    #         s
    #         for _source_collection in self.source_collections.values()
    #         for s in _source_collection.stimuli
    #     ]

    def compile_source_collections(self):
        for elt in self.timeline.elts:
            if isinstance(elt, SourceCollection):
                id_ = elt.module_id
                assert id_ is not None
                if id_ in self.stimuli and elt != self.stimuli[id_]:
                    raise RuntimeError(
                        f"Tried to register two non-identical source collections with the same ID: {id_}"
                    )
                self.stimuli[id_] = elt

    def prepare_for_deployment(self):
        self.create_networks()
        self.stage_assets()

    def create_networks(self):
        for source_collection in self.stimuli.values():
            source_collection.create_networks(self.experiment)
        generic_network = GenericTrialNetwork(self.experiment)
        db.session.add(generic_network)
        db.session.commit()

    def stage_assets(self):
        for source_collection in self.stimuli.values():
            for source in source_collection.values():
                source.stage_assets(self.experiment)
        db.session.commit()


class SourceCollectionFromDir(SourceCollection):
    def __init__(
        self, id_: str, input_dir: str, media_ext: str, asset_label: str = "prompt"
    ):
        sources = []
        participant_groups = [
            (f.name, f.path) for f in os.scandir(input_dir) if f.is_dir()
        ]
        for participant_group, group_path in participant_groups:
            blocks = [(f.name, f.path) for f in os.scandir(group_path) if f.is_dir()]
            for block, block_path in blocks:
                media_files = [
                    (f.name, f.path)
                    for f in os.scandir(block_path)
                    if f.is_file() and f.path.endswith(media_ext)
                ]
                for media_name, media_path in media_files:
                    sources.append(
                        Source(
                            definition={
                                "name": media_name,
                            },
                            assets={
                                asset_label: CachedAsset(
                                    input_path=media_path,
                                    extension=media_ext,
                                )
                            },
                            participant_group=participant_group,
                            block=block,
                        )
                    )
        return super().__init__(id_, sources)
