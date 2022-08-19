import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib
import urllib.request
import uuid
from functools import cached_property
from typing import Optional

import boto3
import psutil
import requests
import sqlalchemy
from dallinger import db
from joblib import Parallel, delayed
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, select
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import column_property, relationship

from .data import SQLBase, SQLMixin, ingest_to_model, register_table
from .field import PythonDict, PythonObject, register_extra_var
from .media import get_aws_credentials
from .process import AsyncProcess, LocalAsyncProcess
from .timeline import NullElt
from .utils import (
    cache,
    cached_class_property,
    get_args,
    get_extension,
    get_file_size_mb,
    get_folder_size_mb,
    get_logger,
    md5_directory,
    md5_file,
    md5_object,
)

logger = get_logger()


def _get_experiment_if_available():
    from .utils import disable_logger

    try:
        with disable_logger():
            # This is to suppress Dallinger's 'Error retrieving experiment class' messages
            from .experiment import get_experiment

            return get_experiment()
    except ImportError:
        return None


class AssetSpecification(NullElt):
    def __init__(self, key, label, description):
        if key is None:
            key = f"pending--{uuid.uuid4()}"
        self.key = key
        self.label = label
        self.description = description

    def prepare_for_deployment(self, registry):
        raise NotImplementedError

    null_key_pattern = re.compile("^pending--.*")

    @property
    def has_key(self):
        return self.key is not None and not self.null_key_pattern.match(self.key)


class AssetCollection(AssetSpecification):
    pass


class InheritedAssets(AssetCollection):
    def __init__(self, path, key: str):
        super().__init__(key, label=None, description=None)

        self.path = path

    def prepare_for_deployment(self, registry):
        self.ingest_specification_to_db()

    def ingest_specification_to_db(self):
        clear_columns = Asset.foreign_keyed_columns + ["parent"]
        with open(self.path, "r") as file:
            ingest_to_model(
                file,
                Asset,
                clear_columns=clear_columns,
                replace_columns=dict(
                    inherited=True,
                    inherited_from=self.key,
                ),
            )


def get_asset(key):
    from .experiment import is_experiment_launched

    if not is_experiment_launched():
        raise RuntimeError(
            "You can't call get_asset before the experiment is launched. "
            "The usual solution is to wrap this code in a PageMaker or a CodeBlock."
        )

    matches = Asset.query.filter_by(key=key).all()
    if len(matches) == 0:
        raise KeyError
    elif len(matches) == 1:
        return matches[0]
    else:
        raise ValueError(
            f"Unexpected number of assets found with key = {key} ({len(matches)})"
        )


@register_table
class Asset(AssetSpecification, SQLBase, SQLMixin):
    # Inheriting from SQLBase and SQLMixin means that the Asset object is stored in the database.
    # Inheriting from NullElt means that the Asset object can be placed in the timeline.

    __tablename__ = "asset"
    __extra_vars__ = {}

    # Remove default SQL columns
    id = None
    failed = None
    failed_reason = None
    time_of_death = None

    needs_storage_backend = True

    psynet_version = Column(String)
    deployment_id = Column(String)
    deposited = Column(Boolean)
    inherited = Column(Boolean, default=False)
    inherited_from = Column(String)
    key = Column(String, primary_key=True, index=True)
    label = Column(String)
    parent = Column(PythonObject)
    description = Column(String)
    personal = Column(Boolean)
    content_id = Column(String)
    host_path = Column(String)
    url = Column(String)
    is_folder = Column(Boolean)
    data_type = Column(String)
    extension = Column(String)
    storage = Column(PythonObject)
    replace_existing = Column(Boolean)

    # participant_id = Column(Integer, ForeignKey("participant.id"))
    # participant = relationship(
    #     "psynet.participant.Participant", back_populates="assets"
    # )
    #
    # trial_maker_id = Column(String)
    #
    # network_id = Column(Integer, ForeignKey("network.id"))
    # network = relationship("TrialNetwork")
    #
    # node_id = Column(Integer, ForeignKey("node.id"))
    # node = relationship(
    #     "TrialNode"
    # )
    #
    # trial_id = Column(Integer, ForeignKey("info.id"))
    # trial = relationship(
    #     "Trial"
    # )  # We don't use automatic back_populates functionality, but write our own
    #
    # response_id = Column(Integer, ForeignKey("response.id"))
    # response = relationship("psynet.timeline.Response", back_populates="assets")

    # @property
    # def label_or_key(self):
    #     if self.label is not None:
    #         return self.label
    #     return self.key

    async_processes = relationship("AsyncProcess")
    awaiting_async_process = column_property(
        select(AsyncProcess)
        .where(AsyncProcess.asset_key == key, AsyncProcess.pending)
        .exists()
    )
    register_extra_var(__extra_vars__, "awaiting_async_process")

    participant_links = relationship(
        "AssetParticipant", order_by="AssetParticipant.creation_time"
    )
    participants = association_proxy("participant_links", "participant")

    trial_links = relationship("AssetTrial", order_by="AssetTrial.creation_time")
    trials = association_proxy("trial_links", "trial")

    node_links = relationship("AssetNode", order_by="AssetNode.creation_time")
    nodes = association_proxy("node_links", "node")

    network_links = relationship("AssetNetwork", order_by="AssetNetwork.creation_time")
    networks = association_proxy("network_links", "network")

    errors = relationship("ErrorRecord")

    # foreign_keyed_columns = [
    #     "participant_id",
    #     "network_id",
    #     "node_id",
    #     "trial_id",
    #     "response_id",
    # ]

    def __init__(
        self,
        key=None,
        label=None,
        description=None,
        is_folder=False,
        data_type=None,
        extension=None,
        parent=None,
        replace_existing=False,
        variables: Optional[dict] = None,
        personal=False,
    ):
        super().__init__(key, label, description)

        from . import __version__ as psynet_version

        self.psynet_version = psynet_version
        self.replace_existing = replace_existing
        self.is_folder = is_folder

        self.extension = extension if extension else self.get_extension()

        if data_type is None:
            data_type = self.infer_data_type()

        self.data_type = data_type
        self.parent = parent

        self.set_variables(variables)
        self.personal = personal

    def consume(self, experiment, participant):
        if not self.has_key:
            self.key = self.generate_key()
        try:
            experiment.assets.get(self.key)
        except KeyError:
            self.deposit()

    def infer_data_type(self):
        if self.extension in ["wav", "mp3"]:
            return "audio"
        elif self.extension in ["mp4", "avi"]:
            return "video"
        else:
            return None

    @property
    def trial_maker(self):
        from psynet.experiment import get_trial_maker

        return get_trial_maker(self.trial_maker_id)

    def set_variables(self, variables):
        if variables:
            for key, value in variables.items():
                self.var.set(key, value)

    # @property
    # def identifiers(self):
    #     attr = [
    #         "key",
    #         "is_folder",
    #         "data_type",
    #         "extension",
    #         "participant_id",
    #         "trial_maker_id",
    #         "network_id",
    #         "node_id",
    #         "trial_id",
    #     ]
    #     return {a: getattr(self, a) for a in attr}

    def get_extension(self):
        raise NotImplementedError

    def prepare_for_deployment(self, registry):
        """Runs in advance of the experiment being deployed to the remote server."""
        self.deposit(self.default_storage)
        db.session.commit()

    def deposit(
        self,
        storage=None,
        replace=None,
        async_: bool = False,
        delete_input: bool = False,
    ):
        """

        Parameters
        ----------
        storage
        replace
        async_

        delete_input :
            Whether or not to delete the input file after it has been deposited.

        Returns
        -------

        """
        try:

            if replace is None:
                replace = self.replace_existing

            if storage is None:
                storage = self.default_storage
            self.storage = storage

            self.deployment_id = self.registry.deployment_id
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
                try:
                    db.session.add(self)
                    db.session.commit()
                except sqlalchemy.exc.IntegrityError as err:
                    if "duplicate key value" in str(err):
                        # Another asset beat us to it. They'll take priority.
                        db.session.rollback()
                        asset_to_use = Asset.query.filter_by(key=self.key)
                    else:
                        raise

            if asset_to_use == self:
                self._deposit(self.storage, async_, delete_input)
                # if deposit_complete:
                #     self.deposited = True

            if self.parent:
                _label = self.label if self.label else self.key
                self.parent.assets[_label] = asset_to_use

            # if self.link:
            #     db.session.add(self.link)

            # if self.network:
            #     self.network.assets[self.label_or_key] = self
            #
            # if self.node:
            #     self.node.assets[self.label_or_key] = self
            #
            # if self.trial:
            #     self.trial.assets[self.label_or_key] = self
            #
            # if self.response:
            #     self.response.assets[self.label_or_key] = self

            return asset_to_use

        finally:
            db.session.commit()

    def _deposit(self, storage: "AssetStorage", async_: bool, delete_input: bool):
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

    def delete_input(self):
        """
        Deletes the input file(s) that make(s) up the asset.
        """
        raise NotImplementedError

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
        # cls.assert_identifiers_are_equivalent(old, new)
        cls.assert_content_ids_are_equivalent(old, new)

    # @classmethod
    # def assert_identifiers_are_equivalent(cls, old, new):
    #     _old = old.identifiers
    #     _new = new.identifiers
    #     if _old != _new:
    #         raise cls.InconsistentIdentifiersError(
    #             f"Tried to add duplicate assets with the same key ({old.key}, "
    #             "but they had inconsistent identifiers.\n"
    #             f"\nOld asset: {old.identifiers}\n"
    #             f"\nNew asset: {new.identifiers}"
    #         )

    @classmethod
    def assert_content_ids_are_equivalent(cls, old, new):
        _old = old.content_id
        _new = new.content_id

        if _old != _new:
            raise cls.InconsistentContentError(
                f"Initiated a new deposit for pre-existing asset ({new.key}), "
                "but replace=False and the content IDs did not match "
                f"(old: {_old}, new: {_new}), implying that their content differs. "
            )

    def get_content_id(self):
        raise NotImplementedError

    def generate_host_path(self, deployment_id: str):
        raise NotImplementedError

    @cached_class_property
    def experiment_class(cls):  # noqa
        from .experiment import import_local_experiment

        return import_local_experiment()["class"]

    @cached_class_property
    def registry(cls):  # noqa
        return cls.experiment_class.assets

    @cached_class_property
    def default_storage(cls):  # noqa
        return cls.registry.storage

    def export(self, path):
        try:
            self.storage.export(self, path)
        except Exception:
            from .command_line import log

            log(f"Failed to export the asset {self.key} to path {path}.")
            raise

    def export_subfile(self, subfile, path):
        assert self.is_folder
        try:
            self.storage.export_subfile(self, subfile, path)
        except Exception:
            from .command_line import log

            log(
                f"Failed to export the subfile {subfile} from asset {self.key} to path {path}."
            )
            raise

    def export_subfolder(self, subfolder, path):
        try:
            self.storage.export_subfolder(self, subfolder, path)
        except Exception:
            from .command_line import log

            log(
                f"Failed to export the subfolder {subfolder} from asset {self.key} to path {path}."
            )
            raise

    def receive_stimulus_definition(self, definition):
        self.var.stimulus_definition = definition

    def read_text(self):
        assert not self.is_folder
        with tempfile.NamedTemporaryFile() as f:
            self.export(f.name)
            with open(f.name, "r") as reader:
                return reader.read()


class MockAsset(Asset):
    @property
    def url(self):
        return "The asset database has not yet loaded, so here is a placeholder URL."

    def get_extension(self):
        return ""


class AssetLink:
    id = None
    failed = None
    failed_reason = None
    time_of_death = None

    label = Column(String, primary_key=True)

    @declared_attr
    def asset_key(cls):
        return Column(String, ForeignKey("asset.key"), primary_key=True)

    def __init__(self, label, asset):
        self.label = label
        self.asset = asset


@register_table
class AssetParticipant(AssetLink, SQLBase, SQLMixin):
    __tablename__ = "asset_participant"

    participant_id = Column(Integer, ForeignKey("participant.id"), primary_key=True)
    participant = relationship(
        "psynet.participant.Participant", back_populates="asset_links"
    )

    asset = relationship("Asset", back_populates="participant_links")


@register_table
class AssetTrial(AssetLink, SQLBase, SQLMixin):
    __tablename__ = "asset_trial"

    trial_id = Column(Integer, ForeignKey("info.id"), primary_key=True)
    trial = relationship("Trial", back_populates="asset_links")

    asset = relationship("Asset", back_populates="trial_links")

    # def __init__(self, label, asset, trial):
    #     super().__init__(label, asset)
    #     self.trial = trial


@register_table
class AssetNode(AssetLink, SQLBase, SQLMixin):
    __tablename__ = "asset_node"

    node_id = Column(Integer, ForeignKey("node.id"), primary_key=True)
    node = relationship("TrialNode", back_populates="asset_links")

    asset = relationship("Asset", back_populates="node_links")


@register_table
class AssetNetwork(AssetLink, SQLBase, SQLMixin):
    __tablename__ = "asset_network"

    network_id = Column(Integer, ForeignKey("network.id"), primary_key=True)
    network = relationship("TrialNetwork", back_populates="asset_links")

    asset = relationship("Asset", back_populates="network_links")


class ManagedAsset(Asset):
    input_path = Column(String)
    # autogenerate_key = Column(Boolean)
    obfuscate = Column(Integer)
    md5_contents = Column(String)
    size_mb = Column(Float)
    deposit_time_sec = Column(Float)

    def __init__(
        self,
        input_path,
        label=None,
        is_folder=None,
        description=None,
        data_type=None,
        extension=None,
        parent=None,
        key=None,
        variables: Optional[dict] = None,
        personal=False,
        replace_existing=False,
        obfuscate=1,  # 0: no obfuscation; 1: can't guess URL; 2: can't guess content
    ):
        self.deposited = False
        self.input_path = input_path
        self.obfuscate = obfuscate

        if is_folder is None:
            is_folder = os.path.isdir(input_path)
        # self.autogenerate_key = key is None

        super().__init__(
            key=key,
            label=label,
            is_folder=is_folder,
            description=description,
            data_type=data_type,
            extension=extension,
            parent=parent,
            replace_existing=replace_existing,
            variables=variables,
            personal=personal,
        )

    def get_content_id(self):
        return self.get_md5_contents()

    def get_md5_contents(self):
        return self._get_md5_contents(self.input_path, self.is_folder)

    @cache
    def _get_md5_contents(self, path, is_folder):
        f = md5_directory if is_folder else md5_file
        return f(path)

    def get_extension(self):
        return get_extension(self.input_path)

    def _deposit(self, storage: "AssetStorage", async_: bool, delete_input: bool):
        if self.needs_storage_backend and isinstance(storage, NoStorage):
            raise RuntimeError(
                "Cannot deposit this asset "
                f"(type = {type(self).__name__}, key = {self.key}) "
                "without an asset storage backend. "
                "Please add one to your experiment class, for example by writing "
                "asset_storage = S3Storage('your-s3-bucket', 'your-subdirectory') "
                "in your experiment class."
            )

        self.host_path = self.generate_host_path(self.deployment_id)
        self.url = self.get_url(storage)
        self.storage.update_asset_metadata(self)

        if self._needs_depositing():
            time_start = time.perf_counter()

            self.prepare_input()

            self.size_mb = self.get_size_mb()
            self.md5_contents = self.get_md5_contents()

            storage.receive_deposit(self, self.host_path, async_, delete_input)

            time_end = time.perf_counter()

            self.deposit_time_sec = time_end - time_start
        else:
            self.deposited = True

        db.session.commit()

    def prepare_input(self):
        pass

    def _needs_depositing(self):
        return True

    def after_deposit(self):
        if self.trial:
            self.trial.check_if_can_run_async_post_trial()
            self.trial.check_if_can_mark_as_finalized()

    def get_url(self, storage: "AssetStorage"):
        return storage.get_url(self.host_path)

    def delete_input(self):
        if self.is_folder:
            shutil.rmtree(self.input_path)
        else:
            os.remove(self.input_path)

    def get_size_mb(self):
        if self.is_folder:
            return get_folder_size_mb(self.input_path)
        else:
            return get_file_size_mb(self.input_path)

    def generate_key(self):
        dir_ = self.generate_dir()
        filename = self.generate_filename()
        return os.path.join(dir_, filename)

    # def get_original_parent(self):
    #     candidates = self.trials + self.nodes + self.networks + self.participants
    #     # if len(candidates) == 0:
    #     #     candidates = self.participants
    #     if len(candidates) == 0:
    #         return None
    #     else:
    #         candidates.sort(key=lambda x: x.creation_time)
    #         return candidates[0]

    @property
    def trial_maker_id(self):
        from .participant import Participant

        if self.parent is None or isinstance(self.parent, Participant):
            return None
        else:
            return self.parent.trial_maker_id

    @property
    def trial(self):
        from .trial.main import Trial

        if isinstance(self.parent, Trial):
            return self.parent

    @property
    def node(self):
        from .trial.main import Trial, TrialNode

        if isinstance(self.parent, Trial):
            return self.parent.node
        elif isinstance(self.parent, TrialNode):
            return self.parent

    @property
    def network(self):
        from .trial.main import Trial, TrialNetwork, TrialNode

        if isinstance(self.parent, (Trial, TrialNode)):
            return self.parent.network
        elif isinstance(self.parent, TrialNetwork):
            return self.parent

    @property
    def participant(self):
        from .participant import Participant

        if self.parent is None:
            return None
        elif isinstance(self.parent, Participant):
            return self.parent
        else:
            return self.parent.participant

    def get_ancestors(self):
        return {
            "network": self.network,
            "node": self.node,
            "trial": self.trial,
            "participant": self.participant,
        }

    def generate_dir(self):
        dir_ = []
        if self.trial_maker_id:
            dir_.append(f"{self.trial_maker_id}")
        if self.participant:
            dir_.append(f"participant_{self.participant.id}")
        return "/".join(dir_)

    def generate_filename(self):
        filename = ""
        identifiers = []
        ancestors = self.get_ancestors()
        if ancestors["network"] is not None:
            identifiers.append(f"network_{ancestors['network'].id}")
        if ancestors["node"] is not None:
            identifiers.append(f"node_{ancestors['node'].id}")
        if ancestors["trial"] is not None:
            identifiers.append(f"trial_{ancestors['trial'].id}")

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
    def generate_host_path(self, deployment_id: str):
        obfuscated = self.obfuscate_key(self.key)
        return os.path.join("experiments", deployment_id, obfuscated)

    def obfuscate_key(self, key):
        random = self.generate_uuid()

        if self.is_folder:
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

        if self.is_folder:
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

    # def generate_dir(self):
    #     return os.path.join(
    #         super().generate_dir(),
    #         self.compute_hash(),
    #     )

    def _needs_depositing(self):
        exists_in_cache = self.storage.check_cache(
            self.host_path, is_folder=self.is_folder
        )
        self.used_cache = exists_in_cache
        return not exists_in_cache

    def retrieve_contents(self):
        pass

    def delete_input(self):
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
        return cls.__table__.c.get("arguments", Column(PythonDict))

    @declared_attr
    def computation_time_sec(cls):
        return cls.__table__.c.get("computation_time_sec", Column(Float))

    def __init__(
        self,
        function,
        key: Optional[str] = None,
        arguments: Optional[dict] = None,
        is_folder=False,
        description=None,
        data_type=None,
        extension=None,
        parent=None,
        variables: Optional[dict] = None,
        replace_existing=False,
        personal=False,
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
        self.input_path = None
        label = key

        super().__init__(
            label=label,
            input_path=self.input_path,
            is_folder=is_folder,
            description=description,
            data_type=data_type,
            extension=extension,
            parent=parent,
            key=key,
            variables=variables,
            replace_existing=replace_existing,
            personal=personal,
            obfuscate=obfuscate,
        )

    def __del__(self):
        if hasattr(self, "temp_dir") and self.temp_dir:
            self.temp_dir.cleanup()

    def deposit(
        self,
        storage=None,
        replace=None,
        async_: bool = False,
    ):
        self.input_path = self.generate_input_path()

        super().deposit(
            storage,
            replace,
            async_,
            delete_input=True,
        )

    def generate_input_path(self):
        if self.is_folder:
            return tempfile.mkdtemp()
        else:
            return tempfile.NamedTemporaryFile(delete=False).name

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

    def prepare_input(self):
        time_start = time.perf_counter()

        self.function(path=self.input_path, **self.arguments)

        time_end = time.perf_counter()
        self.computation_time_sec = time_end - time_start

    def receive_stimulus_definition(self, definition):
        super().receive_stimulus_definition(definition)
        requested_args = get_args(self.function)
        for key, value in definition.items():
            if key in requested_args:
                self.arguments[key] = value


class FunctionAsset(FunctionAssetMixin, ExperimentAsset):
    # FunctionAssetMixin comes first in the inheritance hierarchy
    # because we need to use its ``__init__`` method.
    pass


class FastFunctionAsset(FunctionAssetMixin, ExperimentAsset):
    secret = Column(String)

    needs_storage_backend = False

    def __init__(
        self,
        function,
        key: Optional[str] = None,
        arguments: Optional[dict] = None,
        is_folder: bool = False,
        description=None,
        data_type=None,
        extension=None,
        parent=None,
        variables: Optional[dict] = None,
        replace_existing=False,
        personal=False,
        obfuscate=1,  # 0: no obfuscation; 1: can't guess URL; 2: can't guess content
    ):
        super().__init__(
            function=function,
            key=key,
            arguments=arguments,
            is_folder=is_folder,
            description=description,
            data_type=data_type,
            extension=extension,
            parent=parent,
            variables=variables,
            replace_existing=replace_existing,
            personal=personal,
            obfuscate=obfuscate,
        )
        self.secret = uuid.uuid4()  # Used to protect unauthorized access

    @cached_class_property
    def default_storage(cls):  # noqa
        return NoStorage()

    def _needs_depositing(self):
        return False

    def generate_input_path(self):
        return None

    def export(self, path):
        self.function(path=path, **self.arguments)

    def export_subfile(self, subfile, path):
        assert self.is_folder
        with tempfile.TemporaryDirectory() as tempdir:
            self.export(tempdir)
            shutil.copyfile(tempdir + "/" + subfile, path)

    def export_subfolder(self, subfolder, path):
        assert self.is_folder
        with tempfile.TemporaryDirectory() as tempdir:
            self.export(tempdir)
            shutil.copytree(tempdir + "/" + subfolder, path)

    def get_url(self, storage: "AssetStorage"):
        key_encoded = urllib.parse.quote(self.key)
        secret = self.secret
        return f"/fast-function-asset?key={key_encoded}&secret={secret}"

    def generate_host_path(self, deployment_id):
        return None


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
        is_folder=False,
        description=None,
        data_type=None,
        extension=None,
        replace_existing=False,
        label=None,
        parent=None,
        variables: Optional[dict] = None,
        personal=False,
    ):
        self.host_path = url
        self.url = url
        self.deposited = True

        super().__init__(
            key=key,
            label=label,
            is_folder=is_folder,
            description=description,
            data_type=data_type,
            extension=extension,
            parent=parent,
            replace_existing=replace_existing,
            variables=variables,
            personal=personal,
        )

    def get_extension(self):
        return get_extension(self.url)

    def _deposit(self, storage: "AssetStorage", async_: bool, delete_input: bool):
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
    def default_storage(cls):  # noqa
        return WebStorage()

    def delete_input(self):
        raise NotImplementedError


class ExternalS3Asset(ExternalAsset):
    s3_bucket = Column(String)
    s3_key = Column(String)

    def __init__(
        self,
        key,
        s3_bucket: str,
        s3_key: str,
        is_folder=False,
        description=None,
        data_type=None,
        replace_existing=False,
        label=None,
        parent=None,
        variables: Optional[dict] = None,
        personal=False,
    ):
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        url = self.generate_url()

        super().__init__(
            key=key,
            url=url,
            is_folder=is_folder,
            description=description,
            data_type=data_type,
            replace_existing=replace_existing,
            label=label,
            parent=parent,
            variables=variables,
            personal=personal,
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
    def default_storage(self):  # noqa
        return S3Storage(self.s3_bucket, root="")

    def delete_input(self):
        raise NotImplementedError


class AssetStorage:
    @property
    def experiment(self):
        from .experiment import get_experiment

        return get_experiment()

    @property
    def deployment_id(self):
        return self.experiment.deployment_id

    def on_every_launch(self):
        pass

    def update_asset_metadata(self, asset: Asset):
        pass

    def receive_deposit(self, asset, host_path: str, async_: bool, delete_input: bool):
        if async_:
            f = self._async__call_receive_deposit
        else:
            f = self._call_receive_deposit

        f(asset, host_path, delete_input)

    def _receive_deposit(self, asset: Asset, host_path: str):
        raise NotImplementedError

    def _call_receive_deposit(
        self,
        asset: Asset,
        host_path: str,
        delete_input: bool,  # , db_commit: bool = False
    ):
        # We include this for compatibility with threaded dispatching.
        # Without it, SQLAlchemy complains that the object has become disconnected
        # from the SQLAlchemy session. This command 'merges' it back into the session.
        asset = db.session.merge(asset)

        self._receive_deposit(asset, host_path)
        asset.after_deposit()
        asset.deposited = True

        # if db_commit:
        db.session.commit()

        if delete_input:
            asset.delete_input()

    def _async__call_receive_deposit(
        self, asset: Asset, host_path: str, delete_input: bool
    ):
        LocalAsyncProcess(
            self._call_receive_deposit,
            arguments=dict(
                asset=asset,
                host_path=host_path,
                delete_input=delete_input,
                # db_commit=True,
            ),
            asset=asset,
        )

    def export(self, asset, path):
        raise NotImplementedError

    def prepare_for_deployment(self):
        pass

    def get_url(self, host_path: str):
        raise NotImplementedError

    def check_cache(self, host_path: str, is_folder: bool):
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
        if asset.is_folder:
            self._folder_exporter(asset, path)
        else:
            self._file_exporter(asset, path)

    def export_subfile(self, asset, subfile, path):
        url = asset.url + "/" + subfile
        self._download_file(url, path)

    def export_subfolder(self, asset, subfolder, path):
        raise RuntimeError(
            "export_subfolder is not supported for ExternalAssets."
            "This is because the internet provides "
            "no standard way to list the contents of a folder hosted "
            "on an arbitrary web server. You can avoid this issue in future"
            "by listing each asset as a separate file."
        )

    def _folder_exporter(self, asset, path):
        with open(path, "w") as f:
            f.write(
                "It is not possible to automatically export ExternalAssets "
                "with type='folder'. This is because the internet provides "
                "no standard way to list the contents of a folder hosted "
                "on an arbitrary web server. You can avoid this issue in the "
                "future by listing each asset as a separate file."
            )

    def _file_exporter(self, asset, path):
        try:
            r = requests.get(asset.url)
            with open(path, "wb") as file:
                file.write(r.content)
        except Exception:
            print(
                f"An error occurred when trying to download asset {asset.key} from the following URL: {asset.url}"
            )
            raise


class NoStorage(AssetStorage):
    def _receive_deposit(self, asset, host_path: str):
        raise RuntimeError("Asset depositing is not supported by 'NoStorage' objects.")

    def update_asset_metadata(self, asset: Asset):
        pass


class DebugStorage(AssetStorage):
    def __init__(self, root=None):
        """

        Parameters
        ----------
        root :
            Path to the directory to be used for storage.
            Tilde expansion (e.g. '~/psynet') is performed automatically.
            If none is provided, then defaults to the config value of
            ``debug_storage_root``, which can be set in ``config.txt``
            or ``.dallingerconfig``.

        label :
            Label for the storage object.
        """
        super().__init__()

        self._initialized = False
        self._root = root
        self.label = "debug_storage"
        self.public_path = self._create_public_path()

    def setup_files(self):
        self._ensure_root_dir_exists()
        self._create_symlink()

    def prepare_for_deployment(self):
        self.setup_files()

    def on_every_launch(self):
        self.setup_files()

    @cached_property
    def root(self):
        """
        We defer the registration of the root until as late as possible
        to avoid circular imports when loading the experiment.
        """
        if self._root:
            return self._root
        else:
            try:
                from .utils import get_from_config

                return os.path.expanduser(get_from_config("debug_storage_root"))
            except KeyError:
                raise KeyError(
                    "No root location was provided to DebugStorage and no value for debug_storage_root "
                    "was found in config.txt or ~/.dallingerconfig. Consider setting a default value "
                    "in ~/.dallingerconfig, writing for example: debug_storage_root = ~/psynet-debug-storage"
                )

    def _ensure_root_dir_exists(self):
        from pathlib import Path

        Path(self.root).mkdir(parents=True, exist_ok=True)

    def _create_public_path(self):
        """
        This is the publicly exposed path by which the web browser can access the storage registry.
        This corresponds to a (symlinked) directory inside the experiment directory.
        """
        return os.path.join("static", self.label)

    def _create_symlink(self):
        try:
            os.unlink(self.public_path)
        except FileNotFoundError:
            pass
        except PermissionError:
            shutil.rmtree(self.public_path)

        os.makedirs("static", exist_ok=True)

        os.symlink(self.root, self.public_path)
        # except FileExistsError:
        #     pass

    def update_asset_metadata(self, asset: Asset):
        host_path = asset.host_path
        file_system_path = self.get_file_system_path(host_path)
        asset.var.file_system_path = file_system_path

    def _receive_deposit(self, asset: Asset, host_path: str):
        file_system_path = self.get_file_system_path(host_path)
        os.makedirs(os.path.dirname(file_system_path), exist_ok=True)

        if asset.is_folder:
            shutil.copytree(asset.input_path, file_system_path, dirs_exist_ok=True)
        else:
            shutil.copyfile(asset.input_path, file_system_path)

        asset.deposited = True

        # return dict(
        #     url=os.path.abspath(file_system_path),
        # )

    def export(self, asset, path):
        from_ = self.get_file_system_path(asset.host_path)
        to_ = path
        if asset.is_folder:
            shutil.copytree(from_, to_, dirs_exist_ok=True)
        else:
            shutil.copyfile(from_, to_)

    def export_subfile(self, asset, subfile, path):
        from_ = self.get_file_system_path(asset.host_path) + "/" + subfile
        to_ = path
        shutil.copyfile(from_, to_)

    def export_subfolder(self, asset, subfolder, path):
        from_ = self.get_file_system_path(asset.host_path) + "/" + subfolder
        to_ = path
        shutil.copytree(from_, to_, dirs_exist_ok=True)

    def get_file_system_path(self, host_path):
        if host_path:
            return os.path.join(self.root, host_path)
        else:
            return None

    def get_url(self, host_path):
        assert (
            self.root
        )  # Makes sure that the root storage location has been instantiated
        return os.path.join(self.public_path, host_path)

    def check_cache(self, host_path: str, is_folder: bool):
        file_system_path = self.get_file_system_path(host_path)
        return os.path.exists(file_system_path) and (
            (is_folder and os.path.isdir(file_system_path))
            or (not is_folder and os.path.isfile(file_system_path))
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


class AwsCliError(RuntimeError):
    pass


class S3Storage(AssetStorage):
    def __init__(self, s3_bucket, root):
        super().__init__()
        assert not root.endswith("/")
        self.s3_bucket = s3_bucket
        self.root = root

    def prepare_for_deployment(self):
        from .media import make_bucket_public

        if not self.bucket_exists(self.s3_bucket):
            self.create_bucket(self.s3_bucket)
        make_bucket_public(self.s3_bucket)

    def _receive_deposit(self, asset, host_path):
        s3_key = self.get_s3_key(host_path)
        if asset.is_folder:
            self.upload_folder(asset.input_path, s3_key)
        else:
            self.upload_file(asset.input_path, s3_key)

    def get_url(self, host_path: str):
        s3_key = self.get_s3_key(host_path)
        return os.path.join(
            "https://s3.amazonaws.com", self.s3_bucket, self.escape_s3_key(s3_key)
        )

    @staticmethod
    def bucket_exists(bucket_name):
        import botocore

        resource = get_boto3_s3_resource()
        try:
            resource.meta.client.head_bucket(Bucket=bucket_name)
        except botocore.exceptions.ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                return False
        return True

    def get_s3_key(self, host_path: str):
        return os.path.join(self.root, host_path)

    def escape_s3_key(self, s3_key):
        # This might need revisiting as and when we find special characters that aren't quoted correctly
        return urllib.parse.quote_plus(s3_key, safe="/~()*!.'")

    def check_cache(self, host_path: str, is_folder: bool, use_cache=None):
        """
        Checks whether a file or folder is present in the remote bucket.
        Uses caching where appropriate for efficiency.
        """
        s3_key = os.path.join(self.root, host_path)

        if use_cache is None:
            use_cache = not self.experiment.var.launch_finished

        if is_folder:
            return self.check_cache_for_folder(s3_key, use_cache)
        else:
            return self.check_cache_for_file(s3_key, use_cache)

    def check_cache_for_folder(self, s3_key, use_cache):
        files = self.list_files_with_prefix(s3_key + "/", use_cache)
        return len(files) > 0

    def check_cache_for_file(self, s3_key, use_cache):
        files = self.list_files_with_prefix(s3_key, use_cache)
        return s3_key in files

    def list_files_with_prefix(self, prefix, use_cache):
        try:
            if use_cache:
                # If we are in the 'preparation' phase of deployment, then we rely on a cached listing
                # of the files in the S3 bucket. This is necessary because the preparation phase
                # may involve checking caches for thousands of files at a time, and it would be slow
                # to talk to S3 separately for each one. This wouldn't catch situations where
                # the cache has been added during the preparation phase itself, but this shouldn't happen very often,
                # so doesn't need to be optimized for just yet.
                return [
                    x
                    for x in list_files_in_s3_bucket__cached(
                        self.s3_bucket, prefix=self.root
                    )
                    if x.startswith(prefix)
                ]
            else:
                return list_files_in_s3_bucket(self.s3_bucket, prefix)
        except Exception as err:
            if "NoSuchBucket" in str(err):
                return []
            raise

    # @create_bucket_if_necessary
    # def folder_exists__slow(self, s3_key):
    #     return len(self.list_folder(s3_key)) > 0
    #
    # # @create_bucket_if_necessary
    # def list_folder(self, folder):
    #     # cmd = f"aws s3 ls {s3_bucket}/{folder}/"
    #     # from subprocess import PIPE
    #     # credentials = psynet.media.get_aws_credentials()
    #     # cmd = ""
    #     # cmd += f"export AWS_ACCESS_KEY_ID={credentials['aws_access_key_id']}; "
    #     # cmd += f"export AWS_SECRET_ACCESS_KEY={credentials['aws_secret_access_key']}; "
    #     # cmd += f"aws s3 ls {s3_bucket} "
    #     # x = subprocess.run(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
    #     # breakpoint()
    #     return [x.key for x in self.boto3_bucket.objects.filter(Prefix="folder" + "/")]

    # @cached_property
    # def regex_pattern(self):
    #     return re.compile("https://s3.amazonaws.com/(.*)/(.*)")

    def export(self, asset, path):
        s3_key = self.get_s3_key(asset.host_path)
        if asset.is_folder:
            self.download_folder(s3_key, path)
        else:
            self.download_file(s3_key, path)

    def export_subfile(self, asset, subfile, path):
        assert asset.is_folder
        s3_key = self.get_s3_key(asset.host_path) + "/" + subfile
        self.download_file(s3_key, path)

    def export_subfolder(self, asset, subfolder, path):
        assert asset.is_folder
        s3_key = self.get_s3_key(asset.host_path) + "/" + subfolder
        self.download_folder(s3_key, path)

    def run_aws_command(self, cmd):
        logger.info(f"Running AWS CLI command: {cmd}")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as err:
            message = err.stderr.decode("utf8")
            raise AwsCliError(message)

    def download_file(self, s3_key, target_path):
        return self._download(s3_key, target_path, recursive=False)

    def download_folder(self, s3_key, target_path):
        return self._download(s3_key, target_path, recursive=True)

    def _download(self, s3_key, target_path, recursive):
        """
        This function relies on the AWS CLI. You can install it with pip install awscli.
        """
        url = f"s3://{self.s3_bucket}/{s3_key}"
        cmd = ["aws", "s3", "cp", url, target_path]

        if recursive:
            cmd.append("--recursive")

        logger.info(f"Downloading from AWS with command: {cmd}")
        self.run_aws_command(cmd)

    def upload_file(self, path, s3_key):
        return self._upload(path, s3_key, recursive=False)

    def upload_folder(self, path, s3_key):
        return self._upload(path, s3_key, recursive=True)

    def _upload(self, path, s3_key, recursive):
        """
        This function relies on the AWS CLI. You can install it with pip install awscli.
        """
        url = f"s3://{self.s3_bucket}/{s3_key}"
        cmd = ["aws", "s3", "cp", path, url]

        if recursive:
            cmd.append("--recursive")

        try:
            self.run_aws_command(cmd)
        except AwsCliError as err:
            if "NoSuchBucket" in str(err):
                self.create_bucket(self.s3_bucket)
                self.run_aws_command(cmd)
            else:
                raise

    @staticmethod
    def create_bucket(s3_bucket):
        client = get_boto3_s3_client()
        client.create_bucket(Bucket=s3_bucket)

    def delete_file(self, s3_key):
        url = f"s3://{self.s3_bucket}/{s3_key}"
        cmd = ["aws", "s3", "rm", url]

        self.run_aws_command(cmd)

    def delete_folder(self, s3_key):
        url = f"s3://{self.s3_bucket}/{s3_key}/"

        logger.info("Deleting the following folder from S3: {url}")

        cmd = ["aws", "s3", "rm", url, "--recursive"]
        self.run_aws_command(cmd)

    def delete_all(self):
        self.delete_folder(self.root)


class AssetRegistry:
    initial_asset_manifesto_path = "pre_deployed_assets.csv"

    def __init__(self, storage: AssetStorage, n_parallel=None):
        self.storage = storage
        self.n_parallel = n_parallel
        self._staged_asset_specifications = []
        self._staged_asset_lookup_table = {}

        # inspector = sqlalchemy.inspect(db.engine)
        # if inspector.has_table("asset") and Asset.query.count() == 0:
        #     self.populate_db_with_initial_assets()

    @property
    def deployment_id(self):
        return self.storage.deployment_id

    @property
    def experiment(self):
        from .experiment import get_experiment

        return get_experiment()

    def stage(self, *args):
        for asset in [*args]:
            assert isinstance(asset, AssetSpecification)
            self._staged_asset_specifications.append(asset)
            # self._staged_asset_lookup_table[asset.key] = asset

    def update_asset_metadata(self, asset: Asset):
        pass

    def receive_deposit(
        self, asset: Asset, host_path: str, async_: bool, delete_input: bool
    ):
        return self.storage.receive_deposit(asset, host_path, async_, delete_input)

    def get(self, key):
        return get_asset(key)

    def prepare_for_deployment(self):
        self.prepare_assets_for_deployment()
        self.storage.prepare_for_deployment()

    def prepare_assets_for_deployment(self):
        if self.n_parallel:
            n_jobs = self.n_parallel
        elif len(self._staged_asset_specifications) < 25:
            n_jobs = 1
        else:
            n_jobs = psutil.cpu_count()

        logger.info("Preparing assets for deployment...")
        Parallel(
            n_jobs=n_jobs,
            verbose=10,
            backend="threading",
            # backend="multiprocessing",  # Slow compared to threading
        )(
            delayed(lambda a: a.prepare_for_deployment(registry=self))(a)
            for a in self._staged_asset_specifications
        )
        # Parallel(n_jobs=n_jobs)(delayed(db.session.close)() for _ in range(n_jobs))

        db.session.commit()
        # self.save_initial_asset_manifesto()

    # def save_initial_asset_manifesto(self):
    #     copy_db_table_to_csv("asset", self.initial_asset_manifesto_path)

    # def populate_db_with_initial_assets(self):
    #     with open(self.initial_asset_manifesto_path, "r") as file:
    #         ingest_to_model(file, Asset)
