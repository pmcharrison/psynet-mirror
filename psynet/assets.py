import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib
import urllib.request
import uuid
from functools import cache, cached_property
from typing import Optional

import boto3
import psutil
import sqlalchemy
from dallinger import db
from joblib import Parallel, delayed
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import backref, relationship
from sqlalchemy.orm.collections import attribute_mapped_collection

from . import __version__ as psynet_version
from .data import (
    SQLBase,
    SQLMixin,
    copy_db_table_to_csv,
    ingest_to_model,
    register_table,
)
from .field import MutableDict, PythonDict, PythonObject
from .media import bucket_exists, create_bucket, get_aws_credentials, make_bucket_public
from .timeline import NullElt
from .utils import (
    cached_class_property,
    get_extension,
    get_function_args,
    get_logger,
    import_local_experiment,
    md5_directory,
    md5_file,
    md5_object,
    run_async_command_locally,
)

logger = get_logger()


class DataType:
    @classmethod
    def get_file_size_mb(cls, path):
        return cls.get_file_size_bytes(path) / (1024 * 1024)

    @classmethod
    def get_file_size_bytes(cls, path):
        raise NotImplementedError


class File(DataType):
    @classmethod
    def get_file_size_bytes(cls, path):
        return os.path.getsize(path)


class Folder(DataType):
    @classmethod
    def get_file_size_bytes(cls, path):
        sum(entry.stat().st_size for entry in os.scandir(path))


class Audio(File):
    pass


class AssetSpecification:
    def __init__(self, key, label):
        if key is None:
            key = f"pending--{uuid.uuid4()}"
        if label is None:
            label = key
        self.key = key
        self.label = label

    def prepare_for_deployment(self, asset_registry):
        raise NotImplementedError

    null_key_pattern = re.compile("^pending--.*")

    @property
    def has_key(self):
        return self.key is not None and not self.null_key_pattern.match(self.key)


class AssetCollection(AssetSpecification):
    pass


class InheritedAssets(AssetCollection):
    def __init__(self, path, key: str):
        super().__init__(key)

        self.path = path

    def prepare_for_deployment(self, asset_registry):
        self.ingest_specification_to_db()

    def ingest_specification_to_db(self):
        with open(self.path, "r") as file:
            ingest_to_model(
                file,
                Asset,
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
    label = Column(String)
    content_id = Column(String)
    host_path = Column(String)
    url = Column(String)
    data_type = Column(String)
    extension = Column(String)
    asset_storage = Column(PythonObject)

    participant_id = Column(Integer, ForeignKey("participant.id"))
    participant = relationship("psynet.participant.Participant", backref="assets")

    trial_maker_id = Column(String)

    network_id = Column(Integer, ForeignKey("network.id"))
    network = relationship("Network", backref="assets")

    node_id = Column(Integer, ForeignKey("node.id"))
    node = relationship(
        "Node",
        backref=backref(
            "assets", collection_class=attribute_mapped_collection("label")
        ),
    )

    trial_id = Column(Integer, ForeignKey("info.id"))
    trial = relationship(
        "Trial",
        backref=backref(
            "assets", collection_class=attribute_mapped_collection("label")
        ),
    )

    foreign_keyed_columns = ["participant_id", "network_id", "node_id", "trial_id"]

    def __init__(
        self,
        key=None,
        label=None,
        data_type="file",
        extension=None,
        trial=None,
        participant=None,
        node=None,
        network=None,
        replace_existing=False,
        variables: Optional[dict] = None,
    ):
        super().__init__(key, label)

        self.psynet_version = psynet_version
        self.replace_existing = replace_existing
        self.data_type = data_type
        self._data_type = self.data_types[data_type]
        self.extension = extension if extension else self.get_extension()

        self.participant = participant
        if participant:
            # I'm not sure this duplication is absolutely necessary but it adds safety
            self.participant_id = participant.id

        self.network = network
        self.node = node
        self.trial = trial

        self.set_trial_maker_id()
        self.set_variables(variables)
        self.infer_missing_parents()

    def set_trial_maker_id(self):
        for obj in [self.trial, self.node, self.network]:
            try:
                self.trial_maker_id = getattr(obj, "trial_maker_id")
                break
            except AttributeError:
                pass

    def set_variables(self, variables):
        if variables:
            for key, value in variables.items():
                self.var.set(key, value)

    def infer_missing_parents(self):
        if self.participant is None and self.trial is not None:
            self.participant = self.trial.participant
        if self.node is None and self.trial is not None:
            self.node = self.trial.origin
        if self.network is None and self.node is not None:
            self.network = self.node.network

    data_types = dict(
        file=File,
        folder=Folder,
        audio=Audio,
    )

    @property
    def identifiers(self):
        attr = [
            "key",
            "data_type",
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
        self.deposit(self.default_asset_storage)
        db.session.commit()

    def deposit(self, asset_storage=None, replace=None, async_: bool = False):
        try:
            if replace is None:
                replace = self.replace_existing

            if asset_storage is None:
                asset_storage = self.default_asset_storage
            self.asset_storage = asset_storage

            self.deployment_id = self.asset_registry.deployment_id
            self.content_id = self.get_content_id()

            if not self.has_key:
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

                self._deposit(self.asset_storage, async_)
                # if deposit_complete:
                #     self.deposited = True

            return asset_to_use

        finally:
            db.session.commit()

    def _deposit(self, asset_storage: "AssetStorage", async_: bool):
        """
        Performs the actual deposit, confident that no duplicates exist.

        Returns
        -------

        Returns ``True`` if the deposit has been completed,
        or ``False`` if the deposit has yet to be completed,
        typically because it is being performed in an asynchronous process
        which will take responsibility for marking the deposit as complete
        in due course.
        """
        raise NotImplementedError

    def download(self, path):
        import pydevd_pycharm

        pydevd_pycharm.settrace(
            "localhost", port=12345, stdoutToServer=True, stderrToServer=True
        )

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

    def export(self, path):
        try:
            self.asset_storage.export(self, path)
        except Exception:
            from .command_line import log

            log(f"Failed to export the asset {self.key} to path {path}.")
            raise

    def receive_stimulus_definition(self, definition):
        self.var.stimulus_definition = definition


class MockAsset(Asset):
    @property
    def url(self):
        return "The asset database has not yet loaded, so here's a placeholder URL."

    def get_extension(self):
        return ""


class ManagedAsset(Asset):
    input_path = Column(String)
    # autogenerate_key = Column(Boolean)
    obfuscate = Column(Integer)
    md5_contents = Column(String)
    size_mb = Column(Float)
    deposit_time_sec = Column(Float)

    def __init__(
        self,
        label,
        input_path,
        data_type="file",
        extension=None,
        trial=None,
        participant=None,
        node=None,
        network=None,
        key=None,
        variables: Optional[dict] = None,
        replace_existing=False,
        obfuscate=1,  # 0: no obfuscation; 1: can't guess URL; 2: can't guess content
    ):
        self.deposited = False
        self.input_path = input_path
        self.obfuscate = obfuscate
        # self.autogenerate_key = key is None
        super().__init__(
            key=key,
            label=label,
            data_type=data_type,
            extension=extension,
            trial=trial,
            participant=participant,
            node=node,
            network=network,
            replace_existing=replace_existing,
            variables=variables,
        )

    def get_content_id(self):
        return self.get_md5_contents()

    def get_md5_contents(self):
        self._get_md5_contents(self.input_path, self.type)

    @cache
    def _get_md5_contents(self, path, data_type):
        f = md5_directory if data_type == "folder" else md5_file
        return f(path)

    def get_extension(self):
        return get_extension(self.input_path)

    def _deposit(self, asset_storage: "AssetStorage", async_: bool):
        super()._deposit(asset_storage, async_)
        self.host_path = self.generate_host_path(self.deployment_id)
        self.url = self.asset_registry.asset_storage.get_url(self.host_path)
        self.asset_storage.update_asset_metadata(self)

        time_start = time.perf_counter()
        self._deposit_(asset_storage, self.host_path, async_)
        time_end = time.perf_counter()

        self.size_mb = self.get_size_mb()
        self.md5_contents = self.get_md5_contents()
        self.deposit_time_sec = (
            time_end - time_start
        )  # Todo - update this - won't be correct for async deposits

    def get_size_mb(self):
        return self._data_type.get_file_size_mb(self.input_path)

    def generate_key(self):
        dir_ = self.generate_dir()
        filename = self.generate_filename()
        return os.path.join(dir_, filename)

    def generate_dir(self):
        dir_ = []
        if self.trial_maker_id:
            dir_.append(str(self.trial_maker_id))
        if self.participant:
            # For some reason, checking for self.participant_id does not always work.
            # It seems that SQLAlchemy's propagation of `participant` to `participant_id`
            # is not fully reliable.
            dir_.append(f"participant_{self.participant.id}")
        return "/".join(dir_)

    def generate_filename(self):
        filename = ""
        identifiers = []
        if self.trial_id:
            identifiers.append(f"trial_{self.trial_id}")
        if self.node_id:
            identifiers.append(f"node_{self.node_id}")
        if self.network_id:
            identifiers.append(f"network_{self.network_id}")
        if self.label:
            identifiers.append(f"{self.label}")

        filename += "__".join(identifiers)
        filename += self.extension
        return filename

    def generate_host_path(self, deployment_id: str):
        raise NotImplementedError

    @staticmethod
    def generate_uuid():
        return str(uuid.uuid4())


class ExperimentAsset(ManagedAsset):
    def _deposit_(self, asset_storage, host_path, async_):
        asset_storage.receive_deposit(self, host_path, async_)

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
            # if self.autogenerate_key:
            #     pass  # autogenerated keys already have a random component, we don't need to add another one
            # else:
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

    @cached_property
    def cache_key(self):
        return self.get_md5_contents()

    def generate_host_path(self, deployment_id: str):
        key = self.key  # e.g. big-audio-file.wav
        cache_key = self.cache_key
        base, extension = os.path.splitext(key)

        if self.obfuscate == 2:
            base = "private"

        host_path = os.path.join("cached", base, cache_key)

        if self.type != "folder":
            host_path += extension

        return host_path

    def generate_dir(self, obfuscate, participant_id, trial_maker_id):
        return os.path.join(
            super().generate_dir(obfuscate, participant_id, trial_maker_id),
            self.compute_hash(),
        )

    def _deposit_(self, asset_storage, host_path, async_):
        if asset_storage.check_cache(host_path, data_type=self.type):
            self.used_cache = True
        else:
            self.used_cache = False
            self._deposit__(asset_storage, host_path, async_)

    def _deposit__(self, asset_storage, host_path, async_):
        asset_storage.receive_deposit(self, host_path, async_)

    def retrieve_contents(self):
        pass


class FunctionAssetMixin:
    # The following conditional logic in the column definitions is required
    # to prevent column conflict errors, see
    # https://docs.sqlalchemy.org/en/13/orm/extensions/declarative/inheritance.html#resolving-column-conflicts
    @declared_attr
    def function(cls):
        return cls.__table__.c.get("function", Column(PythonObject))

    @declared_attr
    def arguments(cls):
        # The MutableDict stuff ensures that in-place edits like ``asset.arguments["x"] = 3`` are tracked properly
        return cls.__table__.c.get(
            "arguments", Column(MutableDict.as_mutable(PythonDict), nullable=True)
        )

    @declared_attr
    def computation_time_sec(cls):
        return cls.__table__.c.get("computation_time_sec", Column(Float))

    def __init__(
        self,
        function,
        key: Optional[str] = None,
        arguments: Optional[dict] = None,
        data_type="file",
        extension=None,
        trial=None,
        participant=None,
        node=None,
        network=None,
        variables: Optional[dict] = None,
        replace_existing=False,
        obfuscate=1,  # 0: no obfuscation; 1: can't guess URL; 2: can't guess content
    ):
        assert callable(function)
        if function.__name__ == "<lambda>":
            raise ValueError(
                "'function' cannot be a lambda function, please provide a named function instead"
            )

        self.function = function
        self.arguments = arguments if arguments else {}
        self.temp_dir = None
        input_path = None
        label = key
        super().__init__(
            label=label,
            input_path=input_path,
            data_type=data_type,
            extension=extension,
            trial=trial,
            participant=participant,
            node=node,
            network=network,
            key=key,
            variables=variables,
            replace_existing=replace_existing,
            obfuscate=obfuscate,
        )

    def __del__(self):
        if hasattr(self, "temp_dir") and self.temp_dir:
            self.temp_dir.cleanup()

    @property
    def instructions(self):
        return dict(function=self.function, arguments=self.arguments)

    def get_md5_instructions(self):
        return md5_object(self.instructions)

    def get_md5_contents(self):
        if self.input_path is None:
            return None
        else:
            return super().get_md5_contents()

    def get_size_mb(self):
        if self.input_path is None:
            return None
        else:
            return super().get_size_mb()

    def _deposit__(self, asset_storage, host_path, async_):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.input_path = os.path.join(
            self.temp_dir.name, "function-output" + self.extension
        )

        time_start = time.perf_counter()
        self.function(path=self.input_path, **self.arguments)
        time_end = time.perf_counter()

        self.md5_contents = self.get_md5_contents()
        self.computation_time_sec = time_end - time_start
        asset_storage.receive_deposit(self, host_path, async_)

    def receive_stimulus_definition(self, definition):
        super().receive_stimulus_definition(definition)
        requested_args = get_function_args(self.function)
        for key, value in definition.items():
            if key in requested_args:
                self.arguments[key] = value


class FunctionAsset(FunctionAssetMixin, ExperimentAsset):
    # FunctionAssetMixin comes first in the inheritance hierarchy
    # because we need to use its ``__init__`` method.
    pass


class CachedFunctionAsset(FunctionAssetMixin, CachedAsset):
    # FunctionAssetMixin comes first in the inheritance hierarchy
    # because we need to use its ``__init__`` method.
    @property
    def cache_key(self):
        return self.get_md5_instructions()


class ExternalAsset(Asset):
    def __init__(
        self,
        key,
        url,
        data_type="file",
        extension=None,
        replace_existing=False,
        label=None,
        participant=None,
        network=None,
        node=None,
        trial=None,
        variables: Optional[dict] = None,
    ):
        self.host_path = url
        self.url = url

        super().__init__(
            key=key,
            label=label,
            data_type=data_type,
            extension=extension,
            trial=trial,
            participant=participant,
            node=node,
            network=network,
            replace_existing=replace_existing,
            variables=variables,
        )

    def get_extension(self):
        return get_extension(self.url)

    def _deposit(self, asset_storage: "AssetStorage", async_: bool):
        pass

    @property
    def identifiers(self):
        return {
            **super().identifiers,
            "url": self.url,
        }

    def get_content_id(self):
        return self.url

    @cached_class_property
    def default_asset_storage(cls):  # noqa
        return WebStorage()


class ExternalS3Asset(ExternalAsset):
    s3_bucket = Column(String)
    s3_key = Column(String)

    def __init__(
        self,
        key,
        s3_bucket: str,
        s3_key: str,
        data_type="file",
        replace_existing=False,
        label=None,
        participant=None,
        network=None,
        node=None,
        trial=None,
        variables: Optional[dict] = None,
    ):
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        url = self.generate_url()

        super().__init__(
            key=key,
            url=url,
            data_type=data_type,
            replace_existing=replace_existing,
            label=label,
            participant=participant,
            network=network,
            node=node,
            trial=trial,
            variables=variables,
        )

    def generate_url(self):
        return f"https://s3.amazonaws.com/{self.s3_bucket}/{self.s3_key}"

    @property
    def identifiers(self):
        return {
            **super().identifiers,
            "s3_bucket": self.s3_bucket,
            "s3_key": self.s3_key,
        }

    @cached_property
    def default_asset_storage(self):  # noqa
        return S3Storage(self.s3_bucket, root="")


class AssetStorage:
    @cached_property
    def deployment_id(self):
        from .experiment import Experiment

        x = Experiment.read_deployment_id()
        if x is None:
            raise Experiment.MissingDeploymentIdError

        return x

    def update_asset_metadata(self, asset: Asset):
        pass

    def receive_deposit(self, asset, host_path: str, async_: bool):
        if async_:
            f = self._async__call_receive_deposit
        else:
            f = self._call_receive_deposit

        f(asset, host_path)

    def _receive_deposit(self, asset: Asset, host_path: str):
        raise NotImplementedError

    def _call_receive_deposit(
        self, asset: Asset, host_path: str, db_commit: bool = False
    ):
        self._receive_deposit(asset, host_path)
        asset.deposited = True
        if db_commit:
            db.session.commit()

    def _async__call_receive_deposit(self, asset: Asset, host_path: str):
        run_async_command_locally(
            self._call_receive_deposit, asset, host_path, db_commit=True
        )

    def export(self, asset, path):
        raise NotImplementedError

    def prepare_for_deployment(self):
        pass

    def get_url(self, host_path: str):
        raise NotImplementedError

    def check_cache(self, host_path: str, data_type: str):
        """
        Checks whether the registry can find an asset cached at ``host_path``.
        The implementation is permitted to make optimizations for speed
        that may result in missed caches, i.e. returning ``False`` when
        the cache did actually exists. However, the implementation should
        only return ``True`` if it is certain that the asset cache exists.

        Returns
        -------

        ``True`` or ``False``.

        """
        raise NotImplementedError


class WebStorage(AssetStorage):
    def export(self, asset, path):
        if asset.type == "folder":
            self.export_folder(asset, path)
        else:
            self.export_file(asset, path)

    def export_folder(self, asset, path):
        with open(path, "w") as f:
            f.write(
                "It is not possible to automatically export ExternalAssets "
                "with type='folder'. This is because the internet provides "
                "no standard way to list the contents of a folder hosted "
                "on an arbitrary web server. You can avoid this issue in the "
                "future by listing each asset as a separate file."
            )

    def export_file(self, asset, path):
        urllib.request.urlretrieve(asset.url, path)


class NoStorage(AssetStorage):
    def _receive_deposit(self, asset, host_path: str):
        raise RuntimeError("Asset depositing is not supported by 'NoStorage' objects.")


class LocalStorage(AssetStorage):
    def __init__(self, root, label: str = "local_storage"):
        """

        Parameters
        ----------
        root :
            Path to the directory to be used for storage.
            Tilde expansion (e.g. '~/psynet') is performed automatically.

        label :
            Label for the storage object.
        """
        super().__init__()
        self.root = os.path.expanduser(root)
        self.label = label
        self.public_path = self.create_public_path()
        self.create_symlink()

    def create_public_path(self):
        """
        This is the publicly exposed path by which the web browser can access the storage registry.
        This corresponds to a (symlinked) directory inside the experiment directory.
        """
        return os.path.join("static", self.label)

    def create_symlink(self):
        try:
            os.unlink(self.public_path)
        except FileNotFoundError:
            pass
        os.makedirs("static", exist_ok=True)
        os.symlink(self.root, self.public_path)

    def update_asset_metadata(self, asset: Asset):
        host_path = asset.host_path
        file_system_path = self.get_file_system_path(host_path)
        asset.var.file_system_path = file_system_path

    def receive_deposit(self, asset: Asset, host_path: str, async_: bool):
        super().receive_deposit(asset, host_path, async_)

        file_system_path = self.get_file_system_path(host_path)
        os.makedirs(os.path.dirname(file_system_path), exist_ok=True)

        self.copy_asset(asset, asset.input_path, file_system_path)
        asset.deposited = True

        # return dict(
        #     url=os.path.abspath(file_system_path),
        # )

    def copy_asset(self, asset, from_, to_):
        if asset.type == "folder":
            shutil.copytree(from_, to_, dirs_exist_ok=True)
        else:
            shutil.copyfile(from_, to_)

    def export(self, asset, path):
        from_ = self.get_file_system_path(asset.host_path)
        to_ = path
        self.copy_asset(asset, from_, to_)

    def get_file_system_path(self, host_path):
        return os.path.join(self.root, host_path)

    def get_url(self, host_path):
        return os.path.join(self.public_path, host_path)

    def check_cache(self, host_path: str, data_type: str):
        file_system_path = self.get_file_system_path(host_path)
        return os.path.exists(file_system_path) and (
            (data_type == "folder" and os.path.isdir(file_system_path))
            or (data_type != "folder" and os.path.isfile(file_system_path))
        )


# def create_bucket_if_necessary(fun):
#     @wraps(fun)
#     def wrapper(self, *args, **kwargs):
#         try:
#             return fun(self, *args, **kwargs)
#         except botocore.exceptions.ClientError as ex:
#             if ex.response["Error"]["Code"] == "NoSuchBucket":
#                 create_bucket(self.s3_bucket)
#                 return fun(self, *args, **kwargs)
#             else:
#                 raise
#
#     return wrapper


@cache
def get_boto3_s3_session():
    return boto3.Session(**get_aws_credentials())


@cache
def get_boto3_s3_client():
    return boto3.client("s3")


@cache
def get_boto3_s3_resource():
    return get_boto3_s3_session().resource("s3")


@cache
def get_boto3_s3_bucket(name):
    return get_boto3_s3_resource().Bucket(name)


def list_files_in_s3_bucket(
    bucket_name: str,
    prefix: str = "",
):
    """
    Lists files in an S3 bucket.

    Parameters
    ----------
    bucket_name :
        Bucket to list files within.

    prefix :
        Only lists files whose keys begin with this string.

    Returns
    -------

    A generator that yields keys.

    """
    logger.info(
        "Listing files in S3 bucket %s with prefix '%s'...", bucket_name, prefix
    )
    paginator = get_boto3_s3_client().get_paginator("list_objects_v2")

    return list(
        [
            content["Key"]
            for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix)
            for content in page.get("Contents", ())
        ]
    )


@cache
def list_files_in_s3_bucket__cached(*args, **kwargs):
    return list_files_in_s3_bucket(*args, **kwargs)


class S3Storage(AssetStorage):
    def __init__(self, s3_bucket, root):
        super().__init__()
        assert not root.endswith("/")
        self.s3_bucket = s3_bucket
        self.root = root

    def prepare_for_deployment(self):
        if not bucket_exists(self.s3_bucket):
            create_bucket(self.s3_bucket)
        make_bucket_public(self.s3_bucket)

    def _receive_deposit(self, asset, host_path):
        target_path = os.path.join(self.root, host_path)
        recursive = asset.type == "folder"
        self.upload(asset.input_path, target_path, recursive)

        # return dict(
        #     url=self.get_url(host_path),
        # )

    def get_url(self, host_path: str):
        s3_key = os.path.join(self.root, host_path)
        return os.path.join(
            "https://s3.amazonaws.com", self.s3_bucket, self.escape_s3_key(s3_key)
        )

    def escape_s3_key(self, s3_key):
        # This might need revisiting as and when we find special characters that aren't quoted correctly
        return urllib.parse.quote_plus(s3_key, safe="/~()*!.'")

    # @create_bucket_if_necessary
    def check_cache(self, host_path: str, data_type: str):
        s3_key = os.path.join(self.root, host_path)
        if data_type == "folder":
            return self.check_cache_folder(s3_key)
        else:
            return self.check_cache_file(s3_key)

    def check_cache_file(self, s3_key):
        # from .command_line import FLAGS
        return self._check_cache_file__preparation_phase(s3_key)
        # if "PREPARE" in FLAGS:
        #     return self._check_cache_file__preparation_phase(s3_key)
        # else:
        #     assert False
        #     return self._check_cache__deployed_phase(s3_key)

    def _check_cache_file__preparation_phase(self, s3_key):
        # If we are in the 'preparation' phase of deployment, then we rely on a cached listing
        # of the files in the S3 bucket. This is necessary because the preparation phase
        # may involve checking caches for thousands of files at a time, and it would be slow
        # to talk to S3 separately for each one. This wouldn't catch situations where
        # the cache has been added during the preparation phase itself, but this shouldn't happen very often,
        # so doesn't need to be optimized for just yet.
        # import pydevd_pycharm
        # pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)
        return s3_key in list_files_in_s3_bucket__cached(
            self.s3_bucket, prefix=self.root + "/"
        )

    def _check_cache__deployed_phase(self, s3_key):
        # If we are in the 'deployed' phase of the experiment, then we don't use a cache,
        # and instead talk to the S3 server directly. This is important because we want
        # we wouldn't be uploading many assests at the same time at this point;
        # it is desirable because we want to be able to have a dynamic cache during this phase.
        candidates = get_boto3_s3_bucket(self.s3_bucket).objects.filter(Prefix=s3_key)
        if any([x.key == s3_key for x in candidates]):
            return True
        return False

    # @create_bucket_if_necessary
    def folder_exists__slow(self, s3_key):
        return len(self.list_folder(s3_key)) > 0

    # @create_bucket_if_necessary
    def list_folder(self, folder):
        # cmd = f"aws s3 ls {s3_bucket}/{folder}/"
        # from subprocess import PIPE
        # credentials = psynet.media.get_aws_credentials()
        # cmd = ""
        # cmd += f"export AWS_ACCESS_KEY_ID={credentials['aws_access_key_id']}; "
        # cmd += f"export AWS_SECRET_ACCESS_KEY={credentials['aws_secret_access_key']}; "
        # cmd += f"aws s3 ls {s3_bucket} "
        # x = subprocess.run(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
        # breakpoint()
        return [x.key for x in self.boto3_bucket.objects.filter(Prefix="folder" + "/")]

    @cached_property
    def regex_pattern(self):
        return re.compile("https://s3.amazonaws.com/(.*)/(.*)")

    def export(self, asset, path):
        url = asset.url
        bucket, s3_key = re.match(self.regex_pattern, url)

        if bucket != self.s3_bucket:
            raise ValueError(
                f"The provided URL ({url}) seems inconsistent with the provided S3 bucket name ({self.s3_bucket})."
            )

        recursive = asset.type == "folder"
        self.download(s3_key, path, recursive=recursive)

    def download(self, s3_key, target_path, recursive):
        """
        This function relies on the AWS CLI. You can install it with pip install awscli.
        """
        url = f"s3://{self.s3_bucket}/{s3_key}"
        cmd = ["aws", "s3", "cp", url, target_path]

        if recursive:
            cmd.append("--recursive")

        logger.info(f"Downloading from AWS with command: {cmd}")

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as err:
            logger.error(f"{err} {err.stderr.decode('utf8')}")
            raise

    # @create_bucket_if_necessary
    def upload(self, input_path, s3_key, recursive):
        """
        This function relies on the AWS CLI. You can install it with pip install awscli.
        """
        url = f"s3://{self.s3_bucket}/{s3_key}"
        cmd = ["aws", "s3", "cp", input_path, url]

        if recursive:
            cmd.append("--recursive")

        logger.info(f"Uploading to AWS with command: {cmd}")

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as err:
            logger.error(f"{err} {err.stderr.decode('utf8')}")
            raise


class AssetRegistry:
    initial_asset_manifesto_path = "pre_deployed_assets.csv"

    def __init__(self, asset_storage: AssetStorage, n_parallel=None):
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

    def update_asset_metadata(self, asset: Asset):
        pass

    def receive_deposit(self, asset: Asset, host_path: str, async_: bool):
        return self.asset_storage.receive_deposit(asset, host_path, async_)

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
        if self.n_parallel:
            n_jobs = self.n_parallel
        elif len(self._staged_asset_specifications) < 25:
            n_jobs = 1
        else:
            n_jobs = psutil.cpu_count()

        logger.info("Preparing assets for deployment...")
        Parallel(n_jobs=n_jobs, verbose=10)(
            delayed(lambda a: a.prepare_for_deployment(asset_registry=self))(a)
            for a in self._staged_asset_specifications
        )

        db.session.commit()
        self.save_initial_asset_manifesto()

    def save_initial_asset_manifesto(self):
        copy_db_table_to_csv("asset", self.initial_asset_manifesto_path)

    def populate_db_with_initial_assets(self):
        with open(self.initial_asset_manifesto_path, "r") as file:
            ingest_to_model(file, Asset)
