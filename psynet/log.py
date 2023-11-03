import os
import platform
import re
import sys
from datetime import datetime
from os.path import abspath, basename, dirname

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


ERROR_BLOCKLIST = [
    "ERROR:Experiment_Server:Exception on /.git/config [GET]",
    "ERROR:Experiment_Server:Exception on /.vscode/sftp.json [GET]",
    "ERROR:Experiment_Server:Exception on /v2/_catalog [GET]",
    "ERROR:Experiment_Server:Exception on /telescope/requests [GET]",
]

WARNING_BLOCKLIST_SUBSTRING = [
    "setting to default locale of the experiment",
    "WARNING:Experiment_Server:Could not find a valid locale",
]

CONSOLE_END_SYTLE = "\033[0m"
CONSOLE_STYLES = {
    "bold": {
        "prefix": "\033[1m",
        "suffix": CONSOLE_END_SYTLE,
    },
    "underline": {
        "prefix": "\033[4m",
        "suffix": CONSOLE_END_SYTLE,
    },
    "italic": {
        "prefix": "\033[3m",
        "suffix": CONSOLE_END_SYTLE,
    },
    "blue": {
        "prefix": "\033[94m",
        "suffix": CONSOLE_END_SYTLE,
    },
    "red": {
        "prefix": "\033[91m",
        "suffix": CONSOLE_END_SYTLE,
    },
    "green": {
        "prefix": "\033[92m",
        "suffix": CONSOLE_END_SYTLE,
    },
    "yellow": {
        "prefix": "\033[93m",
        "suffix": CONSOLE_END_SYTLE,
    },
    "orange": {
        "prefix": "\033[33m",
        "suffix": CONSOLE_END_SYTLE,
    },
}

MARKDOWN_STYLES = {
    "bold": {
        "prefix": "**",
        "suffix": "**",
    },
    "underline": {
        "prefix": "<u>",
        "suffix": "</u>",
    },
    "italic": {
        "prefix": "*",
        "suffix": "*",
    },
    "blue": {
        "prefix": '<span style="color:blue">',
        "suffix": "</span>",
    },
    "red": {
        "prefix": '<span style="color:red">',
        "suffix": "</span>",
    },
    "green": {
        "prefix": '<span style="color:green">',
        "suffix": "</span>",
    },
    "yellow": {
        "prefix": '<span style="color:yellow">',
        "suffix": "</span>",
    },
    "orange": {
        "prefix": '<span style="color:orange">',
        "suffix": "</span>",
    },
}

DEFAULT_SYNTAX = "console"


def _get_style(style, syntax):
    if syntax == "console":
        return CONSOLE_STYLES[style]
    elif syntax == "markdown":
        return MARKDOWN_STYLES[style]
    else:
        raise ValueError(f"Invalid syntax: {syntax}")


def _apply_style(text, style, syntax):
    style = _get_style(style, syntax)
    return f"{style['prefix']}{text}{style['suffix']}"


def bold(text, syntax=DEFAULT_SYNTAX):
    return _apply_style(text, "bold", syntax)


def underline(text, syntax=DEFAULT_SYNTAX):
    return _apply_style(text, "underline", syntax)


def italic(text, syntax=DEFAULT_SYNTAX):
    return _apply_style(text, "italic", syntax)


def blue(text, syntax=DEFAULT_SYNTAX):
    return _apply_style(text, "blue", syntax)


def red(text, syntax=DEFAULT_SYNTAX):
    return _apply_style(text, "red", syntax)


def green(text, syntax=DEFAULT_SYNTAX):
    return _apply_style(text, "green", syntax)


def yellow(text, syntax=DEFAULT_SYNTAX):
    return _apply_style(text, "yellow", syntax)


def orange(text, syntax=DEFAULT_SYNTAX):
    return _apply_style(text, "orange", syntax)


def warning(text: str, syntax=DEFAULT_SYNTAX):
    return orange(text, syntax)


def error(text: str, syntax=DEFAULT_SYNTAX):
    return red(text, syntax)


def none(text: str, syntax=DEFAULT_SYNTAX):
    return text


def success(text: str, syntax=DEFAULT_SYNTAX):
    return green(text, syntax)


def parse_gunicorn_logs(path):
    with open(path, "r") as f:
        lines = f.readlines()
    split_lines = [line.split("|") for line in lines]
    locations = [line[0].strip() for line in split_lines]
    messages = ["|".join(line[1:]) for line in split_lines]
    logs = pd.DataFrame({"location": locations, "message": messages})
    logs["cleaned_message"] = logs.message.apply(lambda x: x.strip())
    return logs


LOADING_TIMES_STATUS_LIST = [
    {"min": 0, "max": 0.3, "color": "green", "style": green, "label": "normal"},
    {
        "min": 0.3,
        "max": 0.8,
        "color": "orange",
        "style": orange,
        "label": "slightly slow",
    },
    {"min": 0.8, "max": 1.5, "color": "red", "style": red, "label": "slow"},
    {"min": 1.5, "label": "critically slow", "color": "black", "style": none},
]


def _log_path_to_report_path(log_path):
    log_name = basename(log_path)
    log_dir = dirname(log_path)
    bname, ext = basename(log_name).split(".")
    return f"{log_dir}/{bname}-report.md"


def _find_stack_trace(logs, line_number):
    pattern = r"\d{4}-\d{2}-\d{2}|" + "|".join(["INFO", "WARNING", "ERROR", ">>>>"])
    stack_trace = []
    for i in range(100):
        msg = logs.iloc[line_number + 1 + i].message
        if len(re.findall(pattern, msg)) > 0:
            break
        else:
            stack_trace.append(msg)
    return len(stack_trace), stack_trace


def _parse_error(message, logs, line_number):
    stack_trace_length, stack_trace = _find_stack_trace(logs, line_number)
    error_id = message.strip()
    error_description = ""
    error_type = ""
    if stack_trace_length > 0:
        error_statement = stack_trace[-1].strip()
        error_split = error_statement.split(": ")
        error_type = error_split[0]
        if len(error_split) > 1:
            error_description = ": ".join(error_split[1:])
        error_id = error_type
    return {
        "error_id": error_id,
        "line_start": line_number,
        "line_end": line_number + stack_trace_length,
        "message": message,
        "stack_trace": "".join(stack_trace),
        "error_type": error_type,
        "error_description": error_description,
    }


def parse_errors(logs):
    errors = logs.query("message.str.contains('ERROR')", engine="python")

    errors = errors.query("cleaned_message not in @ERROR_BLOCKLIST")
    error_list = []
    for line_number, row in errors.iterrows():
        error_list.append(_parse_error(row.message, logs, line_number))
    error_df = pd.DataFrame(error_list)
    if len(error_df) > 0:
        error_df.sort_values(["error_id", "line_start"], inplace=True)
    return error_df


def _parse_warning(warning, line_number):
    split_warning = warning.split(":")
    if len(split_warning) >= 3:
        return {
            "line_start": line_number,
            "warning_type": split_warning[1].strip(),
            "warning_message": ":".join(split_warning[2:]).strip(),
        }
    else:
        return None


def parse_warnings(logs):
    warnings = logs.query("message.str.contains('WARNING')", engine="python")

    idx = warnings.message.apply(
        lambda x: not any([substring in x for substring in WARNING_BLOCKLIST_SUBSTRING])
    )
    warnings = warnings[idx]

    parsed_warnings = []
    for line_number, row in warnings.iterrows():
        warning = row.cleaned_message
        parsed_warning = _parse_warning(warning, line_number)
        if parsed_warning is None:
            print("Warning could not be parsed: ", warning)
        else:
            parsed_warnings.append(parsed_warning)

    return pd.DataFrame(parsed_warnings)


def parse_resources(logs):
    resources = logs.query("message.str.contains('CPU usage')", engine="python").copy()
    resources["cpu_usage"] = resources.message.apply(
        lambda x: float(re.findall(r"CPU usage: (.*?)%", x)[0])
    )
    resources["memory_usage"] = resources.message.apply(
        lambda x: float(re.findall(r"RAM usage: (.*?)%", x)[0])
    )
    resources["free_disk_storage"] = resources.message.apply(
        lambda x: float(re.findall(r"Free disk space: (.*?)%", x)[0])
    )
    resources["timestamp"] = resources.message.apply(
        lambda x: datetime.strptime(
            re.findall(r"\[(.*?)\]", x)[0], "%Y-%m-%d %H:%M:%S.%f"
        )
    )
    resources = resources.reset_index()
    return resources[["cpu_usage", "memory_usage", "free_disk_storage", "timestamp"]]


def parse_loading_times(logs):
    timeline = logs.query("message.str.contains('Timeline page took')", engine="python")

    # TODO update this to work with latest Dallinger PR: https://github.com/Dallinger/Dallinger/pull/5749

    timestamps = [
        datetime.strptime(re.findall(r"\[(.*?)\]", message)[0], "%Y-%m-%d %H:%M:%S")
        for message in timeline.message
    ]

    loading_times = [
        float(message.split("Timeline page took ")[-1].split(" seconds")[0])
        for message in timeline.message
    ]

    return pd.DataFrame({"timestamp": timestamps, "loading_time": loading_times})


def _write_heading():
    report_md = "# Automatic log report\n"
    report_md += "## Overview\n"
    report_md += "1. [Summary](#summary)\n"
    report_md += "2. [Errors](#errors)\n"
    report_md += "3. [Warnings](#warnings)\n"
    report_md += "4. [Application metrics](#application-metrics)\n"
    return report_md


def _write_summary(log_path, logs, error_df, warning_df):
    report_md = "## Summary\n"
    log_name = basename(log_path)
    report_md += f"**File**: {log_name}\n\n"
    report_md += f"**Number of lines**: {len(logs)}\n\n"
    report_md += f"**Number of errors**: {len(error_df)}\n\n"
    report_md += f"**Number of warnings**: {len(warning_df)}\n\n"
    return report_md


def _write_errors(error_df):
    report_md = "## Errors\n"

    report_md += f"**{len(error_df)} errors**\n"
    if len(error_df) == 0:
        return report_md
    for error_id, error_group in error_df.groupby("error_id"):
        report_md += f"### {error_id}\n"

        for stack_trace, stack_trace_group in error_group.groupby("stack_trace"):
            # If the stack trace is identical, it implies the description is identical
            description = stack_trace_group.error_description.values[0]
            if description != "":
                report_md += f"#### {description}\n"
            report_md += f"Number of errors: {len(stack_trace_group)}\n"
            for line_number, row in stack_trace_group.iterrows():
                line_range = f"{row.line_start}"
                if row.line_start != row.line_end:
                    line_range += f"-{row.line_end}"
                report_md += f"1. `{row.message}` (line: {line_range})\n"
            if len(stack_trace) > 0:
                report_md += "```\n"
                report_md += stack_trace + "\n"
                report_md += "```\n"
        report_md += "\n"
    return report_md


def _write_warnings(warning_df):
    report_md = "## Warnings\n"

    report_md += f"**{len(warning_df)} warnings**\n"

    if len(warning_df) == 0:
        return report_md

    for warning_type, warning_group in warning_df.groupby("warning_type"):
        report_md += f"### `{warning_type}`\n"
        for line_number, row in warning_group.iterrows():
            report_md += f"1. `{row.warning_message}` (line: {row.line_start})\n"
        report_md += "\n"
    return report_md


def _get_loading_time_status(loading_time_df):
    console_messages, markdown_messages = [], []
    if len(loading_time_df) == 0:
        return console_messages, markdown_messages
    for status in LOADING_TIMES_STATUS_LIST:
        if status.get("max", None) is not None:
            idx = loading_time_df.loading_time.between(
                status["min"], status["max"], inclusive="both"
            )
        else:
            idx = loading_time_df.loading_time >= status["min"]
        n_requests = len(loading_time_df[idx])
        percent_requests = n_requests / len(loading_time_df) * 100
        style = status["style"]
        request_report = f"{n_requests} requests ({percent_requests:.2f}%)"
        markdown_label = (
            f"{bold(style(status['label'], syntax='markdown'), syntax='markdown')}"
        )
        console_label = (
            f"{bold(style(status['label'], syntax='console'), syntax='console')}"
        )
        markdown_messages.append(f"{markdown_label}: {request_report}")
        console_messages.append(f"- {console_label}: {request_report}")
    return console_messages, markdown_messages


def _plot_resource_usage_over_time(
    timestamps,
    resource_usage,
    title,
    y_label,
    output_path,
    latest=120,
    visual_guides=None,
):
    import matplotlib.pyplot as plt
    from matplotlib.dates import DateFormatter, MinuteLocator

    resource_df = pd.DataFrame(
        {"timestamp": timestamps, "resource_usage": resource_usage}
    )
    resource_df = resource_df.set_index("timestamp")
    resource_df = resource_df.resample("1min").mean()
    resource_df = resource_df.reset_index()

    if len(resource_df) > latest:
        time_stamp = resource_df.iloc[-latest].timestamp

        # Round to nearest 30 minutes
        time_stamp = time_stamp - pd.Timedelta(minutes=time_stamp.minute % 30)

        resource_df = resource_df.query("timestamp >= @time_stamp")

    fig = plt.figure(figsize=(10, 5))
    if visual_guides is not None:
        for guide in visual_guides:
            if guide.get("x", None) is not None:
                plt.axhline(guide["x"], color=guide.get("color", "gray"))
            if guide.get("y", None) is not None:
                plt.axvline(guide["y"], color=guide.get("color", "gray"))
    plt.plot(resource_df.timestamp, resource_df.resource_usage)
    plt.suptitle(title)
    plt.title(resource_df.timestamp.min().strftime("%Y-%m-%d"), x=0, ha="left")
    plt.gca().xaxis.set_major_locator(MinuteLocator(30))
    # reformat the times on the x axis to HH:MM
    plt.gca().xaxis.set_major_formatter(DateFormatter("%H:%M"))
    plt.xlabel("Time")
    plt.ylabel(y_label)
    fig.savefig(output_path)
    plt.close(fig)


def write_resource_usage(loading_time_df, resource_df, messages, output_path, log_path):
    report_md = "## Application metrics\n"
    report_md += "### Loading times\n"

    if len(messages) == 0:
        report_md += "No loading times found.\n"
    else:
        loading_time_summary = loading_time_df.loading_time.describe()

        report_md += (
            f"**Average loading time**: {loading_time_summary['mean']:.2f} seconds\n\n"
        )
        report_md += (
            f"**Median loading time**: {loading_time_summary['50%']:.2f} seconds\n\n"
        )
        report_md += (
            f"**Max loading time**: {loading_time_summary['max']:.2f} seconds\n\n"
        )
        report_md += (
            f"**Min loading time**: {loading_time_summary['min']:.2f} seconds\n\n"
        )

        for message in messages:
            report_md += f"- {message}\n\n"

        abs_plot_path = plot_name(output_path, log_path, "loading-times")
        visual_guides = [
            {**status, "x": status["max"]}
            for status in LOADING_TIMES_STATUS_LIST
            if status.get("max", None) is not None
        ]
        _plot_resource_usage_over_time(
            loading_time_df.timestamp,
            loading_time_df.loading_time,
            "Mean loading times per minute",
            "Seconds",
            abs_plot_path,
            visual_guides=visual_guides,
        )
        plot_path = basename(abs_plot_path)
        report_md += f"![Loading times]({plot_path})\n\n"

    report_md += "### Resource usage\n"
    if len(resource_df) == 0:
        report_md += "No resource usage found in log.\n"
    else:
        report_md += f"**Average CPU usage**: {resource_df.cpu_usage.mean():.2f}%\n\n"

        visual_guides = [
            {"x": 25, "color": "green"},
            {"x": 50, "color": "yellow"},
            {"x": 75, "color": "orange"},
            {"x": 100, "color": "red"},
        ]
        abs_plot_path = plot_name(output_path, log_path, "cpu-usage")
        _plot_resource_usage_over_time(
            resource_df.timestamp,
            resource_df.cpu_usage,
            "Mean CPU usage per minute",
            "Percentage",
            abs_plot_path,
            visual_guides=visual_guides,
        )
        plot_path = basename(abs_plot_path)
        report_md += f"![CPU usage]({plot_path})\n\n"

        report_md += (
            f"**Average Memory usage**: {resource_df['memory_usage'].mean():.2f}%\n\n"
        )

        abs_plot_path = plot_name(output_path, log_path, "memory-usage")
        _plot_resource_usage_over_time(
            resource_df.timestamp,
            resource_df["memory_usage"],
            "Mean Memory usage per minute",
            "Percentage",
            abs_plot_path,
            visual_guides=visual_guides,
        )
        plot_path = basename(abs_plot_path)
        report_md += f"![Memory usage]({plot_path})\n\n"

        report_md += f"**Average free storage usage**: {resource_df['free_disk_storage'].mean():.2f}%\n\n"

        abs_plot_path = plot_name(output_path, log_path, "free_disk_storage")
        _plot_resource_usage_over_time(
            resource_df.timestamp,
            resource_df["free_disk_storage"],
            "Mean free disk storage usage per minute",
            "Percentage",
            abs_plot_path,
            visual_guides=visual_guides,
        )
        plot_path = basename(abs_plot_path)
        report_md += f"![Free disk storage]({plot_path})\n\n"

    return report_md


def plot_name(output_path, log_path, suffix, ext="png"):
    return os.path.join(
        dirname(output_path), basename(log_path).replace(".log", f"-{suffix}.{ext}")
    )


def create_report(log_path, output_path=None):
    if output_path is None:
        output_path = _log_path_to_report_path(log_path)
    logs = parse_gunicorn_logs(log_path)
    error_df = parse_errors(logs)
    warning_df = parse_warnings(logs)
    loading_time_df = parse_loading_times(logs)
    resource_df = parse_resources(logs)
    report_md = _write_heading()
    report_md += _write_summary(log_path, logs, error_df, warning_df)
    report_md += _write_errors(error_df)
    report_md += _write_warnings(warning_df)
    console_messages, markdown_messages = _get_loading_time_status(loading_time_df)

    report_md += write_resource_usage(
        loading_time_df, resource_df, markdown_messages, output_path, log_path
    )

    with open(output_path, "w") as f:
        f.write(report_md)

    abs_output_path = abspath(output_path)
    messages_to_print = [
        f"{bold('Log summary')}:",
        f"{bold('Number of errors')}: {len(error_df)}",
        f"{bold('Number of warnings')}: {len(warning_df)}",
        f"{bold('Loading times')}:",
        *console_messages,
    ]

    if len(resource_df) > 0:
        messages_to_print += [
            f"{bold('Mean CPU usage')}: {resource_df.cpu_usage.mean():.2f}%",
            f"{bold('Mean Memory usage')}: {resource_df['memory_usage'].mean():.2f}%",
        ]
    messages_to_print += [
        f"Detailed report written to file://{abs_output_path} ."
        "If you run this in PyCharm on MacOS, it will open automatically.",
    ]

    if platform.system() == "Darwin":
        try:
            os.system(f'open -a "PyCharm.app" {abs_output_path}')
        except Exception as e:
            print(f"Could not open report in PyCharm: {e}")

    return messages_to_print


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create a report from a log file generated by gunicorn."
    )
    parser.add_argument(
        "log_path",
        type=str,
        help="The path to the log file.",
    )
    parser.add_argument(
        "--output_path",
        type=str,
        default=None,
        help="The path to the output file.",
    )
    args = parser.parse_args()
    create_report(args.log_path, args.output_path)
