# Filter out the forkpty deprecation warning; apparently this is not something
# we need to worry about (see https://github.com/gevent/gevent/issues/2052).
import asyncio
import os
import warnings

import debugpy
import dominate
from dallinger.config import Configuration, experiment_available

import psynet.recruiters  # noqa: F401
from psynet.utils import patch_yaspin_jupyter_detection
from psynet.version import psynet_version

# TODO: Remove the following line which fixes the event loop warning once we've updated to
# a version of dominate > 2.9.1, which includes the following commit:
# https://github.com/Knio/dominate/commit/bdbdb8e5ddcf3213518dba0c7d054f14933460bf
dominate.dom_tag.get_event_loop = asyncio.get_running_loop

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


os.environ["GEVENT_SUPPORT"] = "True"


def debugger():
    """
    Create a breakpoint using debugpy.

    Standard IDE breakpoints don't work out of the box with PsyNet because it makes
    heavy use of subprocesses, which cannot easily be accessed using standard IDE breakpoints.
    This function provides a breakpoint that should work well in these contexts,
    specifically when running `psynet debug local`.
    It uses debugpy, which is the default debugger for VSCode/Cursor.
    The following instructions assume you are using one of these two IDEs.
    If you are using PyCharm, you should use PyCharm's remote Python debugger instead.

    Before you can use this functionality, you need to make sure your IDE workspace directory contains
    an appropriate launch.json file. In VSCode/Cursor, this file should be placed in the .vscode directory.
    We recommend the following:

    .. code:: bash

        {
            "version": "0.2.0",
            "configurations": [

                {
                    "name": "Breakpoints in psynet debug local",
                    "type": "debugpy",
                    "request": "attach",
                    "connect": {
                        "host": "localhost",
                        "port": 5678
                    },
                    "pathMappings": [
                        {
                            "localRoot": "${env:PWD}",
                            "remoteRoot": "/tmp/dallinger_develop"
                        }
                    ]
                }
            ]
        }

    Once you have this file, you simply place ``psynet.debugger()`` in the code where you want to create a breakpoint.
    Once you run ``psynet debug local``, you should see a message in your console that says "Press F5 to start debugging".
    Pressing F5 should start the debugger, and you should be able to debug your code as usual.
    """
    # 5678 is the default attach port in the VS Code debug configurations.
    # Unless a host and port are specified, host defaults to 127.0.0.1
    debugpy.listen(5678)
    print("Press F5 to start debugging")
    debugpy.wait_for_client()
    debugpy.breakpoint()
