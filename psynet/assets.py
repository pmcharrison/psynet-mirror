import csv
import os
import shutil
import tempfile
import time
import uuid

import postgres_copy
import requests
import sqlalchemy
from dallinger import db
from dallinger.data import copy_db_to_csv
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .data import SQLBase, SQLMixin, register_table
from .timeline import NullElt
from .utils import get_extension


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
    ):
        self.type = type_
        self._type = self.types[type_]
        self.extension = extension if extension else self.get_extension()
        self.description = description
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

    def prepare_for_deployment(self, asset_registry):
        """Runs in advance of the experiment being deployed to the remote server."""
        raise NotImplementedError

    def read_text(self):
        response = requests.get(self.url)
        return response.text


class ExperimentAsset(Asset):
    input_path = Column(String)
    obfuscate = Column(Boolean)
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
        persistent=False,
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
            type_,
            extension,
            description,
            participant_id,
            trial_maker_id,
            network_id,
            node_id,
            trial_id,
        )
        self.size_mb = self.get_size_mb()
        self.key = key

    def get_extension(self):
        return get_extension(self.input_path)

    def deposit(self, asset_registry):
        if self.key is None:
            self.key = self.generate_key()

        time_start = time.perf_counter()
        asset_registry.receive_deposit(asset=self)
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
            if self.description:
                identifiers.append(f"{self.description}")
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

    def prepare_for_deployment(self, asset_registry):
        """Runs in advance of the experiment being deployed to the remote server."""
        self.deposit(asset_registry)


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
    ):
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
        )

    def get_extension(self):
        return get_extension(self.url)

    def prepare_for_deployment(self, asset_registry):
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

    def receive_deposit(self, asset):
        self.load_deployment_key()


class NoStorage(AssetStorage):
    def receive_deposit(self, asset):
        super().receive_deposit(asset)
        raise RuntimeError("Asset depositing is not supported by 'NoStorage' objects.")


class LocalStorage(AssetStorage):
    def __init__(self, root):
        super().__init__()
        self.root = root

    def receive_deposit(self, asset: ExperimentAsset):
        super().receive_deposit(asset)

        key = asset.key
        input_path = asset.input_path

        target_path = os.path.join(self.root, self.deployment_key, key)

        asset.url = os.path.abspath(target_path)

        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if asset.type == "folder":
            shutil.copytree(input_path, target_path, dirs_exist_ok=True)
        else:
            shutil.copyfile(input_path, target_path)


class S3Storage(AssetStorage):
    def receive_deposit(self, asset):
        super().receive_deposit(asset)

        raise NotImplementedError


class AssetRegistry:
    initial_asset_manifesto_path = "pre_deployed_assets.csv"

    def __init__(self, asset_storage: AssetStorage):
        self.asset_storage = asset_storage
        self.staged_assets = {}

        inspector = sqlalchemy.inspect(db.engine)
        if inspector.has_table("asset") and Asset.query.count() == 0:
            self.populate_db_with_initial_assets()

    def stage(self, *args):
        for asset in [*args]:
            assert isinstance(asset, Asset)
            self.staged_assets[asset.key] = asset

    def receive_deposit(self, asset: Asset):
        self.asset_storage.receive_deposit(asset)

    def get(self, key):
        # import pydevd_pycharm
        # pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)
        inspector = sqlalchemy.inspect(db.engine)
        if inspector.has_table("asset") and Asset.query.count() > 0:
            asset = Asset.query.filter_by(key=key).one()
            return asset
        else:
            return self.staged_assets[key]

    def prepare_for_deployment(self):
        self.prepare_assets_for_deployment()
        self.asset_storage.prepare_for_deployment()

    def prepare_assets_for_deployment(self):
        Asset.query.delete()
        for a in self.staged_assets.values():
            a.prepare_for_deployment(asset_registry=self)
            db.session.add(a)
        db.session.commit()
        self.save_initial_asset_manifesto()

    def save_initial_asset_manifesto(self):
        with tempfile.TemporaryDirectory() as tempdir:
            copy_db_to_csv(db.db_url, tempdir)
            shutil.copyfile(
                os.path.join(tempdir, "asset.csv"), self.initial_asset_manifesto_path
            )

    def populate_db_with_initial_assets(self):
        # Patched version of dallinger.data.ingest_to_model
        engine = db.engine
        with open(self.initial_asset_manifesto_path, "r") as file:
            reader = csv.reader(file)
            columns = tuple('"{}"'.format(n) for n in next(reader))
            postgres_copy.copy_from(
                file, Asset, engine, columns=columns, format="csv", HEADER=False
            )
            # Removed because the Asset table doesn't have an autoincrementing id column
            # fix_autoincrement(engine, model.__table__.name)
