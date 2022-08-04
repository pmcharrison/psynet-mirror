import os
import pathlib
import pytest

from psynet.bot import Bot


def find_demo_dirs():
    """
    Returns
    -------

    A list of directory paths for each of the PsyNet demos.
    These are found by recursively searching in the demos directory
    for all directories containing an experiment.py file.
    """

    psynet_root = pathlib.Path(__file__).parent.parent.resolve()
    demo_root = os.path.join(psynet_root, "demos")
    return sorted(
        [os.path.relpath(dir, demo_root) for dir, sub_dirs, files in os.walk(demo_root) if "experiment.py" in files]
    )


demos = find_demo_dirs()


@pytest.mark.parametrize("demo_name", demos, indirect=True)
class TestDemos:
    def test_run_demo(self, demo_name, demo_exp):
        bot = Bot()
        bot.take_experiment()
