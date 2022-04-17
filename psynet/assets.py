import os
import shutil
import tempfile
import time
import uuid
from functools import cached_property, lru_cache
from typing import Optional

import requests
import sqlalchemy
from dallinger import db
from dallinger.data import copy_db_to_csv
from joblib import Parallel, delayed
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from . import __version__ as psynet_version
from .data import SQLBase, SQLMixin, import_csv_to_db, register_table
from .timeline import NullElt
from .utils import get_extension, import_local_experiment, md5_directory, md5_file


class AssetType:
    @classmethod
    def get_file_size_mb(cls, path):
        return cls.get_file_size_bytes(path) / (1024 * 1024)

    @classmethod
    def get_file_size_bytes(cls, path):
        raise NotImplementedError


class File(AssetType):
    @classmethod
    def get_file_size_bytes(cls, path):
        return os.path.getsize(path)


class Folder(AssetType):
    @classmethod
    def get_file_size_bytes(cls, path):
        sum(entry.stat().st_size for entry in os.scandir(path))


class Audio(File):
    pass


class AssetSpecification:
    def prepare_for_deployment(self, asset_registry):
        raise NotImplementedError


class AssetCollection(AssetSpecification):
    pass


class InheritedAssets(AssetCollection):
    def __init__(self, path, key: str):
        self.path = path
        self.key = key

    def prepare_for_deployment(self, asset_registry):
        self.ingest_specification_to_db()

    def ingest_specification_to_db(self):
        import_csv_to_db(
            self.path,
            Asset,
            fix_id_col=False,
            clear_columns=Asset.foreign_keyed_columns,
            replace_columns=dict(
                inherited=True,
                inherited_from=self.key,
            ),
        )


@register_table
class Asset(SQLBase, SQLMixin, AssetSpecification, NullElt):
    # Inheriting from SQLBase and SQLMixin means that the Asset object is stored in the database.
    # Inheriting from NullElt means that the Asset object can be placed in the timeline.

    __tablename__ = "asset"

    # Remove default SQL columns
    id = None
    failed = None
    failed_reason = None
    time_of_death = None

    psynet_version = Column(String)
    deployment_id = Column(String)
    inherited = Column(Boolean, default=False)
    inherited_from = Column(String)
    key = Column(String, primary_key=True, index=True)
    md5 = Column(String)
    host_path = Column(String)
    url = Column(String)
    type = Column(String)
    extension = Column(String)
    description = Column(String)

    participant_id = Column(Integer, ForeignKey("participant.id"))
    participant = relationship("psynet.participant.Participant", backref="assets")

    trial_maker_id = Column(String)

    network_id = Column(Integer, ForeignKey("network.id"))
    network = relationship("Network", backref="assets")

    node_id = Column(Integer, ForeignKey("node.id"))
    node = relationship("Node", backref="assets")

    trial_id = Column(Integer, ForeignKey("info.id"))
    trial = relationship("Trial", backref="assets")

    foreign_keyed_columns = ["participant_id", "network_id", "node_id", "trial_id"]

    def __init__(
        self,
        type_="file",
        extension=None,
        description=None,
        participant_id=None,
        trial_maker_id=None,
        network_id=None,
        node_id=None,
        trial_id=None,
        variables: Optional[dict] = None,
    ):
        self.psynet_version = psynet_version
        self.type = type_
        self._type = self.types[type_]
        self.extension = extension if extension else self.get_extension()
        self.description = description
        self.participant_id = participant_id
        self.trial_maker_id = trial_maker_id
        self.network_id = network_id
        self.node_id = node_id
        self.trial_id = trial_id

        if variables:
            for key, value in variables.items():
                self.var.set(key, value)

    types = dict(
        file=File,
        folder=Folder,
        audio=Audio,
    )

    def get_extension(self):
        raise NotImplementedError

    def prepare_for_deployment(self, asset_registry):
        """Runs in advance of the experiment being deployed to the remote server."""
        self.register(asset_registry)

    def register(self, asset_registry):
        """Registers the asset as long as no duplicates are found."""
        self.deployment_id = asset_registry.deployment_id

        if self.key is None:
            self.key = self.generate_key()

        duplicate = self.find_duplicate()
        if duplicate:
            if duplicate.get_comparison_key() == self.get_comparison_key():
                pass
            else:
                raise DuplicateKeyError(self, duplicate)
        else:
            self._register(asset_registry)
            db.session.add(self)
            db.session.commit()

    def _register(self, asset_registry):
        """Performs the actual registration, confident that no duplicates exist."""
        raise NotImplementedError

    def find_duplicate(self):
        import pydevd_pycharm

        pydevd_pycharm.settrace(
            "localhost", port=12345, stdoutToServer=True, stderrToServer=True
        )
        return Asset.query.filter_by(key=self.key).one_or_none()

    def read_text(self):
        response = requests.get(self.url)
        return response.text

    def generate_host_path(self, deployment_id: str):
        raise NotImplementedError


class MockAsset(Asset):
    @property
    def url(self):
        return "The asset database has not yet loaded, so here's a placeholder URL."


class DuplicateKeyError(KeyError):
    """Raised when trying to add two assets with the same key."""

    def __init__(self, obj1, obj2):
        comparison_key_1 = obj1.get_comparison_key()
        comparison_key_2 = obj2.get_comparison_key()
        message = (
            f"Tried to deposit an asset with a key of {self.key}, "
            "but there already exists such an asset in the database, "
            "and their contents do not match "
            f"('{comparison_key_1}' != '{comparison_key_2}')."
        )
        super().__init__(message)


class ManagedAsset(Asset):
    input_path = Column(String)
    autogenerate_key = Column(Boolean)
    obfuscate = Column(Integer)
    deposited = Column(Boolean)
    size_mb = Column(Float)
    deposit_time_sec = Column(Float)

    def __init__(
        self,
        input_path,
        key=None,
        type_="file",
        extension=None,
        description=None,
        obfuscate=1,  # 0: no obfuscation; 1: can't guess URL; 2: can't guess content
        participant_id=None,
        trial_maker_id=None,
        network_id=None,
        node_id=None,
        trial_id=None,
        variables: Optional[dict] = None,
    ):
        self.deposited = False
        self.input_path = input_path
        self.obfuscate = obfuscate
        super().__init__(
            type_,
            extension,
            description,
            participant_id,
            trial_maker_id,
            network_id,
            node_id,
            trial_id,
            variables,
        )
        self.size_mb = self.get_size_mb()

        self.key = key
        self.autogenerate_key = key is None

    def get_extension(self):
        return get_extension(self.input_path)

    def prepare_for_deployment(self, asset_registry):
        """Runs in advance of the experiment being deployed to the remote server."""
        super().prepare_for_deployment(asset_registry)
        storage = asset_registry.asset_storage
        self.deposit(storage)
        db.session.commit()

    def _register(self, asset_registry=None):
        super()._register(asset_registry)
        self.deposit(asset_registry.asset_storage)

    def deposit(self, asset_storage=None):
        if not asset_storage:
            asset_storage = import_local_experiment()["class"].assets.asset_storage

        self.deployment_id = asset_storage.deployment_id
        self.host_path = self.generate_host_path(self.deployment_id)

        self.ensure_deposited(asset_storage, self.host_path)
        self.deposited = True
        self.url = asset_storage.get_url(self.host_path)

        db.session.add(self)
        db.session.commit()

    def ensure_deposited(self, asset_storage, host_path):
        raise NotImplementedError

    def get_comparison_key(self):
        return self.get_md5()

    def _deposit(self, asset_storage, host_path):
        time_start = time.perf_counter()
        asset_storage.receive_deposit(self, host_path)
        time_end = time.perf_counter()

        self.deposit_time_sec = time_end - time_start

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
        identifiers = []
        if self.description:
            identifiers.append(f"{self.description}")
        if self.network_id:
            identifiers.append(f"network={self.network_id}")
        if self.node_id:
            identifiers.append(f"node={self.node_id}")
        if self.trial_id:
            identifiers.append(f"trial={self.trial_id}")
        identifiers.append(self.generate_uuid())  # ensures uniqueness
        filename += "__".join(identifiers)
        filename += self.extension
        return filename

    def generate_host_path(self, deployment_id: str):
        raise NotImplementedError

    @staticmethod
    def generate_uuid():
        return str(uuid.uuid4())

    @lru_cache()
    def get_md5(self):
        f = md5_directory if self.type == "folder" else md5_file
        self.md5 = f(self.input_path)
        return self.md5


class ExperimentAsset(ManagedAsset):
    def ensure_deposited(self, asset_storage, host_path):
        self._deposit(asset_storage, host_path)

    def generate_host_path(self, deployment_id: str):
        obfuscated = self.obfuscate_key(self.key)
        return os.path.join("experiments", deployment_id, obfuscated)

    def obfuscate_key(self, key):
        random = self.generate_uuid()

        if self.type == "folder":
            base = key
            extension = None
        else:
            base, extension = os.path.splitext(key)

        if self.obfuscate == 0:
            return key
        elif self.obfuscate == 1:
            if self.autogenerate_key:
                pass  # autogenerated keys already have a random component, we don't need to add another one
            else:
                base += "__" + random
        elif self.obfuscate == 2:
            base = "private/" + random
        else:
            raise ValueError(f"Invalid value of obfuscate: {self.obfuscate}")

        if self.type == "folder":
            return base
        else:
            return base + extension


class CachedAsset(ManagedAsset):
    used_cache = Column(Boolean)

    def generate_host_path(self, deployment_id: str):
        key = self.key  # e.g. big-audio-file.wav
        md5 = self.get_md5()
        base, extension = os.path.splitext(key)

        if self.obfuscate == 2:
            base = "private"

        host_path = os.path.join("cached", base, md5)

        if self.type != "folder":
            host_path += extension

        return host_path

    def generate_dir(self):
        return os.path.join(super().generate_dir(), self.compute_hash())

    def ensure_deposited(self, asset_storage, host_path):
        if asset_storage.asset_exists(host_path, type_=self.type):
            self.used_cache = True
        else:
            self.used_cache = False
            self._deposit(asset_storage, host_path)


class ExternalAsset(Asset):
    def __init__(
        self,
        url,
        key,
        type_="file",
        description=None,
        participant_id=None,
        trial_maker_id=None,
        network_id=None,
        node_id=None,
        trial_id=None,
        variables: Optional[dict] = None,
    ):
        self.host_path = url
        self.url = url
        self.key = key
        super().__init__(
            type_,
            description,
            participant_id,
            trial_maker_id,
            network_id,
            node_id,
            trial_id,
            variables,
        )

    def get_extension(self):
        return get_extension(self.url)

    def get_comparison_key(self):
        return self.url

    def _register(self, asset_registry):
        pass


class AssetStorage:
    @cached_property
    def deployment_id(self):
        from .experiment import Experiment

        x = Experiment.read_deployment_id()
        if x is None:
            raise Experiment.MissingDeploymentIdError

        return x

    def receive_deposit(self, asset, host_path: str):
        pass

    def prepare_for_deployment(self):
        pass

    def get_url(self, host_path: str):
        raise NotImplementedError

    def asset_exists(self, host_path: str, type_: str):
        raise NotImplementedError


class NoStorage(AssetStorage):
    def receive_deposit(self, asset, host_path: str):
        super().receive_deposit(asset, host_path)
        raise RuntimeError("Asset depositing is not supported by 'NoStorage' objects.")


class LocalStorage(AssetStorage):
    def __init__(self, root):
        super().__init__()
        self.root = root

    def receive_deposit(self, asset: ExperimentAsset, host_path: str):
        super().receive_deposit(asset, host_path)

        file_system_path = self.get_file_system_path(host_path)
        os.makedirs(os.path.dirname(file_system_path), exist_ok=True)

        if asset.type == "folder":
            shutil.copytree(asset.input_path, file_system_path, dirs_exist_ok=True)
        else:
            shutil.copyfile(asset.input_path, file_system_path)

        return dict(
            url=os.path.abspath(file_system_path),
        )

    def get_file_system_path(self, host_path):
        return os.path.join(self.root, host_path)

    def get_url(self, host_path):
        return os.path.abspath(self.get_file_system_path(host_path))

    def asset_exists(self, host_path: str, type_: str):
        file_system_path = self.get_file_system_path(host_path)
        return os.path.exists(file_system_path) and (
            (type_ == "folder" and os.path.isdir(file_system_path))
            or (type_ != "folder" and os.path.isfile(file_system_path))
        )


class S3Storage(AssetStorage):
    def receive_deposit(self, asset, host_path):
        raise NotImplementedError
        return super().receive_deposit(asset, host_path)

    def get_url(self, host_path):
        raise NotImplementedError

    def asset_exists(self, host_path: str, type_: str):
        raise NotImplementedError


class AssetRegistry:
    initial_asset_manifesto_path = "pre_deployed_assets.csv"

    def __init__(self, asset_storage: AssetStorage, n_parallel=1):
        self.asset_storage = asset_storage
        self.n_parallel = n_parallel
        self._staged_asset_specifications = []
        self._staged_asset_lookup_table = {}

        inspector = sqlalchemy.inspect(db.engine)
        if inspector.has_table("asset") and Asset.query.count() == 0:
            self.populate_db_with_initial_assets()

    @property
    def deployment_id(self):
        return self.asset_storage.deployment_id

    def stage(self, *args):
        for asset in [*args]:
            assert isinstance(asset, AssetSpecification)
            self._staged_asset_specifications.append(asset)
            self._staged_asset_lookup_table[asset.key] = asset

    def receive_deposit(self, asset: Asset, host_path: str):
        return self.asset_storage.receive_deposit(asset, host_path)

    def get(self, key):
        # When the experiment is running then we can get the assets from the database.
        # However, if we want them before the experiment has been launched,
        # we have to get them from their staging location.
        inspector = sqlalchemy.inspect(db.engine)
        if inspector.has_table("asset") and Asset.query.count() > 0:
            asset = Asset.query.filter_by(key=key).one()
            return asset
        else:
            try:
                return self._staged_asset_lookup_table[key]
            except KeyError:
                # Sometimes an asset won't be available during staging (e.g. if the experimenter
                # is using the InheritedAssets functionality. To prevent the experiment
                # from failing to compile, we therefore return a mock asset.
                return MockAsset()

    def prepare_for_deployment(self):
        self.prepare_assets_for_deployment()
        self.asset_storage.prepare_for_deployment()

    def prepare_assets_for_deployment(self):
        Asset.query.delete()

        Parallel(n_jobs=self.n_parallel, verbose=10)(
            delayed(lambda a: a.prepare_for_deployment(asset_registry=self))(a)
            for a in self._staged_asset_specifications
        )

        db.session.commit()
        self.save_initial_asset_manifesto()

    def save_initial_asset_manifesto(self):
        with tempfile.TemporaryDirectory() as tempdir:
            copy_db_to_csv(db.db_url, tempdir)
            shutil.copyfile(
                os.path.join(tempdir, "asset.csv"), self.initial_asset_manifesto_path
            )

    def populate_db_with_initial_assets(self):
        # Asset doesn't have an ID column to fix
        import_csv_to_db(self.initial_asset_manifesto_path, Asset, fix_id_col=False)
