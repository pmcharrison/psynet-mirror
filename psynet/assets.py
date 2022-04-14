import os
import shutil
import jsonpickle
import time
import uuid

from dallinger import db
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .data import SQLBase, SQLMixin, register_table
from .timeline import NullElt
from .utils import get_extension


class AssetType:
    def get_file_size_mb(self, path):
        return self.get_file_size_bytes(path) / (1024 * 1024)

    def get_file_size_bytes(self, path):
        raise NotImplementedError


class File(AssetType):
    def get_file_size_bytes(self, path):
        return os.path.getsize(path)


class Folder(AssetType):
    def get_file_size_bytes(self, path):
        sum(entry.stat().st_size for entry in os.scandir(path))


class Audio(File):
    pass


@register_table
class Asset(SQLBase, SQLMixin, NullElt):
    # Inheriting from SQLBase and SQLMixin means that the Asset object is stored in the database.
    # Inheriting from NullElt means that the Asset object can be placed in the timeline.

    __tablename__ = "asset"

    # Remove default SQL columns
    id = None
    failed = None
    failed_reason = None
    time_of_death = None

    key = Column(String, primary_key=True, index=True)
    host_location = Column(String)
    type = Column(String)
    extension = Column(String)

    participant_id = Column(Integer, ForeignKey("participant.id"))
    participant = relationship("psynet.participant.Participant", backref="assets")

    trial_maker_id = Column(String)

    network_id = Column(Integer, ForeignKey("network.id"))
    network = relationship("Network", backref="assets")

    node_id = Column(Integer, ForeignKey("node.id"))
    node = relationship("Node", backref="assets")

    trial_id = Column(Integer, ForeignKey("info.id"))
    trial = relationship("Trial", backref="assets")

    def __init__(
        self,
        type_="file",
        participant_id=None,
        trial_maker_id=None,
        network_id=None,
        node_id=None,
        trial_id=None,
    ):
        self.type = type_
        self._type = self.types[type_]
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

    def prepare_for_deployment(self, asset_storage):
        """Runs in advance of the experiment being deployed to the remote server."""
        raise NotImplementedError


class ExperimentAsset(Asset):
    input_path = Column(String)
    obfuscate = Column(Boolean)
    deposited = Column(Boolean)
    size_mb = Column(Float)
    deposit_time_sec = Column(Float)

    def __init__(
        self,
        input_path,
        type_=None,
        key=None,
        obfuscate=1,  # 0: no obfuscation; 1: can't guess URL; 2: can't guess content
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
            type_, participant_id, trial_maker_id, network_id, node_id, trial_id
        )
        self.size_mb = self.get_size_mb()
        self.key = key

    def get_extension(self):
        return get_extension(self.input_path)

    def deposit(self, storage):
        if self.key is None:
            self.key = self.generate_key()

        time_start = time.perf_counter()
        storage.receive_deposit(asset=self)
        time_end = time.perf_counter()

        self.deposit_time_sec = time_end - time_start
        self.deposited = True
        db.session.add(self)
        db.session.commit()

    def get_size_mb(self):
        return self._type.get_file_size_mb(self.input_path)

    def generate_key(self):
        return self.generate_dir() + self.generate_filename()

    def generate_dir(self):
        if self.obfuscate == 2:
            return "private/"
        else:
            dir_ = ""
            if self.participant_id:
                dir_ += f"participants/{self.participant_id}/"
            if self.trial_maker_id:
                dir_ += f"{self.trial_maker_id}/"
            return dir_

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

    def prepare_for_deployment(self, asset_storage):
        """Runs in advance of the experiment being deployed to the remote server."""
        self.deposit(asset_storage)


class ExternalAsset(Asset):
    def __init__(
            self,
            host_location,
            key,
            type_="file",
            participant_id=None,
            trial_maker_id=None,
            network_id=None,
            node_id=None,
            trial_id=None,
    ):
        self.host_location = host_location
        self.key = key
        super().__init__(
            type_, participant_id, trial_maker_id, network_id, node_id, trial_id
        )

    def get_extension(self):
        return get_extension(self.host_location)

    def prepare_for_deployment(self, asset_storage):
        """Runs in advance of the experiment being deployed to the remote server."""
        pass


class AssetStorage:
    def __init__(self):
        self.deployment_key = None

    def prepare_for_deployment(self):
        self.load_deployment_key()

    def load_deployment_key(self):
        if not self.deployment_key:
            from .experiment import Experiment
            self.deployment_key = Experiment.read_deployment_id()
            if self.deployment_key is None:
                raise Experiment.MissingDeploymentIdError

    def deposit(self, asset):
        self.load_deployment_key()


class NoStorage(AssetStorage):
    def deposit(self, asset):
        super().deposit(asset)
        raise RuntimeError("Asset depositing is not supported by 'NoStorage' objects.")


class LocalStorage(AssetStorage):
    def __init__(self, root):
        super().__init__()
        self.root = root

    def deposit(self, asset: ExperimentAsset):
        super().deposit(asset)

        key = asset.key
        input_path = asset.input_path
        target_path = os.path.join(self.root, self.deployment_key, key)

        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if asset.type == "folder":
            shutil.copytree(input_path, target_path, dirs_exist_ok=True)
        else:
            shutil.copyfile(input_path, target_path)


class S3Storage(AssetStorage):
    def deposit(self, asset):
        super().deposit(asset)

        raise NotImplementedError


class AssetRegistry:
    initial_asset_manifesto_path = "initial_asset_manifesto.json"

    def __init__(self, asset_storage: AssetStorage):
        self.asset_storage = asset_storage
        self.assets = []

    def register(self, asset):
        self.assets.append(asset)

    def prepare_for_deployment(self):
        self.prepare_assets_for_deployment()
        self.asset_storage.prepare_for_deployment()

    def prepare_assets_for_deployment(self):
        for a in self.assets:
            a.prepare_for_deployment(asset_storage=self.asset_storage)
        self.save_initial_asset_manifesto()

    def save_initial_asset_manifesto(self):
        encoded = jsonpickle.encode(self.assets)
        with open(self.initial_asset_manifesto_path, "w") as file:
            file.write(encoded)

    def load_initial_asset_manifesto(self):
        with open(self.initial_asset_manifesto_path, "r") as file:
            encoded = file.read()
        return jsonpickle.decode(encoded)

    def on_experiment_launch(self):
        self.populate_db_with_initial_assets()

    def populate_db_with_initial_assets(self):
        self.assets = self.load_initial_asset_manifesto()
        for a in self.assets:
            db.session.add(a)
        db.session.commit()
