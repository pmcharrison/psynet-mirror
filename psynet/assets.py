import os
import shutil

from dallinger import db
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String

from .data import SQLBase, SQLMixin, register_table
from .timeline import ExperimentSetupRoutine, NullElt
from .utils import get_extension


# class AssetRegistry:
#     def link_file(self, url):
#         """
#         Stores a file link in the registry.
#
#         Parameters
#         ----------
#
#         url :
#             URL to that file. The file should be publicly accessible from this URL.
#         """
#         asset = FileAsset(url)
#         db.session.add(asset)
#
#     def link_folder(self, url):
#         asset = ExternalFolderAsset(url, is_)
#         db.session.add(asset)


class AssetType:
    def get_file_size_mb(self, path):
        return self.get_file_size_bytes(path) / (1024 * 1024)

    def get_file_size_bytes(self):
        raise NotImplementedError


class File(AssetType):
    def get_file_size_bytes(self):
        return os.path.getsize(self.input_path)


class Folder(AssetType):
    def get_file_size_bytes(self):
        sum(entry.stat().st_size for entry in os.scandir(file))


class Audio(File):
    pass


@register_table
class Asset(SQLBase, SQLMixin, NullElt):
    # Inheriting from SQLBase and SQLMixin means that the Asset object is stored in the database.
    # Inheriting from NullElt means that the Asset object can be placed in the timeline.

    __tablename__ = "asset"

    # Remove default SQL columns
    failed = None
    failed_reason = None
    time_of_death = None

    host_location = Column(String)
    type = Column(String)
    extension = Column(String)
    description = Column(String)

    participant_id = Column(Integer, ForeignKey("participant.id"))
    participant = relationship("Participant", back_populates="assets")

    trial_maker_id = Column(String)

    network_id = Column(Integer, ForeignKey("network.id"))
    network = relationship("Network", back_populates="assets")

    node_id = Column(Integer, ForeignKey("node.id"))
    node = relationship("Node", back_populates="assets")

    trial_id = Column(Integer, ForeignKey("trial.id"))
    trial = relationship("Trial", back_populates="assets")

    def __init__(
        self,
        type="file",
        participant_id=None,
        trial_maker_id=None,
        network_id=None,
        node_id=None,
        trial_id=None,
    ):
        self.type = type
        self._type = self.types[type]
        self.extension = self.get_extension()
        self.participant_id = participant_id
        self.trial_maker_id = trial_maker_id
        self.network_id = network_id
        self.node_id = node_id
        self.trial_id = trial_id

    types = dict(
        file=File,
        folder=Folder,
        audio=Audio,
    )

    def get_extension(self):
        raise NotImplementedError

    def prepare_for_deployment(self, experiment):
        "Runs in advance of the experiment being deployed to the remote server."
        raise NotImplementedError


class InternalAsset(Asset):
    input_path = Column(String)
    obfuscate = Column(Boolean)
    deposited = Column(Boolean)
    key = Column(String)
    size_mb = Column(Float)
    deposit_time_sec = Column(Float)

    def __init__(
        self,
        input_path,
        type=None,
        key=None,
        obfuscate=0,  # 0: no obfuscation; 1: can't guess URL; 2: can't guess content
        participant_id=None,
        trial_maker_id=None,
        network_id=None,
        node_id=None,
        trial_id=None,
    ):
        self.deposited = False
        self.input_path = input_path
        self.obfuscate = obfuscate
        super().__init__(
            type, participant_id, trial_maker_id, network_id, node_id, trial_id
        )
        self.size_mb = self.get_size_mb()
        self.key = key

    def get_extension(self):
        return get_extension(self.input_path)

    def deposit(self, storage):
        if self.key is None:
            self.key = self.generate_key()
        info = storage.deposit(asset=self)
        self.deposit_time_sec = info["deposit_time"]

    def get_size_mb(self):
        return self._type.get_size_mb(input_path)

    def generate_key(self):
        return self.generate_dir() + self.generate_filename()

    def generate_dir(self):
        if self.obfuscate == 2:
            return "private/"
        else:
            dir = ""
            if self.participant_id:
                dir += f"participants/{self.participant_id}/"
            if self.trial_maker_id:
                dir += f"{self.trial_maker_id}/"
            return dir

    def generate_filename(self):
        filename = ""
        if self.obfuscate < 2:
            identifiers = []
            if self.network_id:
                identifiers.append(f"network={self.network_id}")
            if self.node_id:
                identifiers.append(f"node={self.node_id}")
            if self.trial_id:
                identifiers.append(f"trial={self.trial_id}")
            filename += "__".join(identifiers)
        if self.obfuscate > 0:
            filename += "__" + str(uuid.uuid4())
        filename += self.extension
        return filename

    def prepare_for_deployment(self, experiment):
        "Runs in advance of the experiment being deployed to the remote server."
        asset = self
        experiment.asset_storage.deposit(asset)


class ExternalAsset(Asset):
    def __init__(
        self,
        host_location,
        type="file",
        participant_id=None,
        trial_maker_id=None,
        network_id=None,
        node_id=None,
        trial_id=None,
    ):
        self.host_location = host_location
        super().__init__(
            type, participant_id, trial_maker_id, network_id, node_id, trial_id
        )

    def get_extension(self):
        return get_extension(self.host_location)

    def prepare_for_deployment(self, experiment):
        "Runs in advance of the experiment being deployed to the remote server."
        pass


class Storage:
    def __init__(self):
        self.deployment_key = self.get_deployment_key()

    def get_deployment_key(self):
        # Time? # App ID?
        raise NotImplementedError

    def deposit(self, asset):
        start = time.perf_counter()
        self._deposit(asset)
        end = time.perf_counter()
        return dict(deposit_time_sec=end - start)

    def _deposit(self, asset):
        raise NotImplementedError


class NoStorage(Storage):
    def deposit(self, asset):
        raise RuntimeError("Asset depositing is not supported by 'NoStorage' objects.")


class LocalStorage(Storage):
    def __init__(self, location):
        self.location = location
        self.root = os.path.join(location, self.deployment_key)

    def deposit(self, asset: InternalAsset):
        key = asset.key
        input_path = asset.input_path
        target_path = os.path.join(self.root, key)

        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if asset.type == "folder":
            shutil.copytree(input_path, target_path, dirs_exist_ok=True)
        else:
            shutil.copyfile(input_path, target_path)

    def deposit(self, asset):
        raise NotImplementedError


class S3Storage(Storage):
    def deposit(self, asset):
        raise NotImplementedError


# Linking from experiment.py
# -- maybe this should happen as part of the experiment class?
# -- maybe people should use the class directly?
#
# Linking from the timeline


# Create if exists logic? This could be applied to stimuli too
# This would be bad for performance, I don't think we can do this. <-----
# Check in DB, do I exist? (maybe use transaction)
# If not, upload
# This logic probably needs


InternalAsset()  # <-- what if the user writes this in experiment.py?


class Exp():
    assets = [
        ExternalAsset(),
        InternalAsset(),
        InternalAsset(),
    ]

    def register_assets(self):  # <-- happens once, at experiment setup
        # We need some logic that allows us to upload locally and then retrieve remotely.
        # The uploading would happen in psynet prepare, creating a manifest.
        # When the experiment launches, that manifest is then used to populate the database.
        # It should be possible to pickle assets (jsonpickle) and retrieve them later.
        for a in self.assets:
            self.storage.add(a)  # <-- includes upload

    # def ensure_assets_are_uploaded(self):
    def prepare_assets_for_deployment(self):
        # Occurs in psynet prepare
        for a in self.assets:
            a.prepare_for_deployment()


    # Each time you recreate an Asset object, the key might be different because of the obfuscation. Does this matter?

    timeline = join(
        ExperimentAssets([
            ExternalAsset(),
            InternalAsset(),  # <-- how do we stop redundant uploads?
            InternalAsset(),  # <-- this is dangerous because each time the experiment loads we'll get a different random key
        ]),
        CodeBlock(lambda participant: InternalAsset(participant_id=participant.id)),

        CodeBlock(lambda storage, participant: storage.add(InternalAsset(participant_id=participant.id))),
    )




# Linking during the experiment, e.g. in a code block
db.session.add(ExternalAsset())


def link_external_asset(
        host_location,
        type="file",
        participant_id=None,
        trial_maker_id=None,
        network_id=None,
        node_id=None,
        trial_id=None,
):
    def f(experiment):
        asset = ExternalAsset(host_location, type, participant_id, trial_maker_id, network_id, node_id, trial_id)
        db.session.add(asset)


def elt_external_asset

def link_asset_folder(url):
    def f(experiment):
        experiment.asset_registry.link_folder(url)

    return ExperimentSetupRoutine(f)


def link_asset_file(url):
    def f(experiment):
        experiment.asset_registry.link_file(url)

    return ExperimentSetupRoutine(f)
