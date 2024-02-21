import json
from datetime import datetime
from math import ceil

import pandas as pd
from flask import render_template

from psynet.experiment import get_and_load_config
from psynet.participant import Participant
from psynet.recruiters import BaseLucidRecruiter, LucidRID, LucidStatus
from psynet.timeline import Response

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
    <div style="min-height: 200px" id="{id_name}"></div>
    <script>
    document.addEventListener("DOMContentLoaded", function(e)  {{
        {cmd}
    }});
    </script>
    """


def make_histogram(
    id_name,
    type2color: dict,
    data: list,
    margin: dict = None,
    n_bins=40,
    tooltip="null",
    height="null",
):
    if margin is None:
        margin = {"top": 10, "right": 30, "bottom": 30, "left": 40}
    assert ["bottom", "left", "right", "top"] == sorted(margin), "Got: " + str(margin)
    return _prepare_viz(
        f"""histogram("{id_name}", {data}, {margin}, {n_bins}, {type2color}, {tooltip}, {height});""",
        id_name,
    )


def make_loi_histogram(id_name, data: list, margin: dict = None, n_bins=40):
    type2color = {"Lucid": "black"}
    tooltip = """
    d3.tip().attr('class', 'd3-tip fullscreen')
        .html(function (d) {
            let type = d[0].type;
            let title = `<h5>Bin: [${(d.x0).toFixed(2)}-${d.x1.toFixed(2)}], count: ${d.length} (${type})`;
            // button to close
            title += '<button type="button" class="btn-close" style="float:right" aria-label="Close" onclick="hideTooltips()"></button></h5>';
            let table = '<table class="table table-striped">';
            table += '<tr>';
            table += '<th>Participant ID</th>';
            table += '<th>RID</th>';
            table += '<th>Reason</th>';
            table += '<th>PsyNet duration</th>';
            table += '<th>Lucid duration</th>';
            table += '<th>Client code</th>';
            table += '</tr>';
            d.forEach(function (bin) {
                table += '<tr>';
                table += `<td>${bin.pid}</td>`;
                table += `<td>${bin.rid}</td>`;
                table += `<td>${bin.reason}</td>`;
                table += `<td>${toTwoDecimals(bin.psynet_duration)}</td>`;
                table += `<td>${toTwoDecimals(bin.lucid_duration)}</td>`;
                table += `<td>${bin.code}</td>`;
                table += '</tr>';
            });
            table += '</table>';
            return '<div class="container">' + title + table + "</div>";
        })
    """
    return make_histogram(id_name, type2color, data, margin, n_bins, tooltip)


def make_response_histogram(
    id_name, type2color: dict, data: list, margin: dict = None, n_bins=40
):
    tooltip = """
        d3.tip().attr('class', 'd3-tip fullscreen')
            .html(function (d) {
                let type = d[0].type;
                let title = `<h5>${d.length} participants (${type}) did ${(d.x0).toFixed(0)} pages`;
                // button to close
                title += '<button type="button" class="btn-close" style="float:right" aria-label="Close" onclick="hideTooltips()"></button></h5>';
                let table = '<table class="table table-striped">';
                table += '<tr>';
                table += '<th>Participant ID</th>';
                table += '<th>RID</th>';
                table += '<th>Reason</th>';
                table += '</tr>';
                d.forEach(function (bin) {
                    table += '<tr>';
                    table += `<td>${bin.participant_id}</td>`;
                    table += `<td>${bin.rid}</td>`;
                    table += `<td>${bin.reason}</td>`;
                    table += '</tr>';
                });
                table += '</table>';
                return '<div class="container">' + title + table + "<div>";
            })
        """
    height = 500
    return make_histogram(id_name, type2color, data, margin, n_bins, tooltip, height)


def make_scatterplot(
    id_name,
    data: list,
    x_label: str,
    y_label: str,
    margin: dict = None,
    tooltip: str = "null",
):
    if margin is None:
        margin = {"top": 10, "right": 30, "bottom": 30, "left": 40}
    assert ["bottom", "left", "right", "top"] == sorted(margin), "Got: " + str(margin)

    return _prepare_viz(
        f"""scatter("{id_name}", {data}, {margin}, "{x_label}", "{y_label}", {tooltip});""",
        id_name,
    )


def make_loi_scatterplot(
    id_name, data: list, x_label: str, y_label: str, margin: dict = None
):
    tooltip = """
    d3.tip().attr('class', 'd3-tip')
        .html(function (d) {
            return `Participant ${d.pid} (${d.rid}): ${d.reason}`;
        })
    """
    return make_scatterplot(id_name, data, x_label, y_label, margin, tooltip)


def make_status_card(title, body, status="info", border=False, col="col-4"):
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
    <div class="{col}">
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
    if entrant.lucid_status == BaseLucidRecruiter.MARKETPLACE_CODE:
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
    # elif row.registered_at > row.lucid_last_date:
    #     return row.registered_at - row.lucid_last_date
    else:
        return pd.NaT


def prepare_reconciliations(rids: [str], filename: str):
    return f"""
    <script>
    function getReconciliations() {{
      const content = {rids}.join('\\n');
      const file = new File([content], '{filename}', {{
          type: 'text/plain',
      }})
      const link = document.createElement('a')
      const url = URL.createObjectURL(file)
      link.href = url
      link.download = file.name
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }}
    </script>
    <br>
    <a class="btn btn-primary mt-2" onclick="getReconciliations()">Download reconciliations</a>
    """


def copy_to_clipboard(text: str):
    return f"""
    <script>
    function copyToClipboard() {{
      const el = document.createElement('textarea');
      el.value = `{text}`;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    }}
    </script>
    <br>
    <a class="btn btn-primary mt-2" onclick="copyToClipboard()">Copy compensation command</a>
    """


def get_psynet_finished(row):
    if not pd.isna(row.terminated_at):
        return row.terminated_at
    elif not pd.isna(row.completed_at):
        return row.completed_at
    else:
        return None


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

    survey_number = experiment.recruiter.current_survey_number()
    survey_sid = experiment.recruiter.current_survey_sid()
    title += f" (Survey {survey_number})"

    header = f"""
        <div class='mb-2'>
            <a class="btn btn-primary" role="button" href="https://marketplace.samplicio.us/fulcrum/next/surveys/{survey_number}/reports" target="_blank">Reports</a>
            <a class="btn btn-success" role="button" href="https://www.samplicio.us/fulcrum/SurveyQualifications.aspx?SID={survey_sid}" target="_blank">Qualifications</a>
            <a class="btn btn-danger" role="button" href="https://www.samplicio.us/fulcrum/Reconciliations.aspx?SurveySID={survey_sid}" target="_blank">Reconciliations</a>
            <a class="btn btn-secondary" role="button" href="https://marketplace.samplicio.us/fulcrum/next/surveys/{survey_number}/quotas" target="_blank">Quota</a>
            <a class="btn btn-secondary" role="button" href="https://marketplace.samplicio.us/fulcrum/next/surveys/{survey_number}/details" target="_blank">Details</a>
        </div>
        """
    query = LucidStatus.query.order_by(LucidStatus.id.desc())
    earnings_per_click = 0
    completion_loi = 0
    termination_loi = 0
    conversion_rate = 0
    dropoff_rate = 0
    incidence_rate = 0
    if query.count() > 0:
        last_status = query.first()

        # Set params
        earnings_per_click = last_status.earnings_per_click
        completion_loi = last_status.completion_loi
        termination_loi = last_status.termination_loi
        conversion_rate = last_status.conversion_rate
        dropoff_rate = last_status.drop_off_rate
        incidence_rate = last_status.incidence_rate

        status_name = last_status.status

        last_api_call = int(
            (datetime.now() - pd.to_datetime(last_status.creation_time)).seconds / 60
        )
        selectpicker = "<select id='status' name='status'>"
        for status in BaseLucidRecruiter.survey_codes:
            if status == "archived":
                background = "rgb(166, 172, 179)"
            elif status == "awarded":
                background = "rgb(255, 204, 93)"
            elif status == "live":
                background = "rgb(4, 191, 129)"
            elif status == "paused":
                background = "blue"
            elif status == "pending":
                background = "rgb(250, 62, 100)"
            else:
                background = "black"
            content = f"""<span style="background:{background}" class="badge rounded-pill">{status.capitalize()}</span>"""
            selectpicker += f"<option value='{status}' {'selected' if status == status_name else ''}  data-content='{content}'>{status}</option>"
        if status_name not in BaseLucidRecruiter.survey_codes:
            selectpicker += (
                f"<option value='{status_name}' selected >{status_name}</option>"
            )
        selectpicker += "</select>"

        cost_summary = (
            f"<strong>Cost</strong>: {last_status.cost} {last_status.currency}</br>"
        )
        if last_status.cost > 0:
            cost_summary += f"<strong>Payment per hour</strong>: {last_status.payment_per_hour}</br>"
            cost_summary += f"<strong>Cost per complete</strong>: {last_status.cost_per_survey}</br>"

        header += f"""
        <div class="alert alert-primary" role="alert">
            Last API call: {last_api_call} minutes ago.
        </div>
        <div class="row">
            <div class="col-4">
                <strong>Status</strong>: {selectpicker}</br>
            </div>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.1/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-iYQeCzEYFbKjA/T2uDLTpkwGzCiq6soy8tYaI1GyVh/UjpbCx/TYkiZhlZB6+fzT" crossorigin="anonymous">
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-select@1.14.0-beta3/dist/css/bootstrap-select.min.css">
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.1/dist/js/bootstrap.bundle.min.js" integrity="sha384-u1OknCvxWvY5kfmNBILK2hRnQC3Pr17a+RTT6rIHI7NnikvbZlHgTPOOmMi466C8" crossorigin="anonymous"></script>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap-select@1.14.0-beta3/dist/js/bootstrap-select.min.js"></script>
            <script>
            selectpicker = $('#status').selectpicker();
            document.getElementById('status').addEventListener('change', function(e) {{
                fetch(window.location.origin + '/change_lucid_status?status=' + e.target.value, {{
                    method: 'GET',
                    method: 'GET',
                    credentials: 'same-origin',
                    agent: null,
                    headers: {{
                        "Content-Type": "text/plain",
                        'Authorization': 'Basic ' + btoa('username:password'),
                    }},
                }})
            }})
            </script>
            <div class="col-4">
            <strong>Cost</strong>: {last_status.cost} {last_status.currency}</br>
            </div>
        """
        if last_status.last_complete_date:
            header += f"<div class='col-4'><strong>Last complete date</strong>: {last_status.last_complete_date}</div>"
        header += "</div>"
    if len(all_entrants) == 0:
        return render_template(
            TEMPLATE_NAME,
            title=title,
            html=f"""{header}
                <div class="alert alert-primary" role="alert">
                    No participants entered the experiment.
                </div>
            """,
        )

    entry_df = pd.DataFrame([entrant.to_dict() for entrant in all_entrants])
    participants = pd.DataFrame(
        [
            {"participant_id": participant.id, "rid": participant.worker_id}
            for participant in Participant.query.all()
        ]
    )
    entry_df = entry_df.merge(participants, left_on="rid", right_on="rid", how="left")
    entry_df.lucid_entry_date = pd.to_datetime(
        entry_df.lucid_entry_date, format="mixed"
    )
    entry_df.lucid_last_date = pd.to_datetime(entry_df.lucid_last_date, format="mixed")
    if len(entry_df) > 0:
        entry_df["lucid_duration"] = entry_df.apply(compute_lucid_duration, axis=1)
        entry_df["lucid_duration"] = entry_df.lucid_duration.apply(
            lambda t: t.total_seconds() / 60 if not pd.isna(t) else t
        )

    entry_df["psynet_finished"] = entry_df.apply(get_psynet_finished, axis=1)
    if len(entry_df) > 0:
        durations = []
        for _, row in entry_df.iterrows():
            try:
                durations.append(
                    (row.psynet_finished - row.registered_at).total_seconds() / 60
                )
            except Exception:
                durations.append(pd.NaT)
        entry_df["psynet_duration"] = durations
    # Status; used in pandas query, linter does not recognize it
    completed_status = BaseLucidRecruiter.COMPLETED  # noqa: F841
    terminated_status = BaseLucidRecruiter.TERMINATED  # noqa: F841
    prescreened_status = BaseLucidRecruiter.MARKETPLACE_CODE  # noqa: F841
    in_survey_status = BaseLucidRecruiter.IN_SURVEY  # noqa: F841

    body = f"""
        <script src="https://cdn.jsdelivr.net/npm/masonry-layout@4.2.2/dist/masonry.pkgd.min.js" integrity="sha384-GNFwBvfVxBkLMJpYMOABq3c+d3KnQxudP/mGPkzpZSTYykLBNsZEnG2D9G/X/+7D" crossorigin="anonymous" async></script>
        {header}
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
        BaseLucidRecruiter.MARKETPLACE_CODE: "black",
        BaseLucidRecruiter.IN_SURVEY: "black",
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
        items[1] += (
            "<br><span class='text-danger'>Detected a mismatch in working participants in Psynet (n = "
            f"{n_psynet_working}) and Lucid (n = {n_lucid_working}).</span>"
        )

    if n_lucid_terminated != n_psynet_terminated:
        items[2] += (
            "<br><span class='text-danger'>Detected a mismatch in terminated participants in Psynet (n = "
            f"{n_psynet_terminated}) and Lucid (n = {n_lucid_terminated}).</span>"
        )

    completes_df = entry_df.query("lucid_status == @completed_status")
    n_lucid_completed = len(completes_df)
    psynet_completes_df = entry_df.query("psynet_status == 'Completed'")
    n_psynet_completed = len(psynet_completes_df)
    if n_lucid_completed != n_psynet_completed:
        lucid_complete_rids = psynet_completes_df.rid.to_list()
        cmd = f"cap lucid compensate {survey_number} {','.join(lucid_complete_rids)}"
        items[3] += (
            "<br><span class='text-danger'>Detected a mismatch in completed participants in Psynet (n = "
            + f"{n_psynet_completed}) and Lucid (n = {n_lucid_completed}).</span>"
            + copy_to_clipboard(cmd)
        )

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
        lucid_conversion_rate = make_status_card(
            f"Conversion rate: {int(conversion_rate * 100)}%",
            "Percentage of completes of total people who passed the qualifications. Should be more than 10%.",
            "success" if conversion_rate > 0.1 else "danger",
        )

        lucid_dropoff_rate = make_status_card(
            f"Dropoff rate: {int(dropoff_rate * 100)}%",
            "Percentage of participants not returned to the market place who passed the qualifications. Should be less than 20%.",
            "success" if dropoff_rate < 0.2 else "danger",
        )

        config = get_and_load_config()
        lucid_recruitment_config = json.loads(config.get("lucid_recruitment_config"))
        bid_incidence = lucid_recruitment_config["survey"]["BidIncidence"]

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
            completion_title = f"Completion LOI: {completion_loi} minutes"
            text = f"Expected: {set_completion_loi} minutes."

            data = []
            for _, row in completes_df.iterrows():
                data.append(
                    {
                        "rid": row.rid,
                        "pid": row.participant_id
                        if not pd.isna(row.participant_id)
                        else "Not registered",
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
                        "value": row.psynet_duration
                        if not pd.isna(row.lucid_status)
                        else "n/a",
                    }
                )
            histogram = make_loi_histogram("completion_loi", data)
            if completion_loi < set_completion_loi:
                text += " Consider reducing the expected completion time." + histogram
                lucid_completion_loi = make_status_card(
                    completion_title, text, "warning", True
                )
            elif completion_loi > set_completion_loi:
                text += " Consider increasing the expected completion time." + histogram
                lucid_completion_loi = make_status_card(
                    completion_title, text, "danger", True
                )
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
            # termination_loi = int(terminated_df.lucid_duration.median().round())

            psynet_termination_loi = int(
                psynet_terminated_df.psynet_duration.median().round()
            )
            data = []
            for _, row in terminated_df.iterrows():
                if not pd.isna(row.lucid_duration):
                    data.append(
                        {
                            "rid": row.rid,
                            "pid": row.participant_id
                            if not pd.isna(row.participant_id)
                            else "Not registered",
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
            #     if not pd.isna(row.psynet_duration):
            #         data.append(
            #             {
            #                 "rid": row.rid,
            #                 "pid": row.participant_id,
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

            bad_loi = termination_loi > 1
            histogram = make_loi_histogram("termination_loi", data)
            termination_loi = make_status_card(
                title=f"Termination LOI: {termination_loi} minutes",
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
            scatter_plot = make_loi_scatterplot(
                "scatterplot", data, "LOI (Lucid)", "LOI (PsyNet)"
            )
            termination_loi += make_status_card(
                title="Termination LOI: PsyNet vs Lucid",
                body="Comparison of termination LOI between  PsyNet vs Lucid."
                + scatter_plot,
                status="danger" if bad_loi else "success",
                border=True,
            )

        else:
            termination_loi = make_status_card(
                "Termination LOI", "No terminated participants yet.", "info"
            )

        responses = Response.query.filter_by(failed=False).all()
        response_df = pd.DataFrame(
            [
                {
                    "question": response.question,
                    "participant_id": response.participant_id,
                    "answer": response.answer,
                }
                for response in responses
            ]
        )
        answer_counts = (
            response_df.groupby("participant_id").answer.count().reset_index()
        )
        answer_counts = answer_counts.merge(entry_df, on="participant_id", how="left")
        answer_counts["reason"] = answer_counts.termination_reason.apply(
            lambda r: r if not pd.isna(r) else "n/a"
        )
        answer_counts["value"] = answer_counts.answer
        answer_counts["type"] = answer_counts.psynet_status
        relevant_cols = ["value", "type", "participant_id", "rid", "reason"]
        answer_counts = answer_counts[relevant_cols]
        rids = answer_counts.rid.to_list()  # noqa: F841

        missing = terminated_df.query("rid not in @rids")[["rid", "termination_reason"]]
        missing = missing.merge(participants, on="rid", how="left")
        missing["participant_id"] = missing.participant_id.apply(
            lambda x: x if not pd.isna(x) else "Not registered"
        )
        missing["reason"] = missing.termination_reason.apply(
            lambda r: r if not pd.isna(r) else "n/a"
        )
        missing["value"] = 0
        missing["type"] = "Terminated"

        missing = missing[relevant_cols]
        answer_counts = pd.concat([answer_counts, missing])
        type2color = {"Completed": "green", "Terminated": "red", "Working": "blue"}

        n_bins = answer_counts.value.max()

        hist_plot = make_response_histogram(
            "answer_count",
            type2color,
            answer_counts.to_dict(orient="records"),
            n_bins=n_bins,
        )
        responses_per_participant = make_status_card(
            title="Responses per participant",
            body="Comparison of termination LOI between  PsyNet vs Lucid." + hist_plot,
            col="col-12",
        )

        # cpi = experiment.estimated_max_reward(wage_per_hour)
        # pattern = "Error|In Screener"
        # platform_faults = entry_df.lucid_market_place_code.str.contains(
        #     pattern, regex=True
        # ).sum()
        # estimated_epc = round(
        #     cpi * metrics["n_completes"] / (metrics["n_entrants"] - platform_faults), 2
        # )

        lucid_epc = make_status_card(
            f"EPC: {earnings_per_click} €",
            "Earnings per click = (CPI * completes) / system entrants. Make sure the value is high enough.",
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

        body += "<h3>Timing</h3>"
        body += responses_per_participant
        body += (
            """<div class="row mb-2" data-masonry='{"percentPosition": true }'>"""
            + lucid_completion_loi
            + termination_loi
            + "</div>"
        )

    return render_template(
        TEMPLATE_NAME,
        title=title,
        html=body,
    )
