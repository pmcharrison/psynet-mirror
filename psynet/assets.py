from dallinger import db
from sqlalchemy import Boolean, Column, String

from .dashboard import show_in_dashboard
from .data import SQLBase, SQLMixin
from .timeline import ExperimentSetupRoutine


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
        asset = FolderAsset(url, external=True)
        db.session.add(asset)


@show_in_dashboard
class Asset(SQLBase, SQLMixin):
    __tablename__ = "asset"

    # Remove default SQL columns
    creation_time = None
    failed = None
    failed_reason = None
    time_of_death = None

    external = Column(Boolean)
    url = Column(String)

    def __init__(self, url):
        self.url = url


class FileAsset(Asset):
    pass


class FolderAsset(Asset):
    pass


class Storage:
    pass


class NoStorage(Storage):
    pass


class LocalStorage(Storage):
    pass


class S3Storage(Storage):
    pass


def link_asset_folder(url):
    def f(experiment):
        experiment.asset_registry.link_folder(url)

    return ExperimentSetupRoutine(f)


def link_asset_file(url):
    def f(experiment):
        experiment.asset_registry.link_file(url)

    return ExperimentSetupRoutine(f)
