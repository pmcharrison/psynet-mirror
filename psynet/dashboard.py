import json
from math import ceil

import pandas as pd
from flask import render_template

from psynet.experiment import get_and_load_config
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


def make_status_card(title, body, status="info"):
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
    if not pd.isna(entrant.terminated_at):
        return "Terminated"
    elif not pd.isna(entrant.completed_at):
        return "Completed"
    else:
        return "Working"


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
    entry_df["duration"] = entry_df.lucid_last_date - entry_df.lucid_entry_date

    # Status; used in pandas query, linter does not recognize it
    completed_status = BaseLucidRecruiter.COMPLETED  # noqa: F841
    terminated_status = BaseLucidRecruiter.TERMINATED  # noqa: F841
    prescreened_status = BaseLucidRecruiter.PRESCREENED  # noqa: F841

    body = """
        <script src="https://cdn.jsdelivr.net/npm/masonry-layout@4.2.2/dist/masonry.pkgd.min.js" integrity="sha384-GNFwBvfVxBkLMJpYMOABq3c+d3KnQxudP/mGPkzpZSTYykLBNsZEnG2D9G/X/+7D" crossorigin="anonymous" async></script>
        <div class="row mb-2" data-masonry='{"percentPosition": true }'>
        """

    entry_df["psynet_status"] = entry_df.apply(get_entrant_psynet_status, axis=1)

    entrant_info = [
        {
            "status": "Working",
            "n": entry_df.query("psynet_status == 'Working'").shape[0],
            "color": "blue",
        },
        {
            "status": "Terminated",
            "n": entry_df.query("psynet_status == 'Terminated'").shape[0],
            "color": "red",
        },
        {
            "status": "Completed",
            "n": entry_df.query("psynet_status == 'Completed'").shape[0],
            "color": "green",
        },
    ]
    status_items = []
    for entrant in entrant_info:
        status_items.append(
            render_msg(entrant["status"], entrant["n"], "", entrant["color"])
        )
    body += make_card(
        "PsyNet status", "Inferred status from Participant RID table.", status_items
    )

    lucid_entry_df = entry_df.loc[~pd.isna(entry_df.lucid_status)]
    total_entrants = len(lucid_entry_df)
    total_after_prescreen = len(
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
            "status": "After prescreen",
            "n": total_after_prescreen,
            "color": "blue",
        },
        {
            "status": "Completed",
            "n": total_completes,
            "color": "green",
        },
    ]
    status_items = []
    for entrant in entrant_info:
        status_items.append(
            render_msg(entrant["status"], entrant["n"], "", entrant["color"])
        )

    body += make_card("Lucid status", "Respondent activity from Lucid.", status_items)

    # Client code breakdown (after prescreen):
    terminated_df = entry_df.query("lucid_status == @terminated_status")
    n_lucid_terminated = len(terminated_df)
    n_psynet_terminated = len(entry_df.query("psynet_status == 'Terminated'"))
    client_code_body = "Client codes are more detailed status codes for all participants who passed the initial qualifications."
    if n_lucid_terminated != n_psynet_terminated:
        client_code_body += f"<br><span style='font-weight:bold; color:red'>Detected a mismatch in terminated participants in Psynet (n = {n_psynet_terminated}) and Lucid (n = {n_lucid_terminated}).</span>"

    completes_df = entry_df.query("lucid_status == @completed_status")
    n_lucid_completed = len(completes_df)
    n_psynet_completed = len(entry_df.query("psynet_status == 'Completed'"))
    if n_lucid_completed != n_psynet_completed:
        client_code_body += f"<br><span style='font-weight:bold; color:red'>Detected a mismatch in completed participants in Psynet (n = {n_psynet_completed}) and Lucid (n = {n_lucid_completed}).</span>"

    body += make_card(
        "Lucid client codes", client_code_body, get_count_items(entry_df.lucid_status)
    )

    # Market place codes
    body += make_card(
        "Lucid marketplace codes",
        "Lucid market place codes for respondents.",
        get_count_items(entry_df.lucid_market_place_code),
    )

    # filter entries where termination_reason is not None
    body += make_card(
        "Termination reasons",
        "Reasons why participants were terminated from PsyNet.",
        get_count_items(entry_df.termination_reason),
    )

    if entry_df.shape[0] > 0:
        metrics = BaseLucidRecruiter.get_recruiter_metrics(entry_df)

        conversion_rate = metrics["conversion_rate"]
        if conversion_rate is not None:
            body += make_status_card(
                f"Conversion rate: {int(conversion_rate * 100)}%",
                "Percentage of completes of total people who passed the qualifications. Should be more than 10%.",
                "success" if conversion_rate > 0.1 else "danger",
            )

        dropoff_rate = metrics["drop_off_rate"]
        if dropoff_rate is not None:
            body += make_status_card(
                f"Dropoff rate: {int(dropoff_rate * 100)}%",
                "Percentage of participants not returned to the market place who passed the qualifications. Should be less than 20%.",
                "success" if dropoff_rate < 0.2 else "danger",
            )

        config = get_and_load_config()
        lucid_recruitment_config = json.loads(config.get("lucid_recruitment_config"))
        bid_incidence = lucid_recruitment_config["survey"]["BidIncidence"]
        incidence_rate = metrics["incidence_rate"]

        if incidence_rate is None:
            pass
        elif incidence_rate > bid_incidence / 100:
            body += make_status_card(
                f"Incidence rate: {int(incidence_rate * 100)}%",
                f"Percentage of screened out based on (custom) qualifications divided by total completes + screened out participants. Currently set to: {bid_incidence} %; consider reducing it to increase reach.",
                "success",
            )

        else:
            body += make_status_card(
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
                (completes_df.duration.dt.total_seconds() / 60).median().round()
            )
            title = f"Completion LOI: {completion_loi} minutes"
            body = f"Expected: {set_completion_loi} minutes"
            if completion_loi < set_completion_loi:
                body = f"{body}. Consider reducing the expected completion time."
                body += make_status_card(title, body, "warning")
            elif completion_loi > set_completion_loi:
                body = f"{body}. Consider increasing the expected completion time."
                body += make_status_card(title, body, "danger")
            else:
                body += make_status_card(title, body, "success")

        if len(terminated_df) > 0:
            termination_loi = int(
                (terminated_df.duration.dt.total_seconds() / 60).median().round()
            )
            if termination_loi < 1:
                body += make_status_card(
                    "Termination LOI", f"{termination_loi} minutes", "success"
                )
            else:
                body += make_status_card(
                    "Termination LOI", f"{termination_loi} minutes", "danger"
                )

        cpi = experiment.estimated_max_reward(wage_per_hour)
        pattern = "Error|In Screener"
        platform_faults = entry_df.lucid_market_place_code.str.contains(
            pattern, regex=True
        ).sum()
        estimated_epc = round(
            cpi * metrics["n_completes"] / (metrics["n_entrants"] - platform_faults), 2
        )

        body += make_status_card(
            f"Estimated EPC: {estimated_epc} €",
            f"Earnings per click. It's not entirely clear how it is calculated. It's basically the number of completes divided by the number of entrants multiplied by the CPI ({round(cpi, 2)} €). Make sure the value is high enough.",
            "info",
        )
    body += "</div>"

    return render_template(
        TEMPLATE_NAME,
        title=title,
        html=body,
    )
