import psynet
import click

from dallinger.command_line import require_exp_directory

from .utils import import_local_experiment

FLAGS = set()

@click.group()
@click.version_option(psynet.__version__, "--version", "-v", message="%(version)s")
def psynet():
    pass

@psynet.command()
@click.option("--verbose", is_flag=True, flag_value=True, help="Verbose mode.")
@click.option("--force", is_flag=True, flag_value=True, help="Force override of cache.")
@require_exp_directory
def prepare(verbose, force):
    """
    Prepares all stimulus sets defined in experiment.py,
    uploading all media files to Amazon S3.
    """
    FLAGS.add("prepare")
    if force:
        FLAGS.add("force")
    import_local_experiment()
