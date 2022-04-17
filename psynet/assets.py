import os
import shutil
import tempfile
import time
import uuid
from functools import cached_property, lru_cache
from typing import Optional

import sqlalchemy
from dallinger import db
from dallinger.data import copy_db_to_csv
from joblib import Parallel, delayed
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from . import __version__ as psynet_version
from .data import SQLBase, SQLMixin, import_csv_to_db, register_table
from .timeline import NullElt
from .utils import (
    cached_class_property,
    get_extension,
    import_local_experiment,
    md5_directory,
    md5_file,
)


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
    def __init__(self, key):
        self.key = key

    def prepare_for_deployment(self, asset_registry):
        raise NotImplementedError


class AssetCollection(AssetSpecification):
    pass


class InheritedAssets(AssetCollection):
    def __init__(self, path, key: str):
        super().__init__(key)

        self.path = path

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
class Asset(AssetSpecification, SQLBase, SQLMixin, NullElt):
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
    deposited = Column(Boolean)
    inherited = Column(Boolean, default=False)
    inherited_from = Column(String)
    key = Column(String, primary_key=True, index=True)
    content_id = Column(String)
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
        key=None,
        type_="file",
        extension=None,
        replace_existing=False,
        description=None,
        participant_id=None,
        trial_maker_id=None,
        network_id=None,
        node_id=None,
        trial_id=None,
        variables: Optional[dict] = None,
    ):
        super().__init__(key)
        self.psynet_version = psynet_version
        self.replace_existing = replace_existing
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

    @property
    def identifiers(self):
        attr = [
            "key",
            "type",
            "extension",
            "participant_id",
            "trial_maker_id",
            "network_id",
            "node_id",
            "trial_id",
        ]
        return {a: getattr(self, a) for a in attr}

    def get_extension(self):
        raise NotImplementedError

    def prepare_for_deployment(self, asset_registry):
        """Runs in advance of the experiment being deployed to the remote server."""
        self.deposit(asset_registry.asset_storage)
        db.session.commit()

    def deposit(self, asset_storage=None, replace=None):
        try:
            if replace is None:
                replace = self.replace_existing

            if asset_storage is None:
                asset_storage = self.default_asset_storage

            self.deployment_id = self.asset_registry.deployment_id
            self.content_id = self.get_content_id()

            if self.key is None:
                self.key = self.generate_key()

            asset_to_use = self
            duplicate = self.find_duplicate()

            if duplicate:
                try:
                    self.assert_assets_are_equivalent(self, duplicate)
                    asset_to_use = duplicate
                except self.InconsistentAssetsError:
                    if replace:
                        db.session.delete(duplicate)
                        asset_to_use = self
                    else:
                        raise

            if asset_to_use == self:
                db.session.add(self)

                self._deposit(asset_storage)
                self.deposited = True

            return asset_to_use

        finally:
            db.session.commit()

    def _deposit(self, asset_storage):
        """Performs the actual deposit, confident that no duplicates exist."""
        pass

    def find_duplicate(self):
        return Asset.query.filter_by(key=self.key).one_or_none()

    class InconsistentAssetsError(AssertionError):
        pass

    class InconsistentIdentifiersError(InconsistentAssetsError):
        pass

    class InconsistentContentError(InconsistentAssetsError):
        pass

    @classmethod
    def assert_assets_are_equivalent(cls, old, new):
        cls.assert_identifiers_are_equivalent(old, new)
        cls.assert_content_ids_are_equivalent(old, new)

    @classmethod
    def assert_identifiers_are_equivalent(cls, old, new):
        _old = old.identifiers
        _new = new.identifiers
        if _old != _new:
            raise cls.InconsistentIdentifiersError(
                f"Tried to add duplicate assets with the same key ({old.key}, "
                "but they had inconsistent identifiers.\n"
                f"\nOld asset: {old.identifiers}\n"
                f"\nNew asset: {new.identifiers}"
            )

    @classmethod
    def assert_content_ids_are_equivalent(cls, old, new):
        _old = old.content_id
        _new = new.content_id

        if old != new:
            raise cls.InconsistentContentError(
                f"Initiated a new deposit for pre-existing asset ({new.key}), "
                "but replace=False and the content IDs did not match "
                f"(old: {_old}, new: {_new}), implying that their content differs."
            )

    def get_content_id(self):
        raise NotImplementedError

    def generate_host_path(self, deployment_id: str):
        raise NotImplementedError

    @cached_class_property
    def experiment_class(cls):  # noqa
        return import_local_experiment()["class"]

    @cached_class_property
    def asset_registry(cls):  # noqa
        return cls.experiment_class.assets

    @cached_class_property
    def default_asset_storage(cls):  # noqa
        return cls.asset_registry.asset_storage


class MockAsset(Asset):
    @property
    def url(self):
        return "The asset database has not yet loaded, so here's a placeholder URL."

    def get_extension(self):
        return ""


class ManagedAsset(Asset):
    input_path = Column(String)
    autogenerate_key = Column(Boolean)
    obfuscate = Column(Integer)
    md5 = Column(String)
    size_mb = Column(Float)
    deposit_time_sec = Column(Float)

    def __init__(
        self,
        input_path,
        key=None,
        type_="file",
        extension=None,
        replace_existing=False,
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
            key,
            type_,
            extension,
            replace_existing,
            description,
            participant_id,
            trial_maker_id,
            network_id,
            node_id,
            trial_id,
            variables,
        )
        self.size_mb = self.get_size_mb()
        self.autogenerate_key = key is None

    def get_content_id(self):
        return self.get_md5()

    def get_extension(self):
        return get_extension(self.input_path)

    def _deposit(self, asset_storage):
        super()._deposit(asset_storage)
        self.host_path = self.generate_host_path(self.deployment_id)
        self.url = self.asset_registry.asset_storage.get_url(self.host_path)
        self.md5 = self.get_md5()

        time_start = time.perf_counter()
        self._deposit_(asset_storage, self.host_path)
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
        return f(self.input_path)


class ExperimentAsset(ManagedAsset):
    def _deposit_(self, asset_storage, host_path):
        asset_storage.receive_deposit(self, host_path)

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

    def _deposit_(self, asset_storage, host_path):
        if asset_storage.asset_exists(host_path, type_=self.type):
            self.used_cache = True
        else:
            self.used_cache = False
            asset_storage.receive_deposit(self, host_path)


class ExternalAsset(Asset):
    def __init__(
        self,
        url,
        key,
        type_="file",
        replace_existing=False,
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
        super().__init__(
            key,
            type_,
            replace_existing,
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

    def _deposit(self, asset_storage):
        pass

    @property
    def identifiers(self):
        return {
            **super().identifiers,
            "url": self.url,
        }

    def get_content_id(self):
        return self.url


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
        super().receive_deposit(asset, host_path)
        raise NotImplementedError

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
