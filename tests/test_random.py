# # This seemed like a good idea for preventing cases where people use random functions
# # in code blocks, page makers, etc. In practice however it didn't work, because
# # some library functions tamper with the random state in a hidden way,
# # making the check have too many false positives.
#
# import random
#
# import pytest
#
# from psynet.page import InfoPage
# from psynet.timeline import PageMaker
# from psynet.trial.main import GenericTrialSource, Trial
#
#
# class CustomTrial(Trial):
#     def show_trial(self, experiment, participant):
#         return InfoPage(
#             f"Here is a random number: {random.randint(0, 1000)}",
#             time_estimate=5,
#         )
#
#     def show_feedback(self, experiment, participant):
#         return InfoPage(
#             f"Here is another random number: {random.randint(0, 1000)}",
#             time_estimate=5,
#         )
#
#
# @pytest.mark.parametrize("experiment_directory", ["../demos/mcmcp"], indirect=True)
# def test_trial(launched_experiment, participant):
#     trial = CustomTrial(
#         launched_experiment,
#         node=GenericTrialSource.query.one(),
#         participant=participant,
#         propagate_failure=False,
#         is_repeat_trial=False,
#         definition={},
#     )
#
#     with pytest.raises(
#         RuntimeError, match="It looks like you used Python's random number generator"
#     ):
#         trial._show_trial(launched_experiment, participant)
#
#     with pytest.raises(
#         RuntimeError, match="It looks like you used Python's random number generator"
#     ):
#         trial._show_feedback(launched_experiment, participant)
#
#     page_maker = PageMaker(
#         lambda: InfoPage(f"Here is a random number: {random.randint(0, 1000)}"),
#         time_estimate=5,
#     )
#
#     with pytest.raises(
#         RuntimeError, match="It looks like you used Python's random number generator"
#     ):
#         page_maker.resolve(launched_experiment, participant, position=0)
