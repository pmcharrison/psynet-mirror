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
    resources_df = pd.DataFrame([row.to_dict() for row in data])
    resources_df.drop(columns=["meta", "id"], inplace=True)
    resource_df_copy = resources_df.copy()
    resources_df = normalize_resource_use(resources_df)

    norm_resources_df = resources_df.melt(
        id_vars="timestamp", var_name="type", value_name="y"
    )
    resources_df = resource_df_copy.melt(
        id_vars="timestamp", var_name="type", value_name="y"
    )
    norm_resources_df["y_unit"] = resources_df["y"]
    norm_resources_df["x"] = norm_resources_df["timestamp"].astype(int)
    norm_resources_df["timestamp"] = resources_df["timestamp"]
    norm_resources_df.dropna(inplace=True)

    norm_resources_df["label"] = norm_resources_df.apply(parse_label, axis=1)

    norm_resources_df = parse_time_str(norm_resources_df)

    norm_resources_df = rename_type(norm_resources_df)

    return render_template(
        TEMPLATE_NAME,
        title=title,
        html="",
        data=norm_resources_df.to_dict(orient="records"),
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
        case "total_working":
            return f"{int(row.y_unit)} total working participants"
        case _:
            return row.y_unit


def max_100(x):
    return (x / x.max()) * 100


def normalize_resource_use(resources_df):
    resources_df["timestamp"] = resources_df.index
    resources_df["free_disk_space"] = 100 - max_100(resources_df["free_disk_space"])
    resources_df["median_response_time"] = max_100(resources_df["median_response_time"])
    resources_df["requests_per_minute"] = max_100(resources_df["requests_per_minute"])
    resources_df["total_working"] = max_100(resources_df["total_working"])
    return resources_df


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
            "total_working": "Total working participants",
        }
    )
    return norm_resources_df
