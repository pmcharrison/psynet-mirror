import os
import pathlib

import pytest

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
    # "/Users/peter.harrison/git/psynet-package/demos/assets",
    # "/Users/peter.harrison/git/psynet-package/demos/async_pruning",
    # "/Users/peter.harrison/git/psynet-package/demos/attention_test",
    # "/Users/peter.harrison/git/psynet-package/demos/audio",
    # "/Users/peter.harrison/git/psynet-package/demos/audio_forced_choice_test",
    # "/Users/peter.harrison/git/psynet-package/demos/audio_gibbs",
    # "/Users/peter.harrison/git/psynet-package/demos/audio_stimulus_set_from_dir",
    # "/Users/peter.harrison/git/psynet-package/demos/bot",
    # "/Users/peter.harrison/git/psynet-package/demos/bot_2",
    # "/Users/peter.harrison/git/psynet-package/demos/color_blindness",
    # "/Users/peter.harrison/git/psynet-package/demos/color_vocabulary",
    # "/Users/peter.harrison/git/psynet-package/demos/complex_audio_gibbs",
    # "/Users/peter.harrison/git/psynet-package/demos/consents",
    # "/Users/peter.harrison/git/psynet-package/demos/custom_table_complex",
    # "/Users/peter.harrison/git/psynet-package/demos/custom_table_simple",
    # "/Users/peter.harrison/git/psynet-package/demos/demography/complete",
    # "/Users/peter.harrison/git/psynet-package/demos/demography/general",
    # "/Users/peter.harrison/git/psynet-package/demos/demography/gmsi",
    # "/Users/peter.harrison/git/psynet-package/demos/demography/gmsi_short",
    # "/Users/peter.harrison/git/psynet-package/demos/demography/gmsi_two_modules_with_subscales",
    # "/Users/peter.harrison/git/psynet-package/demos/demography/pei",
    # "/Users/peter.harrison/git/psynet-package/demos/dense_color",
    # "/Users/peter.harrison/git/psynet-package/demos/gibbs",
    # "/Users/peter.harrison/git/psynet-package/demos/graph",
    # "/Users/peter.harrison/git/psynet-package/demos/graphics",
    # "/Users/peter.harrison/git/psynet-package/demos/headphone_test",
    # "/Users/peter.harrison/git/psynet-package/demos/imitation_chain",
    # "/Users/peter.harrison/git/psynet-package/demos/imitation_chain_accumulated",
    # "/Users/peter.harrison/git/psynet-package/demos/language_tests",
    # "/Users/peter.harrison/git/psynet-package/demos/mcmcp",
    # "/Users/peter.harrison/git/psynet-package/demos/modular_page",
    # "/Users/peter.harrison/git/psynet-package/demos/option_controls",
    # "/Users/peter.harrison/git/psynet-package/demos/page_maker",
    # "/Users/peter.harrison/git/psynet-package/demos/pickle_page",
    # "/Users/peter.harrison/git/psynet-package/demos/progress_display",
    # "/Users/peter.harrison/git/psynet-package/demos/recruiters/cap_recruiter",
    # "/Users/peter.harrison/git/psynet-package/demos/recruiters/lucid",
    # "/Users/peter.harrison/git/psynet-package/demos/recruiters/prolific",
    # "/Users/peter.harrison/git/psynet-package/demos/repp_tests",
    # "/Users/peter.harrison/git/psynet-package/demos/rhythm_slider",
    # "/Users/peter.harrison/git/psynet-package/demos/simple_audio_slider",
    # "/Users/peter.harrison/git/psynet-package/demos/singing_iterated",
    # "/Users/peter.harrison/git/psynet-package/demos/slider",
    # "/Users/peter.harrison/git/psynet-package/demos/static",
    # "/Users/peter.harrison/git/psynet-package/demos/static_audio",
    # "/Users/peter.harrison/git/psynet-package/demos/static_audio_2",
    # "/Users/peter.harrison/git/psynet-package/demos/tapping_iterated",
    # "/Users/peter.harrison/git/psynet-package/demos/tapping_memory",
    # "/Users/peter.harrison/git/psynet-package/demos/tapping_static",
    "/Users/peter.harrison/git/psynet-package/demos/timeline",
    "/Users/peter.harrison/git/psynet-package/demos/timeline_with_error",
    "/Users/peter.harrison/git/psynet-package/demos/translation",
    "/Users/peter.harrison/git/psynet-package/demos/unity_autoplay",
    "/Users/peter.harrison/git/psynet-package/demos/video",
    "/Users/peter.harrison/git/psynet-package/demos/video_imitation_chain",
    "/Users/peter.harrison/git/psynet-package/demos/wait",
]

skip = ["singing_iterated"]  # Relies on melody package, which needs updating

demos = [d for d in demos if not d.endswith("singing_iterated")]


@pytest.mark.parametrize("experiment_directory", demos, indirect=True)
def test_run_demo(launched_experiment):
    launched_experiment.test_experiment()


# Example of how to test a single demo at a time

# demo_to_test = "assets"
# @pytest.mark.parametrize("experiment_directory", [os.path.join(demo_root, demo_to_test)], indirect=True)
# def test_run_demo(launched_experiment):
#     bots = [Bot() for _ in range(launched_experiment.num_test_bots)]
#     for bot in bots:
#         bot.take_experiment()
#     assert launched_experiment.test_check_bots(bots=bots)
