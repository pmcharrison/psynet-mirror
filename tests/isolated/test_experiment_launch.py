from unittest.mock import patch

import pytest
from dallinger import db

from psynet import deployment_info as deployment_info_module
from psynet.command_line import run_prepare_in_subprocess
from psynet.experiment import ExperimentConfig, get_experiment
from psynet.pytest_psynet import path_to_test_experiment
from psynet.redis import redis_vars


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static")], indirect=True
)
def test_on_every_launch_ingests_template_when_redis_flag_is_stale(
    in_experiment_directory, deployment_info
):
    deployment_info_module.write(is_local_deployment=False)
    run_prepare_in_subprocess()

    db.init_db(drop_all=True)
    redis_vars.clear()
    redis_vars.set("deployment_db_ingested", True)

    get_experiment.cache_clear()
    exp = get_experiment()
    with (
        patch.object(exp, "load_deployment_config"),
        patch.object(exp.asset_storage, "on_every_launch"),
        patch.object(exp, "record_experiment_status"),
    ):
        exp.on_every_launch()

    assert ExperimentConfig.query.count() == 1
    assert exp.var.deployment_id == deployment_info_module.read("deployment_id")
