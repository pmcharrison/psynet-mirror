import errno
from functools import wraps
import os
import shutil

import click

from dallinger import data as dallinger_data
from dallinger.command_line import (
    debug as dallinger_debug,
    deploy as dallinger_deploy,
    log as dallinger_log,
    sandbox as dallinger_sandbox,
    verify_id as dallinger_verify_id,
)
# from dallinger.config import get_config

from psynet import __version__
from psynet import data
from .utils import import_local_experiment

FLAGS = set()

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
    "v" + __version__
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

@psynet.command()
@click.option("--verbose", is_flag=True, flag_value=True, help="Verbose mode.")
@click.option("--force", is_flag=True, flag_value=True, help="Force override of cache.")
def prepare(verbose, force):
    """
    Prepares all stimulus sets defined in experiment.py,
    uploading all media files to Amazon S3.
    """
    FLAGS.add("prepare")
    if force:
        FLAGS.add("force")
    dallinger_log(f"Preparing stimulus sets{' (forced mode)' if force else ''}...")
    experiment_class = import_local_experiment()["class"]
    experiment_class.pre_deploy()
    return experiment_class

@psynet.command()
@click.option("--verbose", is_flag=True, flag_value=True, help="Verbose mode")
@click.option(
    "--bot", is_flag=True, flag_value=True, help="Use bot to complete experiment"
)
@click.option(
    "--proxy", default=None, help="Alternate port when opening browser windows"
)
@click.option(
    "--no-browsers",
    is_flag=True,
    flag_value=True,
    default=False,
    help="Skip opening browsers",
)
@click.option("--force-prepare", is_flag=True, flag_value=False, help="Force override of cache.")
@click.pass_context
def debug(ctx, verbose, bot, proxy, no_browsers, force_prepare):
    """
    Run the experiment locally.
    """
    dallinger_log(header)
    experiment_class = ctx.invoke(prepare, verbose=verbose, force=force_prepare)
    ctx.invoke(dallinger_debug, verbose=verbose, bot=bot, proxy=proxy, no_browsers=no_browsers)
    experiment_class.post_deploy()

@psynet.command()
@click.option("--verbose", is_flag=True, flag_value=True, help="Verbose mode")
@click.option("--app", default=None, help="ID of the deployed experiment")
@click.option("--archive", default=None, help="Optional path to an experiment archive")
@click.option("--force-prepare", is_flag=True, flag_value=False, help="Force override of cache.")
@click.pass_context
def deploy(ctx, verbose, app, archive, force_prepare):
    """
    Deploy app using Heroku to MTurk.
    """
    dallinger_log(header)
    ctx.invoke(prepare, verbose=verbose, force=force_prepare)
    ctx.invoke(dallinger_deploy, verbose=verbose, app=app, archive=archive)


@psynet.command()
@click.option("--verbose", is_flag=True, flag_value=True, help="Verbose mode")
@click.option("--app", default=None, callback=dallinger_verify_id, help="Experiment id")
@click.option("--local", is_flag=True, flag_value=True, help="Export local data")
@click.option("--force-prepare", is_flag=True, flag_value=False, help="Force override of cache.")
@click.pass_context
def export(ctx, verbose, app, local, force_prepare):
    """
    Export the data.
    """
    dallinger_log(header)
    ctx.invoke(prepare, verbose=verbose, force=force_prepare)

    dallinger_log("Creating database snapshot.")
    dallinger_data.export(app, local=local)
    move_snapshot_file(app)
    dallinger_log("Exporting 'json' and 'csv' files.")
    data.export()
    dallinger_log("Export completed.")


@psynet.command()
@click.option("--verbose", is_flag=True, flag_value=True, help="Verbose mode")
@click.option("--app", default=None, help="Experiment id")
@click.option("--archive", default=None, help="Optional path to an experiment archive")
@click.option("--force-prepare", is_flag=True, flag_value=False, help="Force override of cache.")
@click.pass_context
def sandbox(ctx, verbose, app, archive, force_prepare):
    """
    Deploy app using Heroku to the MTurk Sandbox.
    """
    dallinger_log(header)
    experiment_class = ctx.invoke(prepare, verbose=verbose, force=force_prepare)
    ctx.invoke(dallinger_sandbox, verbose=verbose, app=app, archive=archive)
    experiment_class.post_deploy()


def move_snapshot_file(app):
    try:
        db_snapshot_path = os.path.join("data", "db-snapshot")
        if not os.path.exists(db_snapshot_path):
            os.makedirs(db_snapshot_path)
        filename = f"{app}-data.zip"
        shutil.move(
            os.path.join("data", filename),
            os.path.join(db_snapshot_path, filename)
        )
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(db_snapshot_path):
            raise
