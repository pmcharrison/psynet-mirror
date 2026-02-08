from dallinger.experiment import experiment_route
from dallinger.experiment_server.utils import success_response

import psynet.experiment
from psynet.db import with_transaction
from psynet.page import InfoPage
from psynet.process import WorkerAsyncProcess
from psynet.redis import redis_vars
from psynet.timeline import Timeline
from psynet.utils import get_logger

logger = get_logger()

LOG_PREFIX = "LOG_CAPTURE"

WORKER_DONE_KEY = "log_capture_worker_done"
CLOCK_DONE_KEY = "log_capture_clock_done"
EXPERIMENT_DONE_KEY = "log_capture_experiment_done"


def _log_marker(stage, process, level):
    return f"{LOG_PREFIX}|stage={stage}|process={process}|level={level}"


def _emit_logs(stage, process):
    logger.info(_log_marker(stage, process, "info"))
    logger.warning(_log_marker(stage, process, "warning"))
    logger.error(_log_marker(stage, process, "error"))
    logger.critical(_log_marker(stage, process, "critical"))
    try:
        raise RuntimeError(_log_marker(stage, process, "exception"))
    except RuntimeError:
        logger.exception(_log_marker(stage, process, "exception"))


def _worker_log_task():
    _emit_logs("async", "worker")
    redis_vars.set(WORKER_DONE_KEY, True)


class Exp(psynet.experiment.Experiment):
    label = "Log capture test"

    timeline = Timeline(
        InfoPage("Log capture test", time_estimate=1),
    )

    def on_every_launch(self):
        super().on_every_launch()
        redis_vars.set(WORKER_DONE_KEY, False)
        redis_vars.set(CLOCK_DONE_KEY, False)
        redis_vars.set(EXPERIMENT_DONE_KEY, False)
        _emit_logs("launch", "web")

    @experiment_route("/log_capture", methods=["POST"])
    @classmethod
    @with_transaction
    def log_capture(cls):
        _emit_logs("experiment", "web")
        WorkerAsyncProcess(function=_worker_log_task)
        redis_vars.set(EXPERIMENT_DONE_KEY, True)
        return success_response()

    @psynet.experiment.scheduled_task("interval", seconds=1.0, max_instances=1)
    @staticmethod
    def log_from_clock():
        if not psynet.experiment.is_experiment_launched():
            return
        if redis_vars.get(CLOCK_DONE_KEY, default=False):
            return
        _emit_logs("scheduled", "clock")
        redis_vars.set(CLOCK_DONE_KEY, True)
