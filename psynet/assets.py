from sqlalchemy import Column, String

from .timeline import

class AssetRegistry():
    def link_file(self, url):
        """
        Stores a file link in the registry.

        Parameters
        ----------

        url :
            URL to that file. The file should be publicly accessible from this URL.
        """
        pass


class Asset():
    __tablename__ = "asset"

    url = Column(String)

    def __init__(self, url):
        self.url = url


class FileAsset(Asset):
    pass


class FolderAsset(Asset):
    pass


class Storage():
    pass


class NoStorage(Storage):
    pass


class LocalStorage(Storage):
    pass

class S3Storage(Storage):
    pass


def link_asset_folder(url):
