from unittest.mock import patch

from psynet.experiment import Experiment


def test_performance_summary_handles_missing_response_metrics():
    result = {
        "n_bots": 2,
        "duration_minutes": 0.1,
        "actual_duration": 6.3,
        "total_bots_started": 1,
        "completed_during_test": 1,
        "bot_errors": 0,
        "bots_succeeded": 1,
        "bots_failed": 0,
        "bots_incomplete": 0,
        "total_requests": 0,
        "successful_requests": 0,
        "request_errors": 0,
        "avg_response_time": None,
        "median_response_time": None,
        "p95_response_time": None,
        "p99_response_time": None,
        "stddev_response_time": None,
        "avg_bot_duration": 6.3,
        "avg_init_time": 0.5,
    }

    with patch("psynet.experiment.logger.info") as logger_info:
        Experiment._print_performance_summary(None, [result])

    all_messages = [call.args[0] for call in logger_info.call_args_list]
    assert any("N/A" in message for message in all_messages)


def test_performance_summary_handles_no_completed_or_failed_bots():
    result = {
        "n_bots": 2,
        "duration_minutes": 0.1,
        "actual_duration": 0.8,
        "total_bots_started": 1,
        "completed_during_test": 0,
        "bot_errors": 0,
        "bots_succeeded": 1,
        "bots_failed": 0,
        "bots_incomplete": 0,
        "total_requests": 0,
        "total_requests": 0,
        "successful_requests": 0,
        "request_errors": 0,
        "avg_response_time": 0.0,
        "median_response_time": None,
        "p95_response_time": 0.0,
        "p99_response_time": None,
        "stddev_response_time": None,
        "avg_bot_duration": None,
        "avg_init_time": None,
    }

    with patch("psynet.experiment.logger.info"):
        Experiment._print_performance_summary(None, [result])
