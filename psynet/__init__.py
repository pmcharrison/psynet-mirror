from dallinger.config import Configuration, experiment_available

import psynet.recruiters  # noqa: F401
from psynet.version import psynet_version

__version__ = psynet_version


# Patch dallinger config
old_load = Configuration.load


def load(self):
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
        self.extend(Experiment.config_defaults(), strict=True)

    old_load(self)


Configuration.load = load
