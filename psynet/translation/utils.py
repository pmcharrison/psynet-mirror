LOCALES_DIR = "locales"


def get_locales_dir(locales_dir):
    """Get the locales directory."""
    if locales_dir is None:
        from ..utils import LOCALES_DIR

        locales_dir = LOCALES_DIR
    return locales_dir
