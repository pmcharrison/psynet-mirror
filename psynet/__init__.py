# Filter out the forkpty deprecation warning; apparently this is not something
# we need to worry about (see https://github.com/gevent/gevent/issues/2052).
import warnings

from dallinger.config import Configuration, experiment_available

import psynet.recruiters  # noqa: F401
from psynet.utils import patch_yaspin_jupyter_detection
from psynet.version import psynet_version

warnings.filterwarnings(
    "ignore",
    message="This process.*is multi-threaded, use of fork.*may lead to deadlocks in the child",
    category=DeprecationWarning,
)

__version__ = psynet_version

# Patch yaspin's Jupyter detection
patch_yaspin_jupyter_detection()

# Patch dallinger config
old_load = Configuration.load


def load(self, strict=True):
    if not experiment_available():
        # If we're not in an experiment directory, Dallinger won't have loaded our custom configurations.
        # We better do that now.
        from psynet.experiment import Experiment

        try:
            Experiment.extra_parameters()
        except KeyError as e:
            if "is already registered" in str(e):
                pass
            else:
                raise
        self.extend(Experiment.config_defaults(), strict=strict)

    old_load(self, strict=strict)


Configuration.load = load
