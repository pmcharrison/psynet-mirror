import os
import pathlib

import pytest

from psynet.bot import Bot

psynet_root = pathlib.Path(__file__).parent.parent.resolve()
demo_root = os.path.join(psynet_root, "demos")


def find_demo_dirs():
    """
    Returns
    -------

    A list of directory paths for each of the PsyNet demos.
    These are found by recursively searching in the demos directory
    for all directories containing an experiment.py file.
    """
    return sorted(
        [
            dir
            for dir, sub_dirs, files in os.walk(demo_root)
            if "experiment.py" in files and not dir.endswith("/develop")
        ]
    )


demos = find_demo_dirs()

demos = [
    # "/Users/peter/git/psynet-package/demos/assets",
    # "/Users/peter/git/psynet-package/demos/async_pruning",
    # "/Users/peter/git/psynet-package/demos/attention_test",
    # "/Users/peter/git/psynet-package/demos/audio",
    # "/Users/peter/git/psynet-package/demos/audio_forced_choice_test",
    # "/Users/peter/git/psynet-package/demos/audio_gibbs",
    # "/Users/peter/git/psynet-package/demos/audio_stimulus_set_from_dir",
    # "/Users/peter/git/psynet-package/demos/bot",
    # "/Users/peter/git/psynet-package/demos/bot_2",
    "/Users/peter/git/psynet-package/demos/color_blindness",
    "/Users/peter/git/psynet-package/demos/color_vocabulary",
    "/Users/peter/git/psynet-package/demos/complex_audio_gibbs",
    "/Users/peter/git/psynet-package/demos/consents",
    "/Users/peter/git/psynet-package/demos/custom_table_complex",
    "/Users/peter/git/psynet-package/demos/custom_table_simple",
    "/Users/peter/git/psynet-package/demos/demography/complete",
    "/Users/peter/git/psynet-package/demos/demography/general",
    "/Users/peter/git/psynet-package/demos/demography/gmsi",
    "/Users/peter/git/psynet-package/demos/demography/gmsi_short",
    "/Users/peter/git/psynet-package/demos/demography/gmsi_two_modules_with_subscales",
    "/Users/peter/git/psynet-package/demos/demography/pei",
    "/Users/peter/git/psynet-package/demos/dense_color",
    "/Users/peter/git/psynet-package/demos/gibbs",
    "/Users/peter/git/psynet-package/demos/graph",
    "/Users/peter/git/psynet-package/demos/graphics",
    "/Users/peter/git/psynet-package/demos/headphone_test",
    "/Users/peter/git/psynet-package/demos/imitation_chain",
    "/Users/peter/git/psynet-package/demos/imitation_chain_accumulated",
    "/Users/peter/git/psynet-package/demos/language_tests",
    "/Users/peter/git/psynet-package/demos/mcmcp",
    "/Users/peter/git/psynet-package/demos/modular_page",
    "/Users/peter/git/psynet-package/demos/option_controls",
    "/Users/peter/git/psynet-package/demos/page_maker",
    "/Users/peter/git/psynet-package/demos/pickle_page",
    "/Users/peter/git/psynet-package/demos/progress_display",
    "/Users/peter/git/psynet-package/demos/recruiters/cap_recruiter",
    "/Users/peter/git/psynet-package/demos/recruiters/lucid",
    "/Users/peter/git/psynet-package/demos/recruiters/prolific",
    "/Users/peter/git/psynet-package/demos/repp_tests",
    "/Users/peter/git/psynet-package/demos/rhythm_slider",
    "/Users/peter/git/psynet-package/demos/simple_audio_slider",
    "/Users/peter/git/psynet-package/demos/singing_iterated",
    "/Users/peter/git/psynet-package/demos/slider",
    "/Users/peter/git/psynet-package/demos/static",
    "/Users/peter/git/psynet-package/demos/static_audio",
    "/Users/peter/git/psynet-package/demos/static_audio_2",
    "/Users/peter/git/psynet-package/demos/tapping_iterated",
    "/Users/peter/git/psynet-package/demos/tapping_memory",
    "/Users/peter/git/psynet-package/demos/tapping_static",
    "/Users/peter/git/psynet-package/demos/timeline",
    "/Users/peter/git/psynet-package/demos/timeline_with_error",
    "/Users/peter/git/psynet-package/demos/translation",
    "/Users/peter/git/psynet-package/demos/unity_autoplay",
    "/Users/peter/git/psynet-package/demos/video",
    "/Users/peter/git/psynet-package/demos/video_imitation_chain",
    "/Users/peter/git/psynet-package/demos/wait",
]


@pytest.mark.parametrize("experiment_directory", demos, indirect=True)
def test_run_demo(launched_experiment):
    bots = [Bot() for _ in range(launched_experiment.test_num_bots)]
    for bot in bots:
        bot.take_experiment()
    assert launched_experiment.test_ran_successfully(bots=bots)


# Example of how to test a single demo at a time

# demo_to_test = "assets"
# @pytest.mark.parametrize("experiment_directory", [os.path.join(demo_root, demo_to_test)], indirect=True)
# def test_run_demo(launched_experiment):
#     bots = [Bot() for _ in range(launched_experiment.test_num_bots)]
#     for bot in bots:
#         bot.take_experiment()
#     assert launched_experiment.test_ran_successfully(bots=bots)
