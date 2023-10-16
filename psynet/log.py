import os
import re
import sys
from datetime import datetime

import pandas as pd
import pexpect


def export_docker_ssh_logs(app, server, log_path, timeout=60):
    assert log_path.endswith(
        ".log"
    ), f"Log path ({log_path}) must have a valid extension (.log)."
    folder = os.path.dirname(log_path)
    assert os.path.exists(folder), f"Folder {folder} does not exist."

    cmd = f"ssh -o StrictHostKeyChecking=no {server} docker compose -f '~/dallinger/{app}/docker-compose.yml' logs"
    p = pexpect.spawn(cmd, timeout=timeout)
    with open(log_path, "w") as file:
        while not p.eof():
            line = p.readline().decode("utf-8")
            file.write("%s\n" % line)
    p.close()
    if p.exitstatus > 0:
        sys.exit(p.exitstatus)


def bold(text: str):
    """
    Use this within e.g. ``logger.info`` to format text in bold.
    """
    bold_start, bold_end = "\033[1m", "\033[0m"
    return bold_start + text + bold_end


def parse_gunicorn_logs(path):
    with open(path, "r") as f:
        lines = f.readlines()
    split_lines = [line.split("|") for line in lines]
    locations = [line[0].strip() for line in split_lines]
    messages = ["|".join(line[1:]) for line in split_lines]
    return pd.DataFrame({"location": locations, "message": messages})


def analyze_loading_times(logs, plot=True):
    timeline = logs.query("message.str.contains('/timeline/')", engine="python")

    timestamps = [
        datetime.strptime(re.findall(r"\[(.*?)\]", message)[0], "%Y-%m-%d %H:%M:%S")
        for message in timeline.message
    ]
    loading_times = [
        float(message.split(" ")[-1].split("\n")[0]) for message in timeline.message
    ]

    loading_time_df = pd.DataFrame(
        {"timestamp": timestamps, "loading_time": loading_times}
    )

    if plot:
        from matplotlib import pyplot as plt

        plt.figure(figsize=(10, 5))
        plt.plot(loading_time_df.timestamp, loading_time_df.loading_time)
        plt.xlabel("Time")
        plt.ylabel("Loading time (s)")
        plt.title("Loading time of pages")
        plt.show()


def analyze_errors(logs):
    errors = logs.query("message.str.contains('ERROR')", engine="python")
    print(errors.message.value_counts())
