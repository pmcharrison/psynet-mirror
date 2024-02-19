import json
from math import ceil

import pandas as pd
from flask import render_template

from psynet.experiment import get_and_load_config
from psynet.participant import Participant
from psynet.recruiters import BaseLucidRecruiter, LucidRID

TEMPLATE_NAME = "dashboard_custom.html"


def render_msg(title, msg, details, color):
    return f"<span style='color:{color}'><span style='font-weight:bold'>{title}</span>: {msg}</span> {details}"


def create_accordion(items, id):
    out = '<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js" integrity="sha384-C6RzsynM9kWDrMNeT87bh95OGNyZPhcTNXj1NW7RuBCsyN/o0jlpcV8Qyq46cDfL" crossorigin="anonymous"></script>'
    out += f'<div class="accordion" id="{id}">'
    for i, item in enumerate(items.items()):
        key, value = item
        out += f"""
            <div class="accordion-item">
                <h2 class="accordion-header" id="heading-{id}-{i}">
                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-{id}-{i}" aria-expanded="false" aria-controls="collapse-{id}-{i}">
                        {key}
                    </button>
                </h2>
                <div id="collapse-{id}-{i}" class="accordion-collapse collapse" aria-labelledby="heading-{id}-{i}" data-bs-parent="#{id}">
                    <div class="accordion-body">
                        {value}
                    </div>
                </div>
            </div>
        """
    out += "</div>"
    return out


def make_card(title, body, items):
    out = f"""
    <div class="col-4">
    <div class="card mb-2" style="width: 100%;">
        <div class="card-body">
            <h5 class="card-title">{title}</h5>
            <p class="card-text">{body}</p>
        </div>
        <ul class="list-group list-group-flush">
    """
    for item in items:
        out += f"""<li class="list-group-item">{item}</li>"""

    out += """
        </ul>
    </div>
    </div>
    """
    return out


def _prepare_viz(cmd, id_name):
    return f"""
    <div id="{id_name}"></div>
    <script>
    document.addEventListener("DOMContentLoaded", function(e)  {{
        {cmd}
    }});
    </script>
    """


def make_histogram(
    id_name, type2color: dict, data: list, margin: dict = None, n_bins=40
):
    if margin is None:
        margin = {"top": 10, "right": 30, "bottom": 30, "left": 40}
    assert ["bottom", "left", "right", "top"] == sorted(margin), "Got: " + str(margin)
    return _prepare_viz(
        f"""histogram("{id_name}", {data}, {margin}, {n_bins}, {type2color});""",
        id_name,
    )


def make_scatterplot(
    id_name, data: list, x_label: str, y_label: str, margin: dict = None
):
    if margin is None:
        margin = {"top": 10, "right": 30, "bottom": 30, "left": 40}
    assert ["bottom", "left", "right", "top"] == sorted(margin), "Got: " + str(margin)
    return _prepare_viz(
        f"""scatter("{id_name}", {data}, {margin}, "{x_label}", "{y_label}");""",
        id_name,
    )


def make_status_card(title, body, status="info", border=False):
    if status == "success":
        bg = "bg-success"
    elif status == "danger":
        bg = "bg-danger"
    elif status == "warning":
        bg = "bg-warning"
    elif status == "info":
        bg = ""
    else:
        raise ValueError(f"Unknown status: {status}")
    if bg != "":
        bg = f"{bg} text-white"

    if border:
        bg = f" border-{status} text-{status}"
    return f"""
    <div class="col-4">
    <div class="card mb-2 {bg}" style="width: 100%;">
        <div class="card-body">
            <h5 class="card-title">{title}</h5>
            <p class="card-text">{body}</p>
        </div>
    </div>
    </div>
    """


def trialmaker_exists(trialmaker_id):
    from dallinger.experiment_server.experiment_server import Experiment, session

    exp = Experiment(session)
    return trialmaker_id in exp.timeline.modules


def get_trialmaker(trialmaker_id):
    from dallinger.experiment_server.experiment_server import Experiment, session

    exp = Experiment(session)
    return exp.timeline.modules[trialmaker_id]


status2color = {
    "finished": "green",
    "failed": "red",
    "rejected": "orange",
    "working": "blue",
}


def get_count_items(series):
    count = series.value_counts()
    items = []
    for label, count in zip(count.index, count.values):
        items.append(render_msg(label, count, "", "black"))
    return items


def get_entrant_psynet_status(entrant):
    if entrant.lucid_status == BaseLucidRecruiter.PRESCREENED:
        return "Marketplace codes"
    elif not pd.isna(entrant.terminated_at):
        return "Terminated"
    elif not pd.isna(entrant.completed_at):
        return "Completed"
    else:
        return "Working"


def entrant_info_to_status_items(entrant_info):
    status_items = []
    for entrant in entrant_info:
        status_items.append(
            render_msg(entrant["status"], entrant["n"], "", entrant["color"])
        )
    return status_items


def compute_lucid_duration(row):
    if not pd.isna(row.lucid_entry_date):
        return row.lucid_last_date - row.lucid_entry_date
    elif row.registered_at > row.lucid_last_date:
        return row.registered_at - row.lucid_last_date
    else:
        return pd.NaT


def report_lucid():
    from psynet.experiment import get_experiment

    experiment = get_experiment()
    title = "Lucid"
    if not issubclass(experiment.recruiter.__class__, BaseLucidRecruiter):
        return render_template(
            TEMPLATE_NAME,
            title=title,
            html="""
                <div class="alert alert-danger" role="alert">
                    This experiment is not using Lucid as a recruiter.
                </div>
            """,
        )
    all_entrants = LucidRID.query.all()
    rid2participant_id = {
        participant.worker_id: participant.id for participant in Participant.query.all()
    }

    if len(all_entrants) == 0:
        return render_template(
            TEMPLATE_NAME,
            title=title,
            html="""
                <div class="alert alert-primary" role="alert">
                    No participants entered the experiment.
                </div>
            """,
        )

    entry_df = pd.DataFrame([entrant.to_dict() for entrant in all_entrants])
    entry_df.lucid_entry_date = pd.to_datetime(
        entry_df.lucid_entry_date, format="mixed"
    )
    entry_df.lucid_last_date = pd.to_datetime(entry_df.lucid_last_date, format="mixed")
    entry_df["lucid_duration"] = (
        entry_df.apply(compute_lucid_duration, axis=1)
    ).dt.total_seconds() / 60

    def get_psynet_finished(row):
        if not pd.isna(row.terminated_at):
            return row.terminated_at
        elif not pd.isna(row.completed_at):
            return row.completed_at
        else:
            return None

    entry_df["psynet_finished"] = entry_df.apply(get_psynet_finished, axis=1)
    entry_df["psynet_duration"] = (
        entry_df.psynet_finished - entry_df.registered_at
    ).dt.total_seconds() / 60

    # Status; used in pandas query, linter does not recognize it
    completed_status = BaseLucidRecruiter.COMPLETED  # noqa: F841
    terminated_status = BaseLucidRecruiter.TERMINATED  # noqa: F841
    prescreened_status = BaseLucidRecruiter.PRESCREENED  # noqa: F841
    in_survey_status = BaseLucidRecruiter.UNRETURNED  # noqa: F841

    body = """
        <script src="https://cdn.jsdelivr.net/npm/masonry-layout@4.2.2/dist/masonry.pkgd.min.js" integrity="sha384-GNFwBvfVxBkLMJpYMOABq3c+d3KnQxudP/mGPkzpZSTYykLBNsZEnG2D9G/X/+7D" crossorigin="anonymous" async></script>
        """
    survey_number = experiment.recruiter.current_survey_number()
    title += f" (Survey {survey_number})"

    body += f"""
        <a class="btn btn-primary" role="button" href="https://marketplace.samplicio.us/fulcrum/next/surveys/{survey_number}/reports" target="_blank">Reports</a>
        <a class="btn btn-secondary" role="button" href="https://marketplace.samplicio.us/fulcrum/next/surveys/{survey_number}/quotas" target="_blank">Quota</a>
        <a class="btn btn-secondary" role="button" href="https://marketplace.samplicio.us/fulcrum/next/surveys/{survey_number}/details" target="_blank">Details</a>
    """

    entry_df["psynet_status"] = entry_df.apply(get_entrant_psynet_status, axis=1)

    entrant_info = [
        {
            "status": "Working",
            "n": entry_df.query("psynet_status == 'Working'").shape[0],
            "color": "black",
        },
        {
            "status": "Terminated",
            "n": entry_df.query("psynet_status == 'Terminated'").shape[0],
            "color": "black",
        },
        {
            "status": "Completed",
            "n": entry_df.query("psynet_status == 'Completed'").shape[0],
            "color": "green",
        },
    ]

    items = entrant_info_to_status_items(entrant_info)

    items[
        0
    ] += "<br>The total number of working participants or participants who dropped out (e.g., close window)."
    items[1] += "<br>The total number of respondents send to termination by PsyNet."
    items[2] += "<br>The total number of complete participants."
    psynet_status = make_card(
        title="Status", body="Inferred status from Participant RID table.", items=items
    )
    psynet_terminated_df = entry_df.query("psynet_status == 'Terminated'")

    n_psynet_terminated = len(psynet_terminated_df)

    psynet_termination_reason = make_card(
        "Termination reasons",
        f"Reasons why participants were terminated from PsyNet (n = {n_psynet_terminated}):",
        get_count_items(entry_df.termination_reason),
    )

    body += (
        "<h3>PsyNet</h3>"
        """<div class="row mb-2" data-masonry='{"percentPosition": true }'>"""
        + psynet_status
        + psynet_termination_reason
        + "</div>"
    )

    lucid_entry_df = entry_df.loc[~pd.isna(entry_df.lucid_status)]
    total_entrants = len(lucid_entry_df)
    total_after_qualifications = len(
        lucid_entry_df.query("lucid_status != @prescreened_status")
    )
    total_completes = len(lucid_entry_df.query("lucid_status == @completed_status"))

    # Entrant breakdown
    entrant_info = [
        {
            "status": "Total entrants",
            "n": total_entrants,
            "color": "black",
        },
        {
            "status": "After qualifications",
            "n": total_after_qualifications,
            "color": "black",
        },
        {
            "status": "Completed",
            "n": total_completes,
            "color": "green",
        },
    ]
    items = entrant_info_to_status_items(entrant_info)

    items[0] += "<br>The total number of respondents clicking on the survey link."
    items[1] += "<br>The total number of respondents who passed the qualifications."
    items[
        2
    ] += "<br>The total number of respondents who are marked as complete by Lucid."

    lucid_responent_activity = make_card(
        title="Respondent activity",
        body="Tells us how many people started the qualification, passed them and completed the experiment.",
        items=items,
    )

    # Client code breakdown (after prescreen):
    terminated_df = entry_df.query("lucid_status == @terminated_status")
    n_lucid_terminated = len(terminated_df)

    code_color_dict = {
        BaseLucidRecruiter.PRESCREENED: "black",
        BaseLucidRecruiter.UNRETURNED: "black",
        BaseLucidRecruiter.TERMINATED: "black",
        BaseLucidRecruiter.COMPLETED: "green",
    }
    entrant_info = [
        {
            "status": code,
            "n": len(lucid_entry_df.query("lucid_status == @code")),
            "color": color,
        }
        for code, color in code_color_dict.items()
    ]
    items = entrant_info_to_status_items(entrant_info)

    items[0] += (
        "<br>The total number of respondents who did not enter the experiment (e.g., not passsing the qualifications, "
        "marketplace error, rejection based on respondent quality score; see next card for breakdown)."
    )
    items[1] += (
        "<br>The total number of respondents who are doing the experiment or were not returned to the marketplace "
        "(e.g., closing the window)."
    )
    items[
        2
    ] += "<br>The total number of respondents who are marked as terminated in Lucid."
    items[
        3
    ] += "<br>The total number of respondents who are marked as complete in Lucid."
    n_psynet_working = len(entry_df.query("psynet_status == 'Working'"))
    n_lucid_working = len(lucid_entry_df.query("lucid_status == @in_survey_status"))
    if n_lucid_working != n_psynet_working:
        items[
            1
        ] += f"<br><span class='text-danger'>Detected a mismatch in working participants in Psynet (n = {n_psynet_working}) and Lucid (n = {n_lucid_working}).</span>"

    if n_lucid_terminated != n_psynet_terminated:
        items[
            2
        ] += f"<br><span class='text-danger'>Detected a mismatch in terminated participants in Psynet (n = {n_psynet_terminated}) and Lucid (n = {n_lucid_terminated}).</span>"

    completes_df = entry_df.query("lucid_status == @completed_status")
    n_lucid_completed = len(completes_df)
    n_psynet_completed = len(entry_df.query("psynet_status == 'Completed'"))
    if n_lucid_completed != n_psynet_completed:
        items[
            3
        ] += f"<br><span class='text-danger'>Detected a mismatch in completed participants in Psynet (n = {n_psynet_completed}) and Lucid (n = {n_lucid_completed}).</span>"

    lucid_client_codes = make_card(
        title="Client codes",
        body="A more detailed breakdown us about the status of respondents.",
        items=items,
    )

    # Market place codes
    lucid_market_place_codes = make_card(
        "Marketplace codes",
        "Lucid market place codes for respondents.",
        get_count_items(entry_df.lucid_market_place_code),
    )

    body += (
        "<h3>Lucid</h3>"
        """<div class="row mb-2" data-masonry='{"percentPosition": true }'>"""
        + lucid_responent_activity
        + lucid_client_codes
        + lucid_market_place_codes
        + "</div>"
    )

    if entry_df.shape[0] > 0:
        metrics = BaseLucidRecruiter.get_recruiter_metrics(entry_df)

        conversion_rate = metrics["conversion_rate"]
        lucid_conversion_rate = make_status_card(
            f"Conversion rate: {int(conversion_rate * 100)}%",
            "Percentage of completes of total people who passed the qualifications. Should be more than 10%.",
            "success" if conversion_rate > 0.1 else "danger",
        )

        dropoff_rate = metrics["drop_off_rate"]
        lucid_dropoff_rate = make_status_card(
            f"Dropoff rate: {int(dropoff_rate * 100)}%",
            "Percentage of participants not returned to the market place who passed the qualifications. Should be less than 20%.",
            "success" if dropoff_rate < 0.2 else "danger",
        )

        config = get_and_load_config()
        lucid_recruitment_config = json.loads(config.get("lucid_recruitment_config"))
        bid_incidence = lucid_recruitment_config["survey"]["BidIncidence"]
        incidence_rate = metrics["incidence_rate"]

        if incidence_rate >= bid_incidence / 100:
            lucid_incidence_rate = make_status_card(
                f"Incidence rate: {int(incidence_rate * 100)}%",
                f"Percentage of screened out based on (custom) qualifications divided by total completes + screened out participants. Currently set to: {bid_incidence} %; consider reducing it to increase reach.",
                "success",
            )
        else:
            lucid_incidence_rate = make_status_card(
                f"Incidence rate: {int(incidence_rate * 100)}%",
                f"Percentage of screened out based on (custom) qualifications divided by total completes + screened out participants. Currently set to: {bid_incidence} %, increase incidence rate.",
                "danger",
            )

        wage_per_hour = config.get("wage_per_hour")
        set_completion_loi = ceil(
            experiment.estimated_completion_time(wage_per_hour) / 60
        )

        if len(completes_df) > 0:
            completion_loi = int(
                (completes_df.lucid_duration.dt.total_seconds() / 60).median().round()
            )
            title = f"Completion LOI: {completion_loi} minutes"
            text = f"Expected: {set_completion_loi} minutes."

            data = []
            for _, row in completes_df.iterrows():
                participant_id = rid2participant_id.get(row.rid, "Not registered")
                data.append(
                    {
                        "rid": row.rid,
                        "pid": participant_id,
                        "reason": row.termination_reason
                        if not pd.isna(row.termination_reason)
                        else "n/a",
                        "lucid_duration": row.lucid_duration
                        if not pd.isna(row.lucid_duration)
                        else "n/a",
                        "psynet_duration": row.psynet_duration
                        if not pd.isna(row.psynet_duration)
                        else "n/a",
                        "code": row.lucid_status
                        if not pd.isna(row.lucid_status)
                        else "n/a",
                        "type": "Lucid",
                        "value": row.lucid_duration
                        if not pd.isna(row.lucid_status)
                        else "n/a",
                    }
                )
            type2color = {"Lucid": "black"}
            histogram = make_histogram("termination_loi", type2color, data)
            if completion_loi < set_completion_loi:
                text += "Consider reducing the expected completion time." + histogram
                lucid_completion_loi = make_status_card(title, text, "warning", True)
            elif completion_loi > set_completion_loi:
                text += "Consider increasing the expected completion time." + histogram
                lucid_completion_loi = make_status_card(title, text, "danger", True)
            else:
                lucid_completion_loi = make_status_card(
                    title, text + histogram, "success", True
                )

            data = [
                {**d, "x": d["lucid_duration"], "y": d["psynet_duration"]} for d in data
            ]
        else:
            lucid_completion_loi = make_status_card(
                "Completion LOI", "No completes yet.", "info"
            )

        if len(terminated_df) > 0:
            lucid_termination_loi = int(terminated_df.lucid_duration.median().round())

            psynet_termination_loi = int(
                psynet_terminated_df.psynet_duration.median().round()
            )
            data = []
            for _, row in terminated_df.iterrows():
                participant_id = rid2participant_id.get(row.rid, "Not registered")
                if not pd.isna(row.lucid_duration):
                    data.append(
                        {
                            "rid": row.rid,
                            "pid": participant_id,
                            "reason": row.termination_reason
                            if not pd.isna(row.termination_reason)
                            else "n/a",
                            "lucid_duration": row.lucid_duration
                            if not pd.isna(row.lucid_duration)
                            else "n/a",
                            "psynet_duration": row.psynet_duration
                            if not pd.isna(row.psynet_duration)
                            else "n/a",
                            "code": row.lucid_status
                            if not pd.isna(row.lucid_status)
                            else "n/a",
                            "type": "Lucid",
                            "value": row.lucid_duration
                            if not pd.isna(row.lucid_status)
                            else "n/a",
                        }
                    )
            #
            # for _, row in psynet_terminated_df.iterrows():
            #     participant_id = rid2participant_id.get(row.rid, "Not registered")
            #     if not pd.isna(row.psynet_duration):
            #         data.append(
            #             {
            #                 "rid": row.rid,
            #                 "pid": participant_id,
            #                 "reason": row.termination_reason
            #                 if not pd.isna(row.termination_reason)
            #                 else "n/a",
            #                 "lucid_duration": row.lucid_duration
            #                 if not pd.isna(row.lucid_duration)
            #                 else "n/a",
            #                 "psynet_duration": row.psynet_duration
            #                 if not pd.isna(row.psynet_duration)
            #                 else "n/a",
            #                 "code": row.lucid_status
            #                 if not pd.isna(row.lucid_status)
            #                 else "n/a",
            #                 "type": "PsyNet",
            #                 "value": row.psynet_duration
            #                 if not pd.isna(row.lucid_status)
            #                 else "n/a",
            #             }
            #         )

            bad_loi = lucid_termination_loi > 1
            type2color = {"Lucid": "black"}
            histogram = make_histogram("termination_loi", type2color, data)
            lucid_termination_loi = make_status_card(
                title=f"Termination LOI: {lucid_termination_loi} minutes",
                body=(
                    "Median time from entry to termination. "
                    + "Should be a minute or less. "
                    + "Expected: "
                    + str(psynet_termination_loi)
                    + " minutes."
                    + histogram
                ),
                status="danger" if bad_loi else "success",
                border=True,
            )

            data = [
                {**d, "x": d["lucid_duration"], "y": d["psynet_duration"]} for d in data
            ]
            scatter_plot = make_scatterplot(
                "scatterplot", data, "LOI (Lucid)", "LOI (PsyNet)"
            )
            lucid_termination_loi += make_status_card(
                title="Termination LOI: PsyNet vs Lucid",
                body="Comparison of termination LOI between  PsyNet vs Lucid."
                + scatter_plot,
                status="danger" if bad_loi else "success",
                border=True,
            )

        else:
            lucid_termination_loi = make_status_card(
                "Termination LOI", "No terminated participants yet.", "info"
            )

        cpi = experiment.estimated_max_reward(wage_per_hour)
        pattern = "Error|In Screener"
        platform_faults = entry_df.lucid_market_place_code.str.contains(
            pattern, regex=True
        ).sum()
        estimated_epc = round(
            cpi * metrics["n_completes"] / (metrics["n_entrants"] - platform_faults), 2
        )

        lucid_epc = make_status_card(
            f"Estimated EPC: {estimated_epc} €",
            f"Earnings per click. It's not entirely clear how it is calculated. It's basically the number of completes divided by the number of entrants multiplied by the CPI ({round(cpi, 2)} €). Make sure the value is high enough.",
            "info",
        )

        body += (
            "<h3>Metrics</h3>"
            """<div class="row mb-2" data-masonry='{"percentPosition": true }'>"""
            + lucid_conversion_rate
            + lucid_dropoff_rate
            + lucid_incidence_rate
            + lucid_epc
            + "</div>"
        )

        body += (
            "<h3>Timing</h3>"
            """<div class="row mb-2" data-masonry='{"percentPosition": true }'>"""
            + lucid_completion_loi
            + lucid_termination_loi
            + "</div>"
        )

    return render_template(
        TEMPLATE_NAME,
        title=title,
        html=body,
    )
