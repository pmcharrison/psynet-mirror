import psynet.recruiters  # noqa: F401
from psynet.version import check_dallinger_version, psynet_version

check_dallinger_version()
__version__ = psynet_version
