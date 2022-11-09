import errno
import os
import pathlib
import re
import shutil
import subprocess
import sys
from shutil import rmtree, which

import click
import psutil
from dallinger.config import get_config
from dallinger.version import __version__ as dallinger_version
from yaspin import yaspin

from psynet import __path__ as psynet_path
from psynet import __version__

from .data import drop_all_db_tables, dump_db_to_disk, init_db
from .utils import (
    get_experiment,
    import_local_experiment,
    pretty_format_seconds,
    run_subprocess_with_live_output,
)

FLAGS = set()


def log(msg, chevrons=True, verbose=True, **kw):
    """Log a message to stdout."""
    if verbose:
        if chevrons:
            click.echo("\n❯❯ " + msg, **kw)
        else:
            click.echo(msg, **kw)


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

        Taking online experiments to the next level
""".format(
    f"v{__version__}"
)


@click.group()
@click.version_option(
    __version__,
    "--version",
    "-v",
    message=f"{__version__} (using Dallinger {dallinger_version})",
)
def psynet():
    pass


def reset_console():
    # Console resetting is required because of some nasty issue
    # with the Heroku command-line tool, where killing Heroku processes
    # ends up messing up the console.
    # I've tracked this down to the line
    # os.killpg(os.getpgid(self._process.pid), signal)
    # in heroku/tools.py in Dallinger, but I haven't found a way
    # to stop this line from messing up the terminal.
    # Instead, the present function is designed to sort out the terminal post hoc.
    #
    # Originally I tried the following:
    # os.system("reset")
    # This works but is too aggressive, it resets the whole terminal.
    #
    # However, the following cheeky hack seems to work quite nicely.
    # The 'read' command is a UNIX command that takes an arbitrary input from the user.
    import subprocess

    try:
        # It seems that the timeout must be at least 1.0 s for this to work reliably
        subprocess.call("read NULL", timeout=1.0, shell=True)
    except subprocess.TimeoutExpired:
        pass


###########
# prepare #
###########
@psynet.command()
@click.option("--force", is_flag=True, help="Force override of cache.")
def prepare(force):
    """
    Prepares all stimulus sets defined in experiment.py,
    uploading all media files to Amazon S3.
    """
    from dallinger import db

    from .trial.static import (  # TODO - remove once storage branch is merged
        STIMULUS_SETS,
    )

    FLAGS.add("prepare")
    if force:
        FLAGS.add("force")
    log(f"Preparing stimulus sets{' (forced mode)' if force else ''}...")
    experiment_class = import_local_experiment().get("class")
    experiment_instance = experiment_class.new(session=None)

    for s in STIMULUS_SETS:
        s.prepare_media(force=force)  # TODO - remove once storage branch is merged

    experiment_instance.pre_deploy()
    db.session.commit()
    clean_sys_modules()
    return experiment_class


#########
# debug #
#########
@psynet.command()
@click.option("--verbose", is_flag=True, help="Verbose mode")
@click.option("--legacy", is_flag=True, help="Legacy mode")
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
@click.option(
    "--threads",
    default=1,
    help="Number of threads to spawn. Fewer threads means faster start-up time.",
)
@click.pass_context
def debug(ctx, legacy, verbose, bot, proxy, no_browsers, force_prepare, threads):
    """
    Run the experiment locally.
    """
    log(header)

    drop_all_db_tables()
    _run_prepare_in_subprocess(force_prepare)
    _cleanup_before_debug()

    try:
        if legacy:
            # Warning: _debug_legacy can fail if the experiment directory is imported before _debug_legacy is called.
            # We therefore need to avoid accessing config variables, calling import_local_experiment, etc.
            # This problem manifests specifically when the experiment contains custom tables.
            _debug_legacy(**locals())
        else:
            _debug_auto_reload(**locals())
    finally:
        kill_psynet_worker_processes()


def _run_prepare_in_subprocess(force_prepare):
    # `psynet prepare` runs `import_local_experiment`, which registers SQLAlchemy tables,
    # which can create a problem for subsequent `dallinger debug`.
    # To avoid problems, we therefore run `psynet prepare` in a subprocess.
    prepare_cmd = "psynet prepare"
    if force_prepare:
        prepare_cmd += " --force"
    run_subprocess_with_live_output(prepare_cmd)


def _cleanup_before_debug():
    kill_psynet_worker_processes()

    if not os.getenv("KEEP_OLD_CHROME_WINDOWS_IN_DEBUG_MODE"):
        kill_psynet_chrome_processes()

    # This is important for resetting the state before _debug_legacy;
    # otherwise `dallinger verify` throws an error.
    clean_sys_modules()  # Unimports the PsyNet experiment


def run_pre_auto_reload_checks():
    if is_editable("psynet"):
        root_dir = str(psynet_dir())
        root_basename = os.path.basename(root_dir)
        if root_basename == "psynet" and root_dir in os.getcwd():
            raise RuntimeError(
                "If running demo experiments inside your PsyNet installation, "
                "you will have to rename your PsyNet folder to something other than 'psynet', "
                "for example 'psynet-package'. Otherwise Python gets confused. Sorry about that! "
                f"The PsyNet folder you need to rename is located at {psynet_dir()}. "
                "After renaming it you will need to reinstall PsyNet by rerunning "
                "pip install -e . inside that directory."
            )


def _debug_legacy(ctx, verbose, bot, proxy, no_browsers, threads, **kwargs):
    from dallinger.command_line import debug as dallinger_debug

    exp_config = {"threads": str(threads)}
    try:
        ctx.invoke(
            dallinger_debug,
            verbose=verbose,
            bot=bot,
            proxy=proxy,
            no_browsers=no_browsers,
            exp_config=exp_config,
        )
    finally:
        reset_console()


def _debug_auto_reload(ctx, bot, proxy, no_browsers, **kwargs):
    run_pre_auto_reload_checks()

    for var, var_name in [
        (bot, "bot"),
        (proxy, "proxy"),
        (no_browsers, "no_browsers"),
    ]:
        assert (
            not var
        ), f"The option '{var_name}' is not supported in this mode, please add --legacy to your command."
    from dallinger.command_line.develop import debug as dallinger_debug

    try:
        ctx.invoke(dallinger_debug)
    finally:
        reset_console()


def safely_kill_process(p):
    try:
        p.kill()
    except psutil.NoSuchProcess:
        pass


def kill_psynet_worker_processes():
    processes = list_psynet_worker_processes()
    if len(processes) > 0:
        log(
            f"Found {len(processes)} remaining PsyNet worker process(es), terminating them now."
        )
    for p in processes:
        safely_kill_process(p)


def kill_psynet_chrome_processes():
    processes = list_psynet_chrome_processes()
    if len(processes) > 0:
        log(
            f"Found {len(processes)} remaining PsyNet Chrome process(es), terminating them now."
        )
    for p in processes:
        safely_kill_process(p)


def kill_chromedriver_processes():
    processes = list_chromedriver_processes()
    if len(processes) > 0:
        log(f"Found {len(processes)} chromedriver processes, terminating them now.")
    for p in processes:
        safely_kill_process(p)


def list_psynet_chrome_processes():
    import psutil

    return [p for p in psutil.process_iter() if is_psynet_chrome_process(p)]


def is_psynet_chrome_process(process):
    try:
        if "chrome" in process.name().lower():
            for cmd in process.cmdline():
                if "localhost:5000" in cmd:
                    return True
                if "user-data-dir" in cmd:
                    return True
    except psutil.NoSuchProcess:
        pass

    return False


def list_psynet_worker_processes():
    import psutil

    return [p for p in psutil.process_iter() if is_psynet_worker_process(p)]


def is_psynet_worker_process(process):
    try:
        # This version catches processes in Linux
        if "dallinger_herok" in process.name():
            return True
        # This version catches process in MacOS
        if "python" in process.name().lower():
            for cmd in process.cmdline():
                if "dallinger_heroku_" in cmd:
                    return True
    except psutil.NoSuchProcess:
        pass

    return False


def list_chromedriver_processes():
    import psutil

    return [p for p in psutil.process_iter() if is_chromedriver_process(p)]


def is_chromedriver_process(process):
    try:
        return "chromedriver" in process.name().lower()
    except psutil.NoSuchProcess:
        pass


##############
# pre deploy #
##############
def run_pre_checks_deploy(exp, config, is_mturk):
    initial_recruitment_size = exp.initial_recruitment_size

    if (
        is_mturk
        and initial_recruitment_size <= 10
        and not click.confirm(
            f"Are you sure you want to deploy to MTurk with initial_recruitment_size set to {initial_recruitment_size}? "
            f"You will not be able to recruit more than {initial_recruitment_size} participant(s), "
            "due to a restriction in the MTurk pricing scheme.",
            default=True,
        )
    ):
        raise click.Abort


##########
# deploy #
##########
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
    run_pre_checks("deploy")
    log(header)
    ctx.invoke(prepare, force=force_prepare)

    from dallinger.command_line import deploy as dallinger_deploy

    try:
        ctx.invoke(dallinger_deploy, verbose=verbose, app=app, archive=archive)
    finally:
        reset_console()


########
# docs #
########
@psynet.command()
@click.option(
    "--force-rebuild",
    "-f",
    is_flag=True,
    help="Force complete rebuild by deleting the '_build' directory",
)
def docs(force_rebuild):
    docs_dir = os.path.join(psynet_path[0], "..", "docs")
    docs_build_dir = os.path.join(docs_dir, "_build")
    try:
        os.chdir(docs_dir)
    except FileNotFoundError as e:
        log(
            "There was an error building the documentation. Be sure to have activated your 'psynet' virtual environment."
        )
        raise SystemExit(e)
    if os.path.exists(docs_build_dir) and force_rebuild:
        rmtree(docs_build_dir)
    os.chdir(docs_dir)
    subprocess.run(["make", "html"])
    if which("xdg-open") is not None:
        open_command = "xdg-open"
    else:
        open_command = "open"
    subprocess.run(
        [open_command, os.path.join(docs_build_dir, "html/index.html")],
        stdout=subprocess.DEVNULL,
    )


##############
# pre sandbox #
##############


def run_pre_checks(mode):
    from dallinger.recruiters import MTurkRecruiter

    init_db(drop_all=True)

    config = get_config()
    if not config.ready:
        config.load()

    exp = get_experiment()

    recruiter = exp.recruiter
    is_mturk = isinstance(recruiter, MTurkRecruiter)

    if mode == "sandbox":
        run_pre_checks_sandbox(exp, config, is_mturk)
    elif mode == "deploy":
        run_pre_checks_deploy(exp, config, is_mturk)


def run_pre_checks_sandbox(exp, config, is_mturk):
    us_only = config.get("us_only")

    if (
        is_mturk
        and us_only
        and not click.confirm(
            "Are you sure you want to sandbox with us_only = True? "
            "Only people with US accounts will be able to test the experiment.",
            default=True,
        )
    ):
        raise click.Abort


###########
# sandbox #
###########
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
    run_pre_checks("sandbox")
    log(header)
    ctx.invoke(prepare, force=force_prepare)

    from dallinger.command_line import sandbox as dallinger_sandbox

    try:
        ctx.invoke(dallinger_sandbox, verbose=verbose, app=app, archive=archive)
    finally:
        reset_console()


##########
# update #
##########
@psynet.command()
@click.option(
    "--dallinger-version",
    default="latest",
    help="The git branch, commit or tag of the Dallinger version to install.",
)
@click.option(
    "--psynet-version",
    default="latest",
    help="The git branch, commit or tag of the psynet version to install.",
)
@click.option("--verbose", is_flag=True, help="Verbose mode")
def update(dallinger_version, psynet_version, verbose):
    """
    Update the locally installed `Dallinger` and `PsyNet` versions.
    """

    def _git_checkout(version, cwd, capture_output):
        with yaspin(text=f"Checking out {version}...", color="green") as spinner:
            subprocess.run(
                [f"git checkout {version}"],
                shell=True,
                cwd=cwd,
                capture_output=capture_output,
            )
            spinner.ok("✔")

    def _git_latest_tag(cwd, capture_output):
        return (
            subprocess.check_output(["git", "describe", "--abbrev=0", "--tag"], cwd=cwd)
            .decode("utf-8")
            .strip()
        )

    def _git_pull(cwd, capture_output):
        with yaspin(text="Pulling changes...", color="green") as spinner:
            subprocess.run(
                ["git pull"],
                shell=True,
                cwd=cwd,
                capture_output=capture_output,
            )
            spinner.ok("✔")

    def _git_needs_stashing(cwd):
        return (
            subprocess.check_output(["git", "diff", "--name-only"], cwd=cwd)
            .decode("utf-8")
            .strip()
            != ""
        )

    def _git_version_pattern():
        return re.compile("^v([0-9]+)\\.([0-9]+)\\.([0-9]+)$")

    def _prepare(version, project_name, cwd, capture_output):
        if _git_needs_stashing(cwd):
            with yaspin(
                text=f"Git commit your changes or stash them before updating {project_name}!",
                color="red",
            ) as spinner:
                spinner.ok("✘")
            raise SystemExit()

        _git_checkout("master", cwd, capture_output)
        _git_pull(cwd, capture_output)

        if version == "latest":
            version = _git_latest_tag(cwd, capture_output)

        _git_checkout(version, cwd, capture_output)

    log(header)
    capture_output = not verbose

    # Dallinger
    log("Updating Dallinger...")
    cwd = dallinger_dir()
    if is_editable("dallinger"):
        _prepare(
            dallinger_version,
            "Dallinger",
            cwd,
            capture_output,
        )

    if is_editable("dallinger"):
        text = "Installing development requirements and base packages..."
        install_command = "pip install --editable '.[data]'"
    else:
        text = "Installing base packages..."
        install_command = "pip install '.[data]'"

    with yaspin(
        text=text,
        color="green",
    ) as spinner:
        if is_editable("dallinger"):
            subprocess.run(
                ["pip3 install -r dev-requirements.txt"],
                shell=True,
                cwd=cwd,
                capture_output=capture_output,
            )
        else:
            if _git_version_pattern().match(dallinger_version):
                install_command = f"pip install dallinger=={dallinger_version}"
            else:
                install_command = "pip install dallinger"
        subprocess.run(
            [install_command],
            shell=True,
            cwd=cwd,
            capture_output=capture_output,
        )
        spinner.ok("✔")

    # PsyNet
    log("Updating PsyNet...")
    cwd = psynet_dir()
    _prepare(
        psynet_version,
        "PsyNet",
        cwd,
        capture_output,
    )

    text = "Installing base packages and development requirements..."
    install_command = "pip install -e '.[dev]'"

    with yaspin(text=text, color="green") as spinner:
        install_command = install_command
        subprocess.run(
            [install_command],
            shell=True,
            cwd=cwd,
            capture_output=capture_output,
        )
        spinner.ok("✔")

    log(f'Updated PsyNet to version {get_version("psynet")}')


def dallinger_dir():
    import dallinger as _

    return pathlib.Path(_.__file__).parent.parent.resolve()


def psynet_dir():
    import psynet as _

    return pathlib.Path(_.__file__).parent.parent.resolve()


def get_version(project_name):
    return (
        subprocess.check_output([f"{project_name} --version"], shell=True)
        .decode("utf-8")
        .strip()
    )


def is_editable(project):
    for path_item in sys.path:
        egg_link = os.path.join(path_item, project + ".egg-link")
        if os.path.isfile(egg_link):
            return True
    return False


############
# estimate #
############
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
    log(header)
    experiment_class = import_local_experiment()["class"]
    experiment = setup_experiment_variables(experiment_class)
    if mode in ["bonus", "both"]:
        maximum_bonus = experiment_class.estimated_max_bonus(
            experiment.var.wage_per_hour
        )
        log(f"Estimated maximum bonus for participant: ${round(maximum_bonus, 2)}.")
    if mode in ["time", "both"]:
        completion_time = experiment_class.estimated_completion_time(
            experiment.var.wage_per_hour
        )
        log(
            f"Estimated time to complete experiment: {pretty_format_seconds(completion_time)}."
        )


def setup_experiment_variables(experiment_class):
    experiment = experiment_class()
    experiment.setup_experiment_variables()
    return experiment


def verify_experiment_id(ctx, param, app):
    from dallinger.command_line import verify_id

    return verify_id(ctx, param, app)


########################
# generate-constraints #
########################
@psynet.command()
@click.pass_context
def generate_constraints(ctx):
    """
    Generate the constraints.txt file from requirements.txt.
    """
    from dallinger.command_line import (
        generate_constraints as dallinger_generate_constraints,
    )

    log(header)
    try:
        ctx.invoke(dallinger_generate_constraints)
    finally:
        reset_console()


##########
# export #
##########
@psynet.command()
@click.option(
    "--app",
    default=None,
    required=True,
    callback=verify_experiment_id,
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
    export_(app, local)


def export_(app, local):
    log(header)
    import_local_experiment()

    data_dir_path = os.path.join("data", f"data-{app}")
    create_export_dirs(data_dir_path)

    log("Creating database snapshot.")
    from dallinger import data as dallinger_data
    from dallinger import db as dallinger_db

    # Dallinger hard-codes the list of table names, but this list becomes out of date
    # if we add custom tables, so we have to patch it.
    dallinger_data.table_names = sorted(dallinger_db.Base.metadata.tables.keys())

    dallinger_data.export(app, local=local)
    move_snapshot_file(data_dir_path, app)
    with yaspin(text="Completed.", color="green") as spinner:
        spinner.ok("✔")

    dallinger_zip_path = os.path.join(data_dir_path, "db-snapshot", f"{app}-data.zip")

    if not local:
        log("Populating the local database with the downloaded data.")
        populate_db_from_zip_file(dallinger_zip_path)

    log("Exporting final 'csv' files.")
    dump_db_to_disk(os.path.join(data_dir_path, "csv"))

    log("Export completed.")


def populate_db_from_zip_file(zip_path):
    from dallinger import data as dallinger_data

    init_db(drop_all=True)
    dallinger_data.ingest_zip(zip_path)


def create_export_dirs(data_dir_path):
    for file_format in ["csv", "db-snapshot"]:
        export_path = os.path.join(data_dir_path, file_format)
        try:
            os.makedirs(export_path)
        except OSError as e:
            if e.errno != errno.EEXIST or not os.path.isdir(export_path):
                raise


def move_snapshot_file(data_dir_path, app):
    db_snapshot_path = os.path.join(data_dir_path, "db-snapshot")
    filename = f"{app}-data.zip"
    shutil.move(
        os.path.join("data", filename), os.path.join(db_snapshot_path, filename)
    )


@psynet.command()
@click.option(
    "--ip",
    default="127.0.0.1",
    help="IP address",
)
@click.option("--port", default="4444", help="Port")
def rpdb(ip, port):
    """
    Alias for `nc <ip> <port>`.
    """
    subprocess.run(
        ["nc %s %s" % (ip, port)],
        shell=True,
    )
