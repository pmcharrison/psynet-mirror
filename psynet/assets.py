import os
import shutil

from dallinger import db
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String

from .dashboard import show_in_dashboard
from .data import SQLBase, SQLMixin
from .timeline import ExperimentSetupRoutine
from .utils import get_extension


class AssetRegistry:
    def link_file(self, url):
        """
        Stores a file link in the registry.

        Parameters
        ----------

        url :
            URL to that file. The file should be publicly accessible from this URL.
        """
        asset = FileAsset(url)
        db.session.add(asset)

    def link_folder(self, url):
        asset = ExternalFolderAsset(url, is_)
        db.session.add(asset)


class FileType():
    def get_file_size_mb(self, path):
        return self.get_file_size_bytes(path) / (1024 * 1024)

    def get_file_size_bytes(self):
        raise NotImplementedError


class File(FileType):
    def get_file_size_bytes(self):
        return os.path.getsize(self.input_path)


class Folder(FileType):
    def get_file_size_bytes(self):
        sum(entry.stat().st_size for entry in os.scandir(file))


class Audio(File):
    pass


@show_in_dashboard
class Asset(SQLBase, SQLMixin):
    __tablename__ = "asset"

    # Remove default SQL columns
    failed = None
    failed_reason = None
    time_of_death = None

    host_location = Column(String)
    file_type = Column(String)
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
            file_type="file",
            participant_id=None,
            trial_maker_id=None,
            network_id=None,
            node_id=None,
            trial_id=None,
    ):
        self.file_type = file_type
        self._file_type = self.file_types[file_type]
        self.extension = self.get_extension()
        self.participant_id = participant_id
        self.trial_maker_id = trial_maker_id
        self.network_id = network_id
        self.node_id = node_id
        self.trial_id = trial_id

    file_types = dict(
        file=File,
        folder=Folder,
        audio=Audio,
    )

    def get_extension(self):
        raise NotImplementedError


class InternalAsset(Asset):
    input_path = Column(String)
    obfuscate = Column(Boolean)
    key = Column(String)
    size_mb = Column(Float)
    deposit_time_sec = Column(Float)

    def __init__(
            self,
            input_path,
            storage,
            file_type=None,
            key=None,
            obfuscate=0,  # 0: no obfuscation; 1: can't guess URL; 2: can't guess content
            participant_id=None,
            trial_maker_id=None,
            network_id=None,
            node_id=None,
            trial_id=None,
    ):
        self.input_path = input_path
        self.obfuscate = obfuscate
        super().__init__(file_type, participant_id, trial_maker_id, network_id, node_id, trial_id)
        self.size_mb = self.get_size_mb()
        self.key = key if key else self.generate_key()
        self.deposit(storage)

    def get_extension(self):
        return get_extension(self.input_path)

    def deposit(self, storage):
        info = storage.deposit(asset=self)
        self.deposit_time_sec = info["deposit_time"]

    def get_size_mb(self):
        return self._file_type.get_size_mb(input_path)

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




class ExternalAsset(Asset):
    def __init__(
            self,
            host_location,
            file_type="file",
            participant_id=None,
            trial_maker_id=None,
            network_id=None,
            node_id=None,
            trial_id=None,
    ):
        self.host_location = host_location
        super().__init__(file_type, participant_id, trial_maker_id, network_id, node_id, trial_id)

    def get_extension(self):
        return get_extension(self.host_location)

class Storage:
    def deposit(self, asset):
        info = {}
        info["size_mb"] = asset.

        raise NotImplementedError

    def _deposit(self, asset):
        raise NotImplementedError


class NoStorage(Storage):
    def deposit(self, asset):
        raise RuntimeError("Asset depositing is not supported by 'NoStorage' objects.")


class LocalStorage(Storage):
    def __init__(self, root):
        self.root = root

    def deposit(self, asset: InternalAsset):
        key = asset.key
        input_path = asset.input_path
        target_path = os.path.join(self.root, key)

        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if asset.file_type == "folder":
            shutil.copytree(input_path, target_path, dirs_exist_ok=True)
        else:
            shutil.copyfile(input_path, target_path)


    def deposit(self, asset):
        raise NotImplementedError


class S3Storage(Storage):
    def deposit(self, asset):
        raise NotImplementedError


def link_asset_folder(url):
    def f(experiment):
        experiment.asset_registry.link_folder(url)

    return ExperimentSetupRoutine(f)


def link_asset_file(url):
    def f(experiment):
        experiment.asset_registry.link_file(url)

    return ExperimentSetupRoutine(f)
