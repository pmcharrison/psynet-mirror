import errno
import json
import os
import shutil
import sys

import click
import requests
from dallinger.command_line import data as dallinger_data
from dallinger.command_line import debug as dallinger_debug
from dallinger.command_line import deploy as dallinger_deploy
from dallinger.command_line import log as dallinger_log
from dallinger.command_line import sandbox as dallinger_sandbox
from dallinger.command_line import verify_id as dallinger_verify_id
from dallinger.models import (
    Info,
    Network,
    Node,
    Notification,
    Participant,
    Question,
    Transformation,
    Transmission,
    Vector,
)
from dallinger.utils import get_base_url
from yaspin import yaspin

from psynet import __version__

from .utils import (
    import_local_experiment,
    json_to_data_frame,
    model_name_to_snake_case,
    serialise,
)

FLAGS = set()


def clean_sys_modules():
    to_clear = [k for k in sys.modules if k.startswith("dallinger_experiment")]
    for key in to_clear:
        del sys.modules[key]


header = r"""
    ____             _   __     __
   / __ \_______  __/ | / /__  / /_
  / /_/ / ___/ / / /  |/ / _ \/ __/
 / ____(__  ) /_/ / /|  /  __/ /_
/_/   /____/\__, /_/ |_/\___/\__/
           /____/
                                 {:>8}

                Laboratory automation for
       the behavioral and social sciences.
""".format(
    f"v{__version__}"
)


@click.group()
@click.version_option(__version__, "--version", "-v", message="%(version)s")
def psynet():
    pass
    # 1 + 1
    # config = get_config()
    # if not config.ready:
    #     import pdb; pdb.set_trace()
    #     config.load()


### prepare ###
@psynet.command()
@click.option("--force", is_flag=True, help="Force override of cache.")
def prepare(force):
    """
    Prepares all stimulus sets defined in experiment.py,
    uploading all media files to Amazon S3.
    """
    FLAGS.add("prepare")
    if force:
        FLAGS.add("force")
    dallinger_log(f"Preparing stimulus sets{' (forced mode)' if force else ''}...")
    experiment_class = import_local_experiment().get("class")
    experiment_class.pre_deploy()
    clean_sys_modules()
    return experiment_class


### debug ###
@psynet.command()
@click.option("--verbose", is_flag=True, help="Verbose mode")
@click.option("--bot", is_flag=True, help="Use bot to complete experiment")
@click.option(
    "--proxy", default=None, help="Alternate port when opening browser windows"
)
@click.option(
    "--no-browsers",
    is_flag=True,
    help="Skip opening browsers",
)
@click.option("--force-prepare", is_flag=True, help="Force override of cache.")
@click.pass_context
def debug(ctx, verbose, bot, proxy, no_browsers, force_prepare):
    """
    Run the experiment locally.
    """
    dallinger_log(header)
    ctx.invoke(prepare, force=force_prepare)
    ctx.invoke(
        dallinger_debug, verbose=verbose, bot=bot, proxy=proxy, no_browsers=no_browsers
    )


### deploy ###
@psynet.command()
@click.option("--verbose", is_flag=True, help="Verbose mode")
@click.option("--app", default=None, help="Experiment id")
@click.option("--archive", default=None, help="Optional path to an experiment archive")
@click.option("--force-prepare", is_flag=True, help="Force override of cache.")
@click.pass_context
def deploy(ctx, verbose, app, archive, force_prepare):
    """
    Deploy app using Heroku to MTurk.
    """
    dallinger_log(header)
    ctx.invoke(prepare, force=force_prepare)
    ctx.invoke(dallinger_deploy, verbose=verbose, app=app, archive=archive)


### sandbox ###
@psynet.command()
@click.option("--verbose", is_flag=True, help="Verbose mode")
@click.option("--app", default=None, help="Experiment id")
@click.option("--archive", default=None, help="Optional path to an experiment archive")
@click.option("--force-prepare", is_flag=True, help="Force override of cache.")
@click.pass_context
def sandbox(ctx, verbose, app, archive, force_prepare):
    """
    Deploy app using Heroku to the MTurk Sandbox.
    """
    dallinger_log(header)
    ctx.invoke(prepare, force=force_prepare)
    ctx.invoke(dallinger_sandbox, verbose=verbose, app=app, archive=archive)


### estimate ###
@psynet.command()
@click.option(
    "--mode",
    default="both",
    type=click.Choice(["bonus", "time", "both"]),
    help="Type of result. Can be either 'bonus', 'time', or 'both'.",
)
def estimate(mode):
    """
    Estimate the maximum bonus for a participant and the time for the experiment to complete, respectively.
    """
    dallinger_log(header)
    experiment_class = import_local_experiment()["class"]
    experiment = setup_experiment_variables(experiment_class)
    if mode in ["bonus", "both"]:
        maximum_bonus = experiment_class.estimated_max_bonus(experiment.wage_per_hour)
        dallinger_log(
            f"Estimated maximum bonus for participant: ${round(maximum_bonus, 2)}."
        )
    if mode in ["time", "both"]:
        completion_time = experiment_class.estimated_completion_time(
            experiment.wage_per_hour
        )
        dallinger_log(
            f"Estimated time to complete experiment: {format_seconds(completion_time)}."
        )


def setup_experiment_variables(experiment_class):
    experiment = experiment_class()
    experiment.setup_experiment_variables()
    return experiment


### export ###
@psynet.command()
@click.option(
    "--app",
    default=None,
    required=True,
    callback=dallinger_verify_id,
    help="Experiment id",
)
@click.option("--local", is_flag=True, help="Export local data")
def export(app, local):
    """
    Export data from an experiment.

    The data is exported in three distinct formats into the 'data/data-<app>'
    directory of an experiment which has following structure:

    data/
    └── data-<app>/
        ├── csv/
        ├── db-snapshot/
        └── json/

    csv:
        Contains the experiment data in CSV format.
    db-snapshot:
        Contains the zip file generated by the default Dallinger export command.
    json:
        Contains the experiment data in JSON format.
    """
    dallinger_log(header)
    import_local_experiment()

    data_dir_path = os.path.join("data", f"data-{app}")
    create_export_dirs(data_dir_path)

    dallinger_log("Creating database snapshot.")
    dallinger_data.export(app, local=local)
    move_snapshot_file(data_dir_path, app)
    with yaspin(text="Completed.", color="green") as spinner:
        spinner.ok("✔")

    dallinger_log("Exporting 'json' and 'csv' files.")
    base_url = get_base_url() if local else f"https://dlgr-{app}.herokuapp.com"

    for dallinger_model in dallinger_models():
        class_name = dallinger_model.__name__

        result = requests.get(f"{base_url}/export", params={"class_name": class_name})
        json_data = json.loads(result.content.decode("utf8"))

        for model_name, json_data in json_data.items():
            base_filename = model_name_to_snake_case(model_name)
            print(f"Exporting {base_filename} data...")
            export_data(base_filename, data_dir_path, json_data)
    dallinger_log("Export completed.")


def dallinger_models():
    return [
        Info,
        Network,
        Node,
        Notification,
        Participant,
        Question,
        Transformation,
        Transmission,
        Vector,
    ]


def export_data(base_filename, data_dir_path, json_data):
    for file_format in ["json", "csv"]:
        with yaspin(text=f"Exporting '{file_format}'...", color="green") as spinner:
            base_filepath = os.path.join(data_dir_path, file_format, base_filename)
            with open(f"{base_filepath}.{file_format}", "w") as outfile:
                if file_format == "json":
                    json.dump(
                        json_data, outfile, indent=2, sort_keys=False, default=serialise
                    )
                elif file_format == "csv":
                    data_frame = json_to_data_frame(json_data)
                    data_frame.to_csv(outfile, index=False)
            spinner.ok("✔")


def create_export_dirs(data_dir_path):
    for file_format in ["csv", "db-snapshot", "json"]:
        export_path = os.path.join(data_dir_path, file_format)
        try:
            os.makedirs(export_path)
        except OSError as e:
            if e.errno != errno.EEXIST or not os.path.isdir(export_path):
                raise


def move_snapshot_file(data_dir_path, app):
    try:
        db_snapshot_path = os.path.join(data_dir_path, "db-snapshot")
        filename = f"{app}-data.zip"
        shutil.move(
            os.path.join("data", filename), os.path.join(db_snapshot_path, filename)
        )
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(db_snapshot_path):
            raise


def format_seconds(seconds):
    minutes_and_seconds = divmod(seconds, 60)
    return f"{round(minutes_and_seconds[0])} min {round(minutes_and_seconds[1])} sec"
