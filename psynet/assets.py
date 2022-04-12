from dallinger import db
from sqlalchemy import Column, String

from .dashboard import show_in_dashboard
from .data import Base, SharedMixin
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
        asset = FolderAsset(url)
        db.session.add(asset)


@show_in_dashboard
class Asset(Base, SharedMixin):
    __tablename__ = "asset"

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
