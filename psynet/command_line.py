import errno
import os
import shutil

import click

from dallinger import data as dallinger_data
from dallinger.command_line import verify_id, log
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
    import_local_experiment()

@psynet.command()
@click.option("--app", default=None, callback=verify_id, help="Experiment id")
@click.option("--local", is_flag=True, flag_value=True, help="Export local data")
def export(app, local):
    """
    Export the data.
    """
    log(header, chevrons=False)
    import_local_experiment()

    log("Creating database snapshot.")
    dallinger_data.export(app, local=local)
    move_snapshot_file(app)
    log("Exporting 'json' and 'csv' files.")
    data.export()
    log("Export completed.")

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
