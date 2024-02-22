import pandas as pd
from flask import render_template

TEMPLATE_NAME = "dashboard_resources.html"


def parse_label(row):
    if row.type == "cpu_usage":
        return f"{row.y_unit} % of total CPU usage"
    if row.type == "ram_usage":
        return f"{row.y_unit} % of total RAM"
    if row.type == "free_disk_space":
        return f"{int(row.y_unit)} GB free disk space"
    if row.type == "median_response_time":
        return f"{round(row.y_unit, 2)} ms median response time within a minute"
    if row.type == "n_responses":
        return f"{int(row.y_unit)} page loads within a minute"
    if row.type == "total_working":
        return f"{int(row.y_unit)} total working participants"
    return row.y_unit


def report_resource_use():
    from psynet.experiment import ExperimentStatus

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
    resources_df["timestamp"] = resources_df.index

    resources_df["free_disk_space"] = (
        100
        - (resources_df["free_disk_space"] / resources_df["free_disk_space"].max())
        * 100
    )
    resources_df["median_response_time"] = (
        resources_df["median_response_time"]
        / resources_df["median_response_time"].max()
    ) * 100
    resources_df["n_responses"] = (
        resources_df["n_responses"] / resources_df["n_responses"].max()
    ) * 100
    resources_df["total_working"] = (
        resources_df["total_working"] / resources_df["total_working"].max()
    ) * 100

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
    now = pd.to_datetime("now")
    earliest = norm_resources_df["timestamp"].min()

    # if same day
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

    norm_resources_df["type"] = norm_resources_df["type"].map(
        {
            "cpu_usage": "CPU usage (%)",
            "ram_usage": "RAM usage (%)",
            "free_disk_space": "Used disk space compared to min (%)",
            "median_response_time": "Median page loading time (%)",
            "n_responses": "Number of page loads",
            "total_working": "Total working participants",
        }
    )

    return render_template(
        TEMPLATE_NAME,
        title=title,
        html="",
        data=norm_resources_df.to_dict(orient="records"),
    )
