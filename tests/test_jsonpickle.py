# import jsonpickle
import pytest


@pytest.mark.usefixtures("demo_static")
def test_jsonpickle_sql(trial, node, network, participant):
    pass
    # trial_pickled = jsonpickle.encode(trial)
    # import pydevd_pycharm
    #
    # pydevd_pycharm.settrace(
    #     "localhost", port=12345, stdoutToServer=True, stderrToServer=True
    # )
