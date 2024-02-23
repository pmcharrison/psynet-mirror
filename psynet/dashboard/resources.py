import pandas as pd
from flask import render_template


def report_resource_use():
    from psynet.experiment import ExperimentStatus

    TEMPLATE_NAME = "dashboard_resources.html"
    title = "Resource usage"
    data = ExperimentStatus.query.order_by(ExperimentStatus.id.desc()).all()
    if len(data) == 0:
        return render_template(
            TEMPLATE_NAME,
            title=title,
            html="""
            <div class="alert alert-danger" role="alert">
                Wait at least 1 minute to see the first data.
            </div>
            """,
        )
    df_raw = pd.DataFrame([row.to_dict() for row in data])
    df_raw.drop(columns=["extra_info", "id"], inplace=True)

    df_normalized = normalize_resource_use(df_raw)

    df_plot = df_normalized.melt(id_vars="timestamp", var_name="type", value_name="y")
    df_plot = add_raw_values(df_plot, df_raw)
    df_plot["label"] = df_plot.apply(parse_label, axis=1)
    df_plot = parse_time_str(df_plot)
    df_plot = rename_type(df_plot)

    data = df_plot.to_dict(orient="records")

    return render_template(
        TEMPLATE_NAME,
        title=title,
        html="",
        data=data,
    )


def parse_label(row):
    match row.type:
        case "cpu_usage":
            return f"{row.y_unit} % of total CPU usage"
        case "ram_usage":
            return f"{row.y_unit} % of total RAM"
        case "free_disk_space":
            return f"{int(row.y_unit)} GB free disk space"
        case "median_response_time":
            return f"{round(row.y_unit, 2)} ms median response time within a minute"
        case "requests_per_minute":
            return f"{int(row.y_unit)} page loads within a minute"
        case "n_working_participants":
            return f"{int(row.y_unit)} total working participants"
        case _:
            return row.y_unit


def max_100(x):
    return (x / x.max()) * 100


def normalize_resource_use(_resources_df):
    resources_df = _resources_df.copy()
    resources_df["timestamp"] = resources_df.index
    resources_df["free_disk_space"] = 100 - max_100(resources_df["free_disk_space"])
    resources_df["median_response_time"] = max_100(resources_df["median_response_time"])
    resources_df["requests_per_minute"] = max_100(resources_df["requests_per_minute"])
    resources_df["n_working_participants"] = max_100(
        resources_df["n_working_participants"]
    )
    return resources_df


def add_raw_values(df_plot, df_raw):
    df_raw_long = df_raw.melt(id_vars="timestamp", var_name="type", value_name="y")
    df_plot["y_unit"] = df_raw_long["y"]
    df_plot["x"] = df_plot["timestamp"].astype(int)
    df_plot["timestamp"] = df_raw_long["timestamp"]
    df_plot.dropna(inplace=True)
    return df_plot


def parse_time_str(norm_resources_df):
    now = pd.to_datetime("now")
    earliest = norm_resources_df["timestamp"].min()

    if now.day == earliest.day:
        date_format = "%H:%M"
    elif now.year == earliest.year:
        date_format = "%m-%d %H:%M"
    else:
        date_format = "%Y-%m-%d %H:%M"

    norm_resources_df["timestamp"] = [
        str(ts)
        for ts in pd.to_datetime(norm_resources_df["timestamp"], unit="s").dt.strftime(
            date_format
        )
    ]
    return norm_resources_df


def rename_type(norm_resources_df):
    norm_resources_df["type"] = norm_resources_df["type"].map(
        {
            "cpu_usage": "CPU usage (%)",
            "ram_usage": "RAM usage (%)",
            "free_disk_space": "Used disk space compared to min (%)",
            "median_response_time": "Median page loading time (%)",
            "requests_per_minute": "Number of page loads",
            "n_working_participants": "Total working participants",
        }
    )
    return norm_resources_df
