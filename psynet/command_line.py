import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from hashlib import md5
from importlib import resources
from pathlib import Path
from shutil import rmtree, which
from urllib.parse import urlencode

import click
import click.shell_completion
import dallinger.command_line.utils
import psutil
import psycopg2
import requests
from dallinger import db
from dallinger.command_line.docker_ssh import (
    CONFIGURED_HOSTS,
    option_server,
    remote_postgres,
)
from dallinger.command_line.utils import verify_id
from dallinger.config import experiment_available, get_config
from dallinger.heroku.tools import HerokuApp
from dallinger.recruiters import ProlificRecruiter
from dallinger.version import __version__ as dallinger_version
from sqlalchemy.exc import ProgrammingError
from yaspin import yaspin

from psynet import __path__ as psynet_path
from psynet import __version__
from psynet.version import check_dallinger_version, check_versions

from . import deployment_info
from .data import drop_all_db_tables, dump_db_to_disk, ingest_zip, init_db
from .log import bold
from .lucid import get_lucid_service
from .recruiters import BaseLucidRecruiter, HotAirRecruiter
from .redis import redis_vars
from .serialize import serialize, unserialize
from .utils import (
    get_args,
    get_experiment_url,
    get_logger,
    get_package_name,
    git_repository_available,
    in_python_package,
    list_experiment_dirs,
    list_isolated_tests,
    make_parents,
    pretty_format_seconds,
    require_exp_directory,
    require_requirements_txt,
    run_subprocess_with_live_output,
    working_directory,
)

logger = get_logger()


def _suppress_dallinger_header():
    """
    Stops the Dallinger logo from being printed in the command line.
    """
    dallinger.command_line.header = ""
    dallinger.command_line.utils.header = ""

    # We need to use importlib here to avoid confusion with the command group of the same name
    develop_module = importlib.import_module("dallinger.command_line.develop")
    develop_module.header = ""


_suppress_dallinger_header()


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


def update_docker_tag():
    with open("Dockertag", "w") as file:
        file.write(os.path.basename(os.getcwd()))
        file.write("\n")


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
    subprocess.call("stty sane", shell=True)


###########
# prepare #
###########
@psynet.command()
@click.option(
    "--archive",
    type=click.Path(exists=True),
    help="Path to database archive for re-deployment",
)
def prepare(archive):
    """
    Prepare the experiment for deployment.
    """
    _prepare(archive)


def _prepare(archive=None):
    from dallinger import db

    from .experiment import get_experiment

    redis_vars.clear()

    if archive:
        from psynet.experiment import database_template_path

        shutil.copyfile(archive, database_template_path)

    db.init_db(drop_all=True)
    experiment = get_experiment()
    experiment.pre_deploy(redeploying_from_archive=archive is not None)
    db.session.flush()
    clean_sys_modules()
    update_docker_tag()

    db.session.commit()


#########
# debug #
#########


def _experiment_variables(connection, echo=False):
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT vars FROM experiment")
        records = cursor.fetchall()

        if len(records) == 0:
            raise RuntimeError(
                "No rows found in the `experiment` table, maybe the experiment isn't launched yet?"
            )

        assert len(records) == 1

        _vars = unserialize(records[0][0])
        if echo:
            click.echo(serialize(_vars, indent=4))
        return _vars
    except psycopg2.errors.UndefinedTable:
        click.echo(
            "Could not find the table `experiment` on the remote database. This could mean that the experiment isn't "
            "launched yet, or it could mean that the experiment is using an incompatible version of PsyNet."
        )
    finally:
        cursor.close()


# Experiment variables ####


def _validate_location(ctx, param, value):
    allowed = ["local", "heroku", "ssh"]
    if value not in allowed:
        raise click.UsageError(
            f"Invalid location {value}; location must be one of: {', '.join(allowed)}"
        )


@psynet.command("experiment-variables")
@click.argument("location", default="local")  # , callback=_validate_location)
@click.option(
    "--app",
    default=None,
    help="Name of the experiment app (required for non-local deployments)",
)
@option_server
def experiment_variables(location, app, server):
    """
    Show the variables of the experiment.
    """
    with db_connection(location, app, server) as connection:
        return _experiment_variables(connection, echo=True)


@contextmanager
def db_connection(location, app=None, server=None):
    """
    Get a database connection.
    """
    try:
        connection = None
        with get_db_uri(location, app, server) as db_uri:
            if "postgresql://" in db_uri or "postgres://" in db_uri:
                connection = psycopg2.connect(dsn=db_uri)
            else:
                connection = psycopg2.connect(database=db_uri, user="dallinger")
            yield connection
    except psycopg2.OperationalError as err:
        if "Connection refused" in str(err):
            raise ConnectionError(
                f"Couldn't connect to the experiment database. Are you sure the app name ({app}) is correct? "
                "You can list all valid apps using the following command:\n\tpsynet apps ssh"
            )
        else:
            raise
    finally:
        if connection:
            connection.close()


def prompt_for_ssh_server():
    click.echo(
        "Choose one of the configured servers (add one with `dallinger docker-ssh servers add`):"
    )
    return click.Choice(CONFIGURED_HOSTS.keys())


@contextmanager
def get_db_uri(location, app=None, server=None):
    match location:
        case "local":
            yield db.db_url
        case "heroku" | "docker_heroku":
            if app is None:
                raise click.UsageError("Missing parameter: --app")
            yield HerokuApp(app).db_uri
        case "ssh":
            if app is None:
                raise click.UsageError("Missing parameter: --app")
            if server is None:
                server = prompt_for_ssh_server()
            server_info = CONFIGURED_HOSTS[server]
            with remote_postgres(server_info, app) as db_uri:
                yield db_uri
        case _:
            raise click.BadParameter(f"Invalid location: {location}")


@psynet.command("db")
@click.argument("location", default="local", callback=_validate_location)
@click.option(
    "--app",
    default=None,
    help="Name of the experiment app (required for non-local deployments)",
)
@click.option(
    "--server",
    default=None,
    help="Name of the remote server (only relevant for ssh deployments)",
)
def _db(location, app, server):
    """
    Get the database connection URI.
    """
    with get_db_uri(location, app, server) as uri:
        click.echo(uri)
        return uri


@psynet.group("debug")
@click.pass_context
@require_exp_directory
def debug(ctx):
    """
    Debug the experiment.
    """
    pass


@psynet.command(
    context_settings=dict(
        allow_extra_args=True,
        ignore_unknown_options=True,
    )
)
@require_exp_directory
def sandbox(*args, **kwargs):
    """
    Sandbox the experiment (has been replaced with `psynet debug heroku`).
    """
    raise click.ClickException(
        "`psynet sandbox` has been replaced with `psynet debug heroku`, please use the latter."
    )


def _run_local(ctx, docker, archive, legacy, no_browsers, mode, context_group):
    """
    Debug the experiment locally (this should normally be your first choice).
    """
    if not ctx:
        from click import Context

        ctx = Context(context_group)

    if legacy and docker:
        raise click.UsageError(
            "It is not possible to select both --legacy and --docker modes simultaneously."
        )

    _pre_launch(ctx, mode=mode, archive=archive, local_=True, docker=docker, app=None)
    _cleanup_before_debug()

    try:
        # Note: PsyNet bypasses Dallinger's deploy-from-archive system and uses its own, so we set archive=None.
        if legacy:
            # Warning: _debug_legacy can fail if the experiment directory is imported before _debug_legacy is called.
            # We therefore need to avoid accessing config variables, calling import_local_experiment, etc.
            # This problem manifests specifically when the experiment contains custom tables.
            _debug_legacy(ctx, archive=None, no_browsers=no_browsers)
        elif docker:
            _debug_docker(ctx, archive=None, no_browsers=no_browsers)
        else:
            _debug_auto_reload(ctx, archive=None, no_browsers=no_browsers)
    finally:
        kill_psynet_worker_processes()
        _cleanup_exp_directory()


@debug.command("local")
@click.option("--docker", is_flag=True, help="Docker mode.")
@click.option("--archive", default=None, help="Optional path to an experiment archive.")
@click.option("--legacy", is_flag=True, help="Legacy mode.")
@click.option("--no-browsers", is_flag=True, help="Skip opening browsers.")
@click.pass_context
def debug__local(ctx, docker, archive, legacy, no_browsers):
    """
    Debug the experiment locally (this should normally be your first choice).
    """
    _run_local(
        ctx, docker, archive, legacy, no_browsers, mode="debug", context_group=debug
    )


def run_prepare_in_subprocess():
    # `psynet prepare` runs `import_local_experiment`, which registers SQLAlchemy tables,
    # which can create a problem for subsequent `dallinger debug`.
    # To avoid problems, we therefore run `psynet prepare` in a subprocess.
    prepare_cmd = "psynet prepare"
    run_subprocess_with_live_output(prepare_cmd)


def _cleanup_before_debug():
    kill_psynet_worker_processes()

    if not os.getenv("KEEP_OLD_CHROME_WINDOWS_IN_DEBUG_MODE"):
        kill_psynet_chrome_processes()

    # This is important for resetting the state before _debug_legacy;
    # otherwise `dallinger verify` throws an error.
    clean_sys_modules()  # Unimports the PsyNet experiment

    drop_all_db_tables()


def _cleanup_exp_directory():
    """
    Cleans up temporary files that are sometimes left behind by the experiment.
    """
    for file in ["source_code.zip", "server.log", "logs.jsonl"]:
        try:
            os.remove(file)
        except FileNotFoundError:
            pass

    for dir in [".deploy"]:
        try:
            shutil.rmtree(dir)
        except FileNotFoundError:
            pass


def run_pre_auto_reload_checks():
    config = get_config()
    if not config.ready:
        config.load()

    from dallinger.utils import develop_target_path

    _develop_path = str(develop_target_path(config))
    if "." in _develop_path:
        raise ValueError(
            f"The target path for your app's temporary development directory ({_develop_path}) "
            "contains a period ('.'). Unfortunately Dallinger doesn't support this."
            "You should set a revised path in your .dallingerconfig file. "
            "We recommend: dallinger_develop_directory = /tmp/dallinger_develop"
        )

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


def _debug_legacy(ctx, archive, no_browsers):
    if archive:
        raise click.UsageError(
            "Legacy debug mode doesn't currently support loading from archive."
        )

    from dallinger.command_line import debug as dallinger_debug

    db.session.commit()

    try:
        ctx.invoke(
            dallinger_debug,
            verbose=True,
            bot=False,
            proxy=None,
            no_browsers=no_browsers,
            exp_config={"threads": "1"},
        )
    finally:
        db.session.commit()
        reset_console()


def _debug_docker(ctx, archive, no_browsers):
    from dallinger.command_line.docker import debug as dallinger_debug

    if archive:
        raise click.UsageError(
            "`psynet debug` with Docker doesn't currently support loading from archive."
        )

    db.session.commit()

    try:
        ctx.invoke(
            dallinger_debug,
            verbose=True,
            bot=False,
            proxy=None,
            no_browsers=no_browsers,
        )
    finally:
        db.session.commit()
        reset_console()


def _debug_auto_reload(ctx, archive, no_browsers):
    if no_browsers:
        raise click.UsageError(
            "--no-browsers option is not supported in this debug mode."
        )

    run_pre_auto_reload_checks()

    from dallinger.command_line.develop import debug as dallinger_debug
    from dallinger.deployment import DevelopmentDeployment

    DevelopmentDeployment.archive = archive
    patch_dallinger_develop()

    develop_module = importlib.import_module("dallinger.command_line.develop")
    develop_module.header = ""

    try:
        ctx.invoke(dallinger_debug, skip_flask=False)
    finally:
        db.session.commit()
        reset_console()


def patch_dallinger_develop():
    from dallinger.deployment import DevelopmentDeployment

    if not (
        hasattr(DevelopmentDeployment, "patched") and DevelopmentDeployment.patched
    ):
        old_run = DevelopmentDeployment.run

        def new_run(self):
            old_run(self)
            if hasattr(self, "archive") and self.archive:
                archive_path = os.path.abspath(self.archive)
                if not os.path.exists(archive_path):
                    raise click.BadParameter(
                        'Experiment archive "{}" does not exist.'.format(archive_path)
                    )
                init_db()
                ingest_zip(archive_path, engine=db.engine)

        DevelopmentDeployment.run = new_run
        DevelopmentDeployment.patched = True


patch_dallinger_develop()


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
        logger.debug(
            f"Found {len(processes)} remaining PsyNet Chrome process(es), terminating them now."
        )
    for p in processes:
        safely_kill_process(p)


def kill_chromedriver_processes():
    processes = list_chromedriver_processes()
    if len(processes) > 0:
        logger.debug(
            f"Found {len(processes)} chromedriver processes, terminating them now."
        )
    for p in processes:
        safely_kill_process(p)


def list_psynet_chrome_processes():
    return [p for p in psutil.process_iter() if is_psynet_chrome_process(p)]


def is_psynet_chrome_process(process):
    try:
        if "chrome" in process.name().lower():
            for cmd in process.cmdline():
                if "localhost:5000" in cmd:
                    return True
                if "user-data-dir" in cmd:
                    return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    return False


def list_psynet_worker_processes():
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
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    return False


def list_chromedriver_processes():
    return [p for p in psutil.process_iter() if is_chromedriver_process(p)]


def is_chromedriver_process(process):
    try:
        return "chromedriver" in process.name().lower()
    except psutil.NoSuchProcess:
        pass


###########
# run bot #
###########


def _run_bot(real_time, dashboard_user, dashboard_password):
    from .experiment import get_experiment

    os.environ["PASSTHROUGH_ERRORS"] = "True"

    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    config = get_config()
    if not config.ready:
        config.load()

    config.set("dashboard_user", dashboard_user)
    config.set("dashboard_password", dashboard_password)
    time_factor = 1.0 if real_time else 0.0

    exp = get_experiment()
    exp.run_bot(time_factor=time_factor)


@psynet.command()
@click.option(
    "--real-time",
    is_flag=True,
    help="Instead of running the bot through the experiment as fast as possible, follow the timings in time_estimate instead.",
)
@click.option(
    "--dashboard-user",
    help="The username for the experiment's dashboard (used for bot authentication).",
)
@click.option(
    "--dashboard-password",
    help="The password for the experiment's dashboard (used for bot authentication).",
)
@click.pass_context
@require_exp_directory
def run_bot(ctx, real_time=False, dashboard_user=None, dashboard_password=None):
    """
    Run a bot through the local version of the experiment.
    Prior to running this command you must spin up a local experiment, for example
    by running ``psynet debug local``. You can then call ``psynet run-bot``
    multiple times to simulate multiple bots being run through the experiment.
    """
    _run_bot(real_time, dashboard_user, dashboard_password)


##############
# pre deploy #
##############
def run_pre_checks_deploy(exp, config, is_mturk, local_, recruiter):
    verify_psynet_requirement()
    check_versions()
    initial_recruitment_size = exp.initial_recruitment_size

    if (
        is_mturk
        and initial_recruitment_size <= 10
        and not user_confirms(
            f"Are you sure you want to deploy to MTurk with initial_recruitment_size set to {initial_recruitment_size}? "
            f"You will not be able to recruit more than {initial_recruitment_size} participant(s), "
            "due to a restriction in the MTurk pricing scheme.",
            default=True,
        )
    ):
        raise click.Abort

    if local_ and not isinstance(recruiter, HotAirRecruiter):
        raise click.UsageError(
            "``psynet deploy local`` currently only supports the 'generic' recruiter. "
            "Set recruiter = generic in your experiment config, or deploy to a remote server instead "
            "(e.g. ``psynet deploy ssh``)."
        )


##########
# deploy #
##########


def _pre_launch(
    ctx,
    *,
    mode,
    archive,
    local_,
    ssh=False,
    docker=False,
    heroku=False,
    server=None,
    app=None,
):
    from .experiment import get_experiment

    redis_vars.clear()
    deployment_info.init(
        redeploying_from_archive=archive is not None,
        mode=mode,
        is_local_deployment=local_,
        is_ssh_deployment=ssh,
        server=server,
        app=app,
    )

    if ssh:
        server_info = CONFIGURED_HOSTS[server]

        ssh_host = server_info["host"]
        ssh_user = server_info.get("user")

        deployment_info.write(ssh_host=ssh_host, ssh_user=ssh_user)

    run_pre_checks(mode, local_, heroku, docker, app)

    # Always use the Dallinger version in requirements.txt, not the local editable one
    os.environ["DALLINGER_NO_EGG_BUILD"] = "1"

    if docker:
        if Path("Dockerfile").exists():
            # Tell Dallinger not to rebuild constraints.txt, because we'll manage this within the Docker image
            os.environ["SKIP_DEPENDENCY_CHECK"] = "1"

    experiment = get_experiment()
    experiment.update_deployment_id()

    config = get_config()
    deployment_info.write(locale=config.get("locale", "en"))

    if config.get("check_dallinger_version"):
        check_dallinger_version()

    ctx.invoke(prepare, archive=archive)

    _forget_tables_defined_in_experiment_directory()

    if heroku:
        # Unimports the PsyNet experiment, because Dallinger will want to start from scratch when using Heroku.
        # We don't unimport it in other cases because reloading the experiment produces an unnecessary time overhead.
        clean_sys_modules()


def _forget_tables_defined_in_experiment_directory():
    # We need to instruct SQLAlchemy to forget tables defined in the experiment directory,
    # because otherwise SQLAlchemy will get confused and throw errors when we run subsequent commands
    # that import the same experiment from other locations (e.g. /tmp/dallinger_develop).

    from dallinger.db import Base

    tables_defined_in_experiment_directory = [
        mapper.class_.__tablename__
        for mapper in dallinger.db.Base.registry.mappers
        if mapper.class_.__module__.startswith("dallinger_experiment")
        and not mapper.class_.inherits_table
    ]

    for table in tables_defined_in_experiment_directory:
        Base.metadata.remove(Base.metadata.tables[table])


@psynet.group("deploy")
@require_exp_directory
def deploy():
    """
    Deploy the experiment.
    """
    pass


@deploy.command("local")
@click.option("--docker", is_flag=True, help="Docker mode.")
@click.option("--archive", default=None, help="Optional path to an experiment archive.")
@click.option("--legacy", is_flag=True, help="Legacy mode.")
@click.option("--no-browsers", is_flag=True, help="Skip opening browsers.")
@click.pass_context
def deploy__local(ctx, docker, archive, legacy, no_browsers):
    """
    Deploy the experiment locally (e.g., when collecting data on a computer in the lab or in the field).
    """
    _run_local(
        ctx, docker, archive, legacy, no_browsers, mode="live", context_group=deploy
    )


@deploy.command("heroku")
@click.option("--app", callback=verify_id, required=True, help="Experiment id")
@click.option("--archive", default=None, help="Optional path to an experiment archive")
@click.option("--docker", is_flag=True, default=False, help="Deploy using Docker")
@click.pass_context
def deploy__heroku(ctx, app, archive, docker):
    """
    Deploy the experiment to Heroku.
    """
    if docker:
        _deploy__docker_heroku(ctx, app, archive)

    try:
        from dallinger.command_line import deploy as dallinger_deploy

        _pre_launch(
            ctx,
            mode="live",
            archive=archive,
            local_=False,
            heroku=True,
            app=app,
        )
        # Note: PsyNet bypasses Dallinger's deploy-from-archive system and uses its own, so we set archive=None.
        result = ctx.invoke(dallinger_deploy, verbose=True, app=app, archive=None)
        _post_deploy(result)
    finally:
        _cleanup_exp_directory()
        reset_console()


def _deploy__docker_heroku(ctx, app, archive):
    try:
        from dallinger.command_line.docker import deploy as dallinger_deploy

        if archive is not None:
            raise NotImplementedError(
                "Unfortunately docker-heroku sandbox doesn't yet support deploying from archive. "
                "This shouldn't be hard to fix..."
            )

        _pre_launch(
            ctx,
            mode="live",
            archive=archive,
            local_=False,
            docker=True,
            heroku=True,
            app=app,
        )
        result = ctx.invoke(dallinger_deploy, verbose=True, app=app)
        _post_deploy(result)
    finally:
        _cleanup_exp_directory()
        reset_console()


@deploy.command("ssh")
@click.option("--app", callback=verify_id, required=True, help="Experiment id")
@click.option("--archive", default=None, help="Optional path to an experiment archive")
@option_server
@click.option(
    "--dns-host",
    help="DNS name to use. Must resolve all its subdomains to the IP address specified as ssh host",
)
@click.pass_context
def deploy__docker_ssh(ctx, app, archive, dns_host, server):
    """
    Deploy the experiment to a remote server via Docker and SSH.
    """
    try:
        # Ensures that the experiment is deployed with the Dallinger version specified in requirements.txt,
        # irrespective of whether a different version is installed locally.
        os.environ["DALLINGER_NO_EGG_BUILD"] = "1"

        _pre_launch(
            ctx,
            mode="live",
            archive=archive,
            local_=False,
            ssh=True,
            docker=True,
            server=server,
            app=app,
        )

        from dallinger.command_line.docker_ssh import (
            deploy as dallinger_docker_ssh_deploy,
        )

        # Note: PsyNet bypasses Dallinger's deploy-from-archive system and uses its own, so we set archive_path=None.
        result = ctx.invoke(
            dallinger_docker_ssh_deploy,
            server=server,
            dns_host=dns_host,
            app_name=app,
            archive_path=None,
        )

        _post_deploy(result)
    finally:
        _cleanup_exp_directory()
        reset_console()


def _post_deploy(result):
    assert isinstance(result, dict)
    assert "dashboard_user" in result
    assert "dashboard_password" in result
    export_launch_data(
        deployment_id=deployment_info.read("deployment_id"),
        **result,
    )


def export_launch_data(deployment_id, **kwargs):
    """
    Retrieves dashboard credentials from the current config and
    saves them to disk.
    """
    directory = Path("~/psynet-data/launch-data").expanduser() / deployment_id
    directory.mkdir(parents=True, exist_ok=True)
    _export_launch_info(directory, **kwargs)


def _export_launch_info(directory, dashboard_user, dashboard_password, **kwargs):
    file = directory.joinpath("launch-info.json")
    with open(file, "w") as f:
        json.dump(
            {
                "dashboard_user": dashboard_user,
                "dashboard_password": dashboard_password,
                **kwargs,
            },
            f,
            indent=4,
        )


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
    """
    Build the documentation.
    """
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


def check_prolific_payment(experiment, config):
    from .utils import get_config

    base_payment = config.get("base_payment")
    minutes = config.get("prolific_estimated_completion_minutes")
    wage_per_hour = get_config().get("wage_per_hour")
    assert (
        wage_per_hour * minutes / 60 == base_payment
    ), "Wage per hour does not match Prolific reward"


def run_pre_checks(mode, local_, heroku=False, docker=False, app=None):
    from dallinger.recruiters import MTurkRecruiter

    from .experiment import get_experiment
    from .utils import check_todos_before_deployment

    exp = get_experiment()
    exp.check_config()
    exp.check_size()
    exp.check_consents()
    exp.check_python_dependencies()

    # Make sure source_code.zip is in .gitignore
    try:
        with open(".gitignore", "r") as f:
            source_code_zip_found = False
            for line in f.readlines():
                if "source_code.zip" in line:
                    source_code_zip_found = True
                    break
            if not source_code_zip_found:
                raise click.ClickException(
                    "Please add source_code.zip to .gitignore and try again."
                )
    except FileNotFoundError:
        raise click.ClickException(
            f".gitignore is missing from your experiment directory ({os.getcwd()})."
        )

    # We need an active git repository for Dallinger to recognize .gitignore properly
    if not git_repository_available():
        raise click.ClickException(
            "This directory is not a git repository, or git is not installed. Please ensure git is installed and create a repository by running 'git init' if needed."
        )

    try:
        with open("requirements.txt", "r") as f:
            for line in f.readlines():
                if "computational-audition-lab/psynet" in line.lower() and not user_confirms(
                    "It looks like you're using an old version of PsyNet in requirements.txt "
                    "(computational-audition-lab/psynet); "
                    "the up-to-date version is located at PsyNetDev/PsyNet. Are you sure you want to continue?"
                ):
                    raise click.Abort
    except FileNotFoundError:
        raise click.ClickException(
            f"requirements.txt is missing from your experiment directory ({os.getcwd()})."
        )

    if heroku:
        if docker and not user_confirms(
            "Heroku deployment with Docker hasn't been working well recently; experiments have been failing to launch "
            "and returning a psutil version error. Are you sure you want to continue?"
        ):
            raise click.Abort

        try:
            with open(".gitignore", "r") as f:
                for line in f.readlines():
                    if line.startswith(".deploy"):
                        if not user_confirms(
                            "The .gitignore file contains '.deploy'; "
                            "in order to deploy on Heroku without Docker this line must ordinarily be removed. "
                            "Are you sure you want to continue?"
                        ):
                            raise click.Abort
        except FileNotFoundError:
            pass

    if docker:
        if not Path("Dockerfile").exists():
            raise click.UsageError(
                "If using PsyNet with Docker, it is mandatory to include a Dockerfile in the experiment directory. "
                "To add a generic Dockerfile to your experiment directory, run the following command:\n"
                "psynet update-scripts"
            )

    if not local_:
        init_db(drop_all=True)

        config = get_config()
        if not config.ready:
            config.load()
        check_todos_before_deployment()

        if docker:
            if config.get("docker_image_base_name", None) is None:
                raise click.UsageError(
                    "docker_image_base_name must be specified in config.txt or ~/.dallingerconfig before you can "
                    "launch an experiment using Docker. For example, you might write the following: \n"
                    "docker_image_base_name = registry.gitlab.developers.cam.ac.uk/mus/cms/psynet-experiment-images"
                )
            _expected_docker_volumes = "${HOME}/psynet-data/assets:/psynet-data/assets"
            if _expected_docker_volumes not in config.get(
                "docker_volumes", ""
            ) and not user_confirms(
                "For deploying PsyNet experiments with Docker, you should typically have the following line "
                "in your config.txt: \n"
                f"docker_volumes = {_expected_docker_volumes}\n"
                "You are advised to change this line then retry launching the experiment. "
                "However, if you're sure you want to continue, enter 'y' and press 'Enter'."
            ):
                raise click.Abort
            if config.get("host") != "0.0.0.0" and not user_confirms(
                "For deploying PsyNet experiments with Docker, you should typically have host = 0.0.0.0 in config.txt. "
                "You are advised to change this line then retry launching the experiment. "
                "However, if you're sure you want to continue, enter 'y' and press 'Enter'."
            ):
                raise click.Abort

        config.set("id", exp.make_uuid(app))

        recruiter = exp.recruiter
        is_mturk = isinstance(recruiter, MTurkRecruiter)
        is_prolific = isinstance(recruiter, ProlificRecruiter)

        if heroku:
            if not exp.asset_storage.heroku_compatible:
                raise AttributeError(
                    f"You can't deploy an experiment to Heroku with this asset storage back-end ({exp.asset_storage}). "
                    "The storage back-end is set in your experiment class with a line like `asset_storage = ...`. "
                    "If you don't need assets in your experiment, you can probably remove the line altogether. "
                    "If you do need assets, you should replace the current storage option with a "
                    "Heroku-compatible backend, for example S3Storage('your-bucket', 'your-root')."
                )
            if is_prolific:
                check_prolific_payment(exp, config)

        if mode == "sandbox":
            run_pre_checks_sandbox(exp, config, is_mturk)
        elif mode == "live":
            run_pre_checks_deploy(exp, config, is_mturk, local_, recruiter)


def run_pre_checks_sandbox(exp, config, is_mturk):
    verify_psynet_requirement()
    check_versions()

    us_only = config.get("us_only")

    if (
        is_mturk
        and us_only
        and not user_confirms(
            "Are you sure you want to sandbox with us_only = True? "
            "Only people with US accounts will be able to test the experiment.",
            default=True,
        )
    ):
        raise click.Abort


@debug.command("heroku")
@click.option(
    "--app", callback=verify_id, default=None, help="Name of the experiment app."
)
@click.option("--docker", is_flag=True, help="Docker mode.")
@click.option("--archive", default=None, help="Optional path to an experiment archive.")
@click.pass_context
def debug__heroku(ctx, app, docker, archive):
    """
    Debug the experiment on Heroku.
    """
    if docker:
        debug__docker_heroku(ctx, app, archive)
    else:
        from dallinger.command_line import sandbox as dallinger_sandbox

        try:
            _pre_launch(
                ctx, mode="sandbox", archive=archive, local_=False, heroku=True, app=app
            )
            # Note: PsyNet bypasses Dallinger's deploy-from-archive system and uses its own, so we set archive=None.
            result = ctx.invoke(dallinger_sandbox, verbose=True, app=app, archive=None)
            _post_deploy(result)
        finally:
            _cleanup_exp_directory()
            reset_console()


def debug__docker_heroku(ctx, app, archive):
    from dallinger.command_line.docker import sandbox as dallinger_sandbox

    try:
        if archive is not None:
            raise NotImplementedError(
                "Unfortunately docker-heroku sandbox doesn't yet support deploying from archive. "
                "This shouldn't be hard to fix..."
            )
        _pre_launch(
            ctx, mode="sandbox", archive=archive, local_=False, docker=True, app=app
        )
        result = ctx.invoke(dallinger_sandbox, verbose=True, app=app)
        _post_deploy(result)
    finally:
        _cleanup_exp_directory()
        reset_console()


@debug.command("ssh")
@click.option(
    "--app", callback=verify_id, required=True, help="Name of the experiment app."
)
@click.option("--archive", default=None, help="Optional path to an experiment archive.")
@option_server
@click.option(
    "--dns-host",
    help="DNS name to use. Must resolve all its subdomains to the IP address specified as ssh host",
)
@click.pass_context
def debug__docker_ssh(ctx, app, archive, server, dns_host):
    """
    Debug the experiment on a remote server via SSH.
    """
    try:
        from dallinger.command_line.docker_ssh import sandbox

        os.environ["DALLINGER_NO_EGG_BUILD"] = "1"

        _pre_launch(
            ctx,
            mode="sandbox",
            archive=archive,
            local_=False,
            ssh=True,
            docker=True,
            server=server,
            app=app,
        )

        # Note: PsyNet bypasses Dallinger's deploy-from-archive system and uses its own, so we set archive_path=None.
        result = ctx.invoke(
            sandbox,
            server=server,
            dns_host=dns_host,
            app_name=app,
            config_options={},
            archive_path=None,
        )

        _post_deploy(result)
    finally:
        _cleanup_exp_directory()


##########
# install #
##########
@psynet.group("install")
def install():
    """
    Install additional PsyNet components.
    """
    pass


@install.command("autocomplete")
def install_autocomplete():
    """
    Install shell tab completion for the psynet command.

    This command automatically detects your shell (bash or zsh) and adds the appropriate
    completion setup to your shell configuration file.
    """
    import os
    import subprocess

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    psynet_root = os.path.dirname(script_dir)
    install_script = os.path.join(
        psynet_root, "psynet", "resources", "scripts", "install-completion.sh"
    )

    if not os.path.exists(install_script):
        raise click.ClickException(
            f"Installation script not found at {install_script}. "
            "Please ensure you're running this command from a proper PsyNet installation."
        )

    # Make the script executable
    os.chmod(install_script, 0o755)

    # Run the installation script
    try:
        subprocess.run([install_script], check=True)
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"Failed to install autocomplete: {e}")
    except FileNotFoundError:
        raise click.ClickException(
            "Could not find bash executable. Please install bash and try again."
        )


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
        text = "Installing base packages and development requirements..."
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

    return Path(_.__file__).parent.parent.resolve()


def psynet_dir():
    import psynet as _

    return Path(_.__file__).parent.parent.resolve()


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
def _estimate(mode):
    from .experiment import import_local_experiment
    from .utils import get_config

    experiment_class = import_local_experiment()["class"]
    wage_per_hour = get_config().get("wage_per_hour")

    config = get_config()
    if not config.ready:
        config.load()

    if mode in ["reward", "both"]:
        max_reward = experiment_class.estimated_max_reward(wage_per_hour)
        log(
            f"Estimated maximum reward for participant: {config.currency}{round(max_reward, 2)}."
        )
    if mode in ["duration", "both"]:
        completion_time = experiment_class.estimated_completion_time(wage_per_hour)
        log(
            f"Estimated time to complete experiment: {pretty_format_seconds(completion_time)}."
        )


@psynet.command()
@click.option(
    "--mode",
    default="both",
    type=click.Choice(["reward", "duration", "both"]),
    help="Type of result. Can be either 'reward', 'duration', or 'both'.",
)
@require_exp_directory
def estimate(mode):
    """
    Estimate the maximum reward for a participant and the time for the experiment to complete, respectively.
    """
    try:
        _estimate(mode)
    except ProgrammingError:
        log("Initialize the database and try again.")
        db.session.rollback()
        init_db(drop_all=True)
        db.session.commit()
        _estimate(mode)


def setup_experiment_variables(experiment_class):
    experiment = experiment_class()
    experiment.setup_experiment_config()
    experiment.setup_experiment_variables()
    return experiment


########################
# generate-constraints #
########################
@psynet.command()
@click.pass_context
@require_requirements_txt
def generate_constraints(ctx):
    """
    Generate the constraints.txt file from requirements.txt.
    """
    from dallinger.command_line import (
        generate_constraints as dallinger_generate_constraints,
    )

    try:
        # We have removed verify_psynet_requirement here because it caused problems for Docker users.
        # Instead, we just run this in the sandbox/deploy prechecks.
        # verify_psynet_requirement()
        ctx.invoke(dallinger_generate_constraints)
    finally:
        reset_console()


@psynet.command()
@require_requirements_txt
def check_constraints():
    "Check whether the experiment contains an appropriate constraints.txt file."
    if os.environ.get("SKIP_DEPENDENCY_CHECK"):
        print("SKIP_DEPENDENCY_CHECK is set so we will skip checking constraints.txt.")
        return

    with yaspin(
        text="Verifying that constraints.txt is up-to-date with requirements.txt...",
        color="green",
    ) as spinner:
        _check_constraints(spinner)
        spinner.ok("✔")

    verify_psynet_requirement()


def _check_constraints(spinner=None):
    directory = os.getcwd()

    # This code comes from dallinger.utils.ensure_constraints_file_presence.
    # Ideally this Dallinger function would be refactored into exportable components.
    requirements_path = Path(directory) / "requirements.txt"
    constraints_path = Path(directory) / "constraints.txt"

    if not requirements_path.exists():
        if spinner:
            spinner.fail("✘")
        raise click.ClickException(
            "Experiment directory is missing a requirements.txt file. "
            "You need to create this file and put your Python package dependencies (e.g. psynet) in it."
        )
        # raise click.Abort()

    generate_constraints_cmd = (
        "    psynet generate-constraints\n"
        "or, if you are using Docker:\n"
        "    bash docker/generate-constraints"
    )

    if not constraints_path.exists():
        if spinner:
            spinner.fail("✘")
        raise click.ClickException(
            "Error: Experiment directory is missing a constraints.txt file. "
            "This file pins all of your experiment's Python package dependencies, both explicit and implicit. "
            "Please check that your requirements.txt file is up-to-date, then generate the constraints.txt file "
            "by running the following command:\n" + generate_constraints_cmd
        )

    requirements_path_hash = md5(requirements_path.read_bytes()).hexdigest()
    if requirements_path_hash not in constraints_path.read_text():
        if spinner:
            spinner.fail("✘")
        raise click.ClickException(
            "The constraints.txt file is not up-to-date with the requirements.txt file. "
            "Please generate a new constraints.txt file by running the following command:\n"
            + generate_constraints_cmd
        )


def verify_psynet_requirement():
    environment_variable = "SKIP_CHECK_PSYNET_VERSION_REQUIREMENT"
    if os.environ.get(environment_variable, None):
        print(
            f"Skipping PsyNet version requirement check because {environment_variable} was non-empty."
        )
        return

    with yaspin(
        text="Verifying PsyNet version in requirements.txt...",
        color="green",
    ) as spinner:
        valid = False
        with open("requirements.txt", "r") as file:
            regexes = [
                "[a-fA-F0-9]{8,40}",
                "v(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)(rc\\d+)?",
                "master",
            ]
            file_content = file.read()
            for regex in regexes:
                match = re.search(
                    r"^psynet(\s?)@(\s?)git\+https:\/\/gitlab.com\/PsyNetDev\/PsyNet(\.git)?@"
                    + regex
                    + "(#egg=psynet)?$",
                    file_content,
                    re.MULTILINE,
                )
                if match is not None:
                    valid = True
                    break

                match = re.search(
                    r"^psynet(\s?)==(\s?)\d+\.\d+\.\d+(rc\d+)?$",
                    file_content,
                    re.MULTILINE,
                )
                if match is not None:
                    valid = True
                    break

        if valid:
            spinner.ok("✔")
        else:
            spinner.color = "red"
            spinner.fail("✗")

        assert valid, (
            "When deploying an experiment, you need to specify PsyNet in an unambiguous way. "
            "This means you can't just give a branch name, e.g. master; you have to specify a particular version "
            "or a commit hash.\n"
            "\n"
            "\nExamples:\n"
            "* psynet==10.1.1\n"
            "* psynet@git+https://gitlab.com/PsyNetDev/PsyNet@v10.1.1#egg=psynet\n"
            "* psynet@git+https://gitlab.com/PsyNetDev/PsyNet@master#egg=psynet\n"  # Only master branch is allowed
            "* psynet@git+https://gitlab.com/PsyNetDev/PsyNet@45f317688af59350f9a6f3052fd73076318f2775#egg=psynet\n"
            "* psynet@git+https://gitlab.com/PsyNetDev/PsyNet@45f31768#egg=psynet\n"
            "You can skip this check by writing `export SKIP_CHECK_PSYNET_VERSION_REQUIREMENT=1` (without quotes) "
            "in your terminal."
        )


##########
# export #
##########


def app_argument(func):
    return click.option(
        "--app",
        default=None,
        required=False,
        help="App id",
    )(func)


def export_arguments(func):
    args = [
        click.option("--path", default=None, help="Path to export directory"),
        click.option("--legacy", is_flag=True, help="Process the export locally"),
        click.option(
            "--assets",
            default="experiment",
            help="Which assets to export; valid values are none, experiment, and all",
        ),
        click.option(
            "--anonymize",
            default="both",
            help="Whether to anonymize the data; valid values are yes, no, or both (the latter exports both ways)",
        ),
        click.option(
            "--n_parallel",
            default=None,
            help="Number of parallel jobs for exporting assets",
        ),
        click.option(
            "--no-source",
            flag_value="no_source",
            default=False,
            help="Skip exporting the experiment's source code",
        ),
        click.option(
            "--username",
            default=None,
            help="This is used to authenticate to the remote server. If missing, this will be guessed from local config files.",
        ),
        click.option(
            "--password",
            default=None,
            help="This is used to authenticate to the remote server. If missing, this will be guessed from local config files.",
        ),
    ]
    for arg in args:
        func = arg(func)
    return func


@psynet.group("export")
@require_exp_directory
def export():
    """
    Export the experiment.
    """
    pass


@export.command("local")
@export_arguments
@click.pass_context
def export__local(ctx=None, **kwargs):
    """
    Export the experiment locally.
    """
    exp_variables = ctx.invoke(experiment_variables, location="local")
    export_(ctx, local=True, exp_variables=exp_variables, **kwargs)


@export.command("heroku")
@export_arguments
@click.option(
    "--app",
    required=True,
    help="Name of the app to export",
)
@click.pass_context
def export__heroku(ctx, app, **kwargs):
    """
    Export the experiment from Heroku.
    """
    exp_variables = ctx.invoke(experiment_variables, location="heroku", app=app)
    export_(ctx, app=app, local=False, exp_variables=exp_variables, **kwargs)


@export.command("ssh")
@click.option(
    "--app",
    required=True,
    help="Name of the app to export",
)
@option_server
@export_arguments
@click.pass_context
def export__docker_ssh(ctx, app, server, **kwargs):
    """
    Export the experiment from a remote server via Docker and SSH.
    """
    exp_variables = ctx.invoke(
        experiment_variables, location="ssh", app=app, server=server
    )
    export_(
        ctx,
        app=app,
        local=False,
        server=server,
        exp_variables=exp_variables,
        docker_ssh=True,
        **kwargs,
    )


def export_(
    ctx,
    exp_variables,
    app=None,
    local=False,
    path=None,
    legacy=False,
    assets="experiment",
    anonymize="both",
    n_parallel=None,
    no_source=False,
    docker_ssh=False,
    server=None,
    dns_host=None,
    username=None,
    password=None,
):
    """
    Export data from an experiment.

    The data is exported into the specified export directory with the following structure:

    ::

        export_path/
        ├── logs.jsonl
        ├── source_code.zip
        ├── regular/
        │   ├── database.zip
        │   ├── data/
        │   └── assets/
        └── anonymous/
            ├── database.zip
            ├── data/
            └── assets/

    logs.jsonl:
        Contains the experiment logs exported from the remote server.
    source_code.zip:
        Contains a snapshot of the experiment source code at the time of deployment.
    regular/:
        Contains non-anonymized data:
            - the database.zip file generated by the default Dallinger export command
            - experiment data in CSV format
            - assets
    anonymous/:
        Contains anonymized data:
            - the database.zip file generated by the default Dallinger export command
            - experiment data in CSV format
            - assets
    """
    from .experiment import import_local_experiment

    deployment_id = exp_variables["deployment_id"]
    assert len(deployment_id) > 0

    remote_exp_label = exp_variables["label"]
    experiment_class = import_local_experiment()["class"]
    local_exp_label = experiment_class.label

    if not remote_exp_label == local_exp_label:
        if not user_confirms(
            f"The remote experiment's label ({remote_exp_label}) does not seem consistent with the "
            f"local experiment's label ({local_exp_label}). Are you sure you are running the export command from "
            "the right experiment folder? If not, the export process is likely to fail. "
            "To continue anyway, press Y and Enter, otherwise just press Enter to cancel."
        ):
            raise click.Abort

    config = get_config()
    if not config.ready:
        config.load()

    if path is None:
        path = experiment_class.export_path(deployment_id)

    path = os.path.expanduser(path)

    if app is None and not local:
        raise ValueError(
            "Either the flag --local must be present or an app name must be provided via --app."
        )

    if app is not None and local:
        raise ValueError("You cannot provide both --local and --app arguments.")

    if assets not in ["none", "experiment", "all"]:
        raise ValueError("--assets must be either none, experiment, or all.")

    if anonymize not in ["yes", "no", "both"]:
        raise ValueError("--anonymize must be either yes, no, or both.")

    if anonymize in ["yes", "no"]:
        anonymize_modes = [anonymize]
    else:
        anonymize_modes = ["yes", "no"]

    source_code_exported = False
    if not legacy:
        experiment_url = get_experiment_url(app, server)
        params = {
            "type": "psynet",
            "anonymize": anonymize,
            "assets": assets,
        }
        export_endpoint = f"{experiment_url}/dashboard/export/download?" + urlencode(
            params
        )
        with yaspin(text="Requesting export from dashboard", color="green") as spinner:
            response = requests.get(
                export_endpoint,
                auth=(config.get("dashboard_user"), config.get("dashboard_password")),
            )
            spinner.ok("✔")
        os.makedirs(path, exist_ok=True)
        zip_path = os.path.join(path, "data.zip")
        if response.status_code == 200:
            with open(zip_path, "wb") as f:
                f.write(response.content)
            # unzip the file
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(path)
            log(f"Export complete. You can find your results at: {path}")
        else:
            log(
                f"Failed to export data. Response: {response.reason} ({response.status_code})"
            )
            try:
                message = response.json().get("message")
                log(f"Reason: {message}.")
            except json.JSONDecodeError as e:
                log(
                    f"Additionally, decoding JSON data from the response failed with '{str(e)}'"
                    f"\nResponse content: {response.content}"
                )
            log("You can add the --legacy flag to retry the export locally.")
    else:
        for anonymize_mode in anonymize_modes:
            _anonymize = anonymize_mode == "yes"
            _export_source_code = not (source_code_exported or no_source)
            _export_(
                ctx,
                app,
                local,
                path,
                assets,
                _anonymize,
                _export_source_code,
                n_parallel,
                docker_ssh,
                server,
                dns_host,
                username,
                password,
            )
            if _export_source_code:
                source_code_exported = True


def _export_(
    ctx,
    app,
    local,
    export_path,
    assets,
    anonymize: bool,
    export_source_code: bool,
    n_parallel=None,
    docker_ssh=False,
    server=None,
    dns_host=None,
    username=None,
    password=None,
):
    """
    An internal version of the export version where argument preprocessing has been done already.
    """
    database_zip_path = export_database(
        ctx, app, local, export_path, anonymize, docker_ssh, server, dns_host
    )
    export_data(local, anonymize, database_zip_path, export_path)

    if assets != "none":
        experiment_assets_only = assets == "experiment"
        include_on_demand_assets = assets == "all"
        export_assets(
            export_path,
            anonymize,
            experiment_assets_only,
            include_on_demand_assets,
            n_parallel,
            server,
            local,
        )

    if export_source_code:
        _export_source_code(app, local, server, export_path, username, password)

    # Export logs.jsonl file for SSH exports
    if docker_ssh and server:
        export_logs(app, server, export_path)

    log(f"Export complete. You can find your results at: {export_path}")


def export_logs(app, server, export_path):
    """Export the logs.jsonl file from the remote server."""
    from dallinger.command_line.docker_ssh import CONFIGURED_HOSTS, Executor, get_sftp

    server_info = CONFIGURED_HOSTS[server]
    ssh_host = server_info["host"]
    ssh_user = server_info.get("user")

    local_logs_path = os.path.join(export_path, "logs.jsonl")

    log(f"Exporting logs to {local_logs_path}")

    try:
        sftp = get_sftp(ssh_host, ssh_user)
        executor = Executor(ssh_host, ssh_user, app)

        remote_home_path = executor.run("echo $HOME", raise_=False).strip()
        remote_logs_path = f"{remote_home_path}/dallinger/{app}/logs.jsonl"

        sftp.get(remote_logs_path, local_logs_path)

        with yaspin(text="Logs exported.", color="green") as spinner:
            spinner.ok("✔")

    except Exception as e:
        log(f"Warning: Failed to export logs from {remote_logs_path}: {str(e)}")


def _export_source_code(app, local, server, export_path, username, password):
    import requests

    config = get_config()
    if not config.ready:
        config.load()

    username = username or config.get("dashboard_user", None)
    password = password or config.get("dashboard_password", None)

    if not all([username, password]):
        if not click.confirm(
            "\nPsyNet failed to find dashboard credentials in your local config files. "
            "These dashboard credentials are needed to authenticate to the remote server "
            "in order to download the experiment's source code. "
            "You can provide these credentials now in a follow-up dialog; you can find these "
            "credentials printed to your console as part of the experiment deployment command. "
            "Alternatively, you can choose to skip downloading the source code. "
            "\nDo you want to proceed with entering username and password now? "
            "Enter 'y', or 'n' to skip downloading the source code.",
            default=True,
            abort=False,
        ):
            log("WARNING: Experiment source code could not be downloaded.")
            return

    log(
        "Downloading source code... (if this fails, you can skip this step by appending `--no-source` to your `psynet export` command)"
    )
    if local:
        url = "http://localhost:5000"
    else:
        if server:
            url = f"https://{app}.{server}"
        else:
            url = HerokuApp(app).url

    url += "/download_source"
    source_code_zip_path = os.path.join(export_path, "source_code.zip")

    while True:
        if not all([username, password]):
            username = click.prompt("Enter dashboard username")
            password = click.prompt("Enter dashboard password", hide_input=True)

        with yaspin(
            text=f"Requesting source code from {url}", color="green"
        ) as spinner:
            response = requests.get(url, auth=(username, password))

        if response.status_code == 200:
            with open(source_code_zip_path, "wb") as f:
                f.write(response.content)
            spinner.ok("✔")
            log(f"Experiment source code saved to {source_code_zip_path}.")
            break
        elif response.status_code == 401:
            try_again = click.confirm(
                "Authentication failed.\nPress ENTER to try again or 'n' to skip downloading the source code.",
                default=True,
                abort=False,
            )
            if not try_again:
                log("Skipped downloading the source code.")
                break
            # Reset the credentials so the user gets another chance to enter them correctly
            username, password = None, None
        else:
            spinner.color = "red"
            spinner.fail("✘")
            click.confirm(
                "Experiment source code could not be downloaded."
                "\nPress ENTER to continue with the remainder of data export, ignoring the source code."
                "\nNote: To skip exporting the source code in the future, add `--no-source` option to your `psynet export` command.",
                default=True,
                prompt_suffix="",
                show_default=False,
            )
            log(
                f"WARNING: Failed to download experiment source code. Response: {response.reason} ({response.status_code})"
            )
            try:
                message = response.json().get("message")
                log(f"\nReason: {message}.")
            except json.JSONDecodeError as e:
                log(
                    f"\nAdditionally, decoding JSON data from the response failed with '{str(e)}'"
                    f"\nResponse content: {response.content}"
                )
            break


def export_database(
    ctx, app, local, export_path, anonymize, docker_ssh, server, dns_host
):
    if local:
        app = "local"

    subdir = "anonymous" if anonymize else "regular"

    database_zip_path = os.path.join(export_path, subdir, "database.zip")

    log(f"Exporting raw database content to {database_zip_path}")

    from dallinger import data as dallinger_data
    from dallinger import db as dallinger_db

    # if docker_ssh:
    #     from dallinger.command_line.docker_ssh import export as dallinger_export
    # else:
    #     from dallinger.data import export as dallinger_export
    # Dallinger hard-codes the list of table names, but this list becomes out of date
    # if we add custom tables, so we have to patch it.
    dallinger_data.table_names = sorted(dallinger_db.Base.metadata.tables.keys())

    with tempfile.TemporaryDirectory() as tempdir:
        with working_directory(tempdir):
            if docker_ssh:
                from dallinger.command_line.docker_ssh import export

                ctx.invoke(
                    export,
                    server=server,
                    app=app,
                    no_scrub=not anonymize,
                )
            else:
                from dallinger.command_line import export

                ctx.invoke(
                    export,
                    app=app,
                    local=local,
                    no_scrub=not anonymize,
                )

            shutil.move(
                os.path.join(tempdir, "data", f"{app}-data.zip"),
                make_parents(database_zip_path),
            )

    with yaspin(text="Completed.", color="green") as spinner:
        spinner.ok("✔")

    return database_zip_path


def export_data(local, anonymize, database_zip_path, export_path):
    subdir = "anonymous" if anonymize else "regular"
    data_path = os.path.join(export_path, subdir, "data")

    if not local:
        log("Populating the local database with the downloaded data.")
        populate_db_from_zip_file(database_zip_path)

    dump_db_to_disk(data_path, scrub_pii=anonymize)

    with yaspin(text="Completed.", color="green") as spinner:
        spinner.ok("✔")


def populate_db_from_zip_file(zip_path):
    from dallinger import data as dallinger_data

    db.session.commit()  # The process can freeze without this
    init_db(drop_all=True)
    dallinger_data.ingest_zip(zip_path)


def export_assets(
    export_path,
    anonymize,
    experiment_assets_only,
    include_on_demand_assets,
    n_parallel,
    server,
    local,
):
    # Assumes we already have loaded the experiment into the local database,
    # as would be the case if the function is called from psynet export.
    from .data import export_assets as _export_assets

    log(f"Exporting assets to {export_path}")

    include_private = not anonymize
    subdir = "anonymous" if anonymize else "regular"
    asset_path = os.path.join(export_path, subdir, "assets")

    _export_assets(
        asset_path,
        include_private,
        experiment_assets_only,
        include_on_demand_assets,
        n_parallel,
        server,
        local,
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


###########
# load #
###########
@psynet.command()
@click.argument("path")
@require_exp_directory
def load(path):
    "Populates the local database with a provided zip file."
    from .experiment import import_local_experiment

    import_local_experiment()
    populate_db_from_zip_file(path)


# Example usage: psynet generate-config --recruiter mturk
@psynet.command(
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.pass_context
def generate_config(ctx):
    """
    Generate a configuration file for the experiment.
    """
    path = os.path.expanduser("~/.dallingerconfig")
    if os.path.exists(path):
        if not user_confirms(
            f"Are you sure you want to overwrite your existing config file at '{path}'?",
            default=False,
        ):
            raise click.Abort

    with open(path, "w") as file:
        file.write("[Config variables]\n")
        assert len(ctx.args) % 2 == 0
        while len(ctx.args) > 0:
            value = ctx.args.pop()
            key = ctx.args.pop()
            assert not value.startswith("--")
            assert key.startswith("--")
            key = key[2:]
            file.write(f"{key} = {value}\n")


@psynet.command()
@require_exp_directory
def update_scripts():
    """
    To be run in an experiment directory; updates a collection of template scripts and help files to their
    latest PsyNet versions.
    """
    update_scripts_()


def update_scripts_():
    """
    To be run in an experiment directory; updates a collection of template scripts and help files to their
    latest PsyNet versions.
    """
    click.echo(f"Updating PsyNet scripts in ({os.getcwd()})...")

    Path(".vscode").mkdir(exist_ok=True)
    Path(".github/workflows").mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        ".gitignore",
        ".dockerignore",
        "Dockerfile",
        "README.md",
        "__init__.py",
        "pytest.ini",
        "test.py",
        ".github/workflows/test.yml",
        ".vscode/launch.json",
    ]
    for file in files_to_copy:
        click.echo(f"...updating {file}.")
        with resources.as_file(
            resources.files("psynet") / f"resources/experiment_scripts/{file}"
        ) as path:
            shutil.copyfile(
                path,
                file,
            )

    click.echo("...updating Dockertag.")
    with open("Dockertag", "w") as file:
        file.write(os.path.basename(os.getcwd()))
        file.write("\n")

    directories_to_copy = ["docs", "docker"]
    for dir in directories_to_copy:
        click.echo(f"...updating {dir} directory.")
        if Path(dir).exists():
            shutil.rmtree(dir, ignore_errors=True)
        with resources.as_file(
            resources.files("psynet") / f"resources/experiment_scripts/{dir}"
        ) as path:
            shutil.copytree(
                path,
                dir,
                dirs_exist_ok=True,
            )
    os.system("chmod +x docker/*")


@psynet.group("destroy")
def destroy():
    """
    Destroy the experiment.
    """
    pass


@destroy.command("heroku")
@click.option("--app", default=None, callback=verify_id, help="Experiment id")
@click.option(
    "--expire-hit/--no-expire-hit",
    flag_value=True,
    default=None,
    help="Expire any MTurk HITs associated with this experiment.",
)
@click.pass_context
def destroy__heroku(ctx, app, expire_hit):
    """
    Destroy the experiment on Heroku.
    """
    _destroy(
        ctx,
        dallinger.command_line.destroy,
        dallinger.command_line.expire,
        app=app,
        expire_hit=expire_hit,
    )


def user_confirms(question, default=False):
    """
    Like click.confirm but safe for using within our wrapped Docker commands.
    """
    print(question + " Enter 'y' for yes, 'n' for no.")
    return click.confirm("", default=default)


def _destroy(
    ctx,
    f_destroy,
    f_expire,
    app,
    expire_hit,
    server=None,
    ask_for_confirmation=True,
):
    confirmed = (
        user_confirms(
            "Would you like to delete the app from the web server?", default=True
        )
        if ask_for_confirmation
        else True
    )

    if confirmed:
        with yaspin("Destroying app...") as spinner:
            try:
                kwargs = {"app": app}
                kwargs = {**kwargs, "server": server} if server else kwargs
                if expire_hit in get_args(f_destroy):
                    ctx.invoke(
                        f_destroy,
                        expire_hit=False,
                        **kwargs,
                    )
                else:
                    ctx.invoke(
                        f_destroy,
                        **kwargs,
                    )
                spinner.ok("✔")
            except subprocess.CalledProcessError:
                spinner.fail("✗")
                click.echo(
                    "Failed to destroy the app. Maybe it was already destroyed, or the app name was wrong?"
                )

    if expire_hit is None:
        if user_confirms(
            "Would you like to look for a related MTurk HIT to expire?", default=True
        ):
            expire_hit = True

    if expire_hit:
        sandbox = user_confirms("Is this a sandbox HIT?", default=True)

        with yaspin("Expiring hit...") as spinner:
            ctx.invoke(
                f_expire,
                app=app,
                sandbox=sandbox,
            )
            spinner.ok("✔")


@destroy.command("ssh")
@click.option("--app", default=None, help="Experiment id")
@click.argument("apps", required=False, nargs=-1)
@option_server
@click.option(
    "--expire-hit",
    flag_value=True,
    default=False,
    help="Expire any MTurk HITs associated with this experiment.",
)
@click.pass_context
def destroy__docker_ssh(ctx, app, apps, server, expire_hit):
    """
    Destroy the experiment on a remote server via SSH.
    """
    from dallinger.command_line import expire
    from dallinger.command_line.docker_ssh import destroy

    example_usage = "`psynet destroy ssh <app> <app> [--server <server>]`"
    if app:
        assert len(apps) == 0, "You cannot provide both --app and a list of apps."
        click.echo(f"Consider using the batch syntax: {example_usage}")
        _destroy(
            ctx,
            destroy,
            expire,
            app=app,
            expire_hit=expire_hit,
            server=server,
        )
    if len(apps) > 0:
        assert app is None, "You cannot provide both --app and a list of apps."
        confirmation = f"""
            Are you sure you want to remove {len(apps)} apps on {server} ({apps})?
            """
        if click.confirm(confirmation, abort=True):
            for app in apps:
                _destroy(
                    ctx,
                    destroy,
                    expire,
                    app=app,
                    expire_hit=expire_hit,
                    server=server,
                    ask_for_confirmation=False,
                )


@psynet.group("apps")
def apps():
    """
    List the apps on the server.
    """
    pass


@apps.command("ssh")
@option_server
@click.pass_context
def apps__docker_ssh(ctx, server):
    from dallinger.command_line.docker_ssh import apps

    _apps = ctx.invoke(apps, server=server)
    if len(_apps) == 0:
        click.echo("No apps found.")


@psynet.group("stats")
def stats():
    """
    Show the stats of the experiment.
    """
    pass


@stats.command("ssh")
@option_server
@click.pass_context
def stats__docker_ssh(ctx, server):
    from dallinger.command_line.docker_ssh import stats

    ctx.invoke(stats, server=server)


@psynet.group("test")
@click.pass_context
@require_exp_directory
def test(ctx):
    """
    Test the experiment.
    """
    pass


_test_options = {}

_test_options["existing"] = click.option(
    "--existing",
    is_flag=True,
    help="Use this flag if the experiment server is already running",
)

_test_options["n_bots"] = click.option(
    "--n-bots",
    help="Number of bots to use in the test. If not specified, will default to Experiment.test_n_bots.",
)

_test_options["parallel"] = click.option(
    "--parallel",
    is_flag=True,
    help=(
        "Forces the tests to be run in parallel, overriding the default specified in the Experiment class. "
        "Only relevant if the number of bots is greater than 1. Does the opposite of --serial."
    ),
)

_test_options["serial"] = click.option(
    "--serial",
    is_flag=True,
    help=(
        "Forces the tests to be run serially, overriding the default specified in the Experiment class. "
        "Does the opposite of --parallel."
    ),
)

_test_options["stagger"] = click.option(
    "--stagger",
    help="Time interval to wait (in seconds) between instantiating each parallel bot.",
)

_test_options["real_time"] = click.option(
    "--real-time",
    is_flag=True,
    help="Instead of running each bot through the experiment as fast as possible, follow the timings in time_estimate instead.",
)


@test.command("local")
@_test_options["existing"]
@_test_options["n_bots"]
@_test_options["parallel"]
@_test_options["serial"]
@_test_options["stagger"]
@_test_options["real_time"]
def test__local(
    existing=False,
    n_bots=None,
    parallel=None,
    serial=None,
    stagger=None,
    real_time=None,
):
    """
    Test the experiment locally.
    """
    assert not (parallel and serial)

    from psynet.experiment import get_experiment

    exp = get_experiment()

    if n_bots:
        n_bots = int(n_bots)
        exp.test_n_bots = n_bots

    if parallel:
        exp.test_mode = "parallel"
    elif serial:
        exp.test_mode = "serial"

    if stagger:
        exp.test_parallel_stagger_interval_s = float(stagger)

    if real_time:
        exp.test_real_time = True

    if existing:
        exp.test_experiment()
    else:
        import pytest

        exit_code = pytest.main(["test.py"])
        if exit_code != 0:
            # Use sys.exit() to ensure that the exit code is propagated to the shell.
            # This is helpful for CI pipelines, where we want to fail the build if the tests fail.
            sys.exit(exit_code)


@test.command("ssh")
@click.option("--app", required=True, help="Name of the experiment app.")
@option_server
@_test_options["n_bots"]
@_test_options["parallel"]
@_test_options["serial"]
@_test_options["stagger"]
@_test_options["real_time"]
@click.pass_context
def test__docker_ssh(
    ctx,
    app,
    server,
    n_bots=None,
    parallel=None,
    serial=None,
    stagger=None,
    real_time=None,
):
    """
    Runs experiment tests on the remote server.
    Assumes that the app has already been launched on the remote server using ``psynet debug ssh``.

    Running this command will not reset the database to a vanilla state, but will instead just use the state
    that exists already. This may cause strange results if the tests are run multiple times.

    Note: this feature is currently experimental and the API is likely to change without warning.
    """
    from dallinger.command_line.docker_ssh import Executor

    cmd = "psynet test local --existing"

    if n_bots:
        cmd += f" --n-bots {n_bots}"

    if parallel:
        cmd += " --parallel"

    if serial:
        cmd += " --serial"

    if stagger:
        cmd += " --stagger"

    if real_time:
        cmd += " --real-time"

    server_info = CONFIGURED_HOSTS[server]
    ssh_host = server_info["host"]
    ssh_user = server_info.get("user")
    executor = Executor(ssh_host, user=ssh_user)
    executor.run_and_echo(f"cd ~/dallinger/{app} && docker compose exec web {cmd}")


@psynet.command()
@click.pass_context
@require_exp_directory
def simulate(ctx):
    """
    Generates simulated data for an experiment by running the experiment's regression test
    and exporting the resulting data.
    """
    # No need to catch the exit code here, because test__local now uses sys.exit()
    # if an error occurs.
    ctx.invoke(test__local)

    ctx.invoke(
        export__local,
        # TODO - maybe legacy is not the best name for this parameter...
        legacy=True,  # required because the server is not running any more, so we need to go direct to the DB
        no_source=True,
        path="data/simulated_data",
    )


@psynet.command(name="list-experiment-dirs")
@click.option("--for-ci-tests", is_flag=True)
@click.option("--ci-node-total", default=None, type=int)
@click.option("--ci-node-index", default=None, type=int)
def _list_experiment_dirs(for_ci_tests=False, ci_node_total=None, ci_node_index=None):
    """
    Lists the directories of all the experiments that are available under the 'demos' directory,
    plus those inside the 'tests/experiments' directory.
    """
    for directory in list_experiment_dirs(
        for_ci_tests=for_ci_tests,
        ci_node_total=ci_node_total,
        ci_node_index=ci_node_index,
    ):
        print(directory)


@psynet.command(name="list-isolated-tests")
@click.option("--ci-node-total", default=None, type=int)
@click.option("--ci-node-index", default=None, type=int)
def _list_isolated_tests(ci_node_total=None, ci_node_index=None):
    """
    Lists the directories of all the demo experiments that are available.
    """
    for test_ in list_isolated_tests(
        ci_node_total=ci_node_total,
        ci_node_index=ci_node_index,
    ):
        print(test_)


# Recruiter specific
@psynet.group("lucid")
@click.pass_context
def lucid(ctx):
    """
    Manage Lucid surveys.
    """
    pass


@lucid.command("cost")
@click.argument("survey_number", required=True)
@click.pass_context
def lucid__cost(ctx, survey_number):
    """
    Show the cost of a Lucid survey.
    """
    summary = get_lucid_service().get_cost(survey_number)
    c = summary["currency"]
    print(bold(f"Cost summary for survey: {survey_number}"))
    print(f"Sample:\t{summary['sample']} {c}")
    print(f"Fee:\t{summary['fee']} {c}")
    print(bold(f"Total:\t{summary['total']} {c}"))
    print(
        f"Total completes: {summary['total_completes']}, price per complete: {round(summary['cost_per_complete'], 2)} {c}"
    )


@lucid.command("compensate")
@click.argument("survey_number", required=True, nargs=1)
@click.argument("rids", required=True, nargs=-1)
@click.pass_context
def lucid__compensate(ctx, survey_number, rids):
    """
    Compensate participants for a Lucid survey.
    """
    rids = list(rids)
    confirmation = f"""
    Are you sure you want to compensate {len(rids)} participants?
    Note: This will ONLY mark these participants as completed, all other participants will be marked as TERMINATED.
    """
    if click.confirm(confirmation, abort=True):
        get_lucid_service().reconcile(survey_number, rids)
        log(
            f"{len(rids)} participants have been approved for survey number: {survey_number}"
        )


@lucid.command("locale")
@click.pass_context
def lucid__locale(ctx):
    """
    Show the locales of a Lucid survey.
    """
    print(
        get_lucid_service().get_lucid_country_language_lookup().to_markdown(index=False)
    )


@lucid.command("estimate")
@click.option(
    "--language-code",
    help="Lucid language code; see `psynet lucid locale`",
    required=True,
)
@click.option(
    "--country-code",
    help="Lucid country code; see `psynet lucid locale`",
    required=True,
)
@click.option("--completes", help="Number of completes", type=int, required=True)
@click.option("--wage", help="Wage per hour", type=float, required=True)
@click.option(
    "--survey-length",
    help="Length of survey in minutes (i.e., the expected time of a user to complete the survey)",
    type=int,
    required=True,
)
@click.option(
    "--duration",
    help="Duration how long the survey is put on the marketplace",
    type=int,
    required=True,
)
@click.option(
    "--delay", type=int, default=2 * 24 * 7, help="Delay in hours (default: 2 weeks)"
)
@click.option("--incidence-rate", type=float, default=0.6, help="Incidence rate")
@click.option("--collects-pii", is_flag=True, help="Survey collects PII")
@click.option("--qualifications", help="Path to qualifications JSON file", default=None)
@click.pass_context
def lucid__estimate(
    ctx,
    language_code,
    country_code,
    completes,
    wage,
    survey_length,
    duration,
    delay,
    incidence_rate,
    collects_pii,
    qualifications,
):
    """
    Estimate the cost of a Lucid survey.
    """
    if qualifications is not None:
        with open(qualifications, "r") as file:
            qualifications = json.load(file)
    params = locals()
    params.pop("ctx")  # pop context
    get_lucid_service().estimate(**params)


@lucid.command("status")
@click.argument("survey_number", required=True)
@click.argument("status", required=True)
@click.pass_context
def lucid__status(ctx, survey_number, status):
    """
    Change the status of a Lucid survey.
    """
    available_statuses = ["live", "paused", "completed", "archived", "pending"]
    assert (
        status in available_statuses
    ), f"Invalid status: {status}, pick from: {available_statuses}"
    if status == "completed":
        status = "complete"
    get_lucid_service().change_status(survey_number, status)


@lucid.command("qualifications")
@click.argument("survey_number", required=True)
@click.option("--path", default=None, help="Path to save the qualifications to")
@click.pass_context
def get_qualifications(ctx, survey_number, path):
    """
    Get the qualifications of a Lucid survey.
    """
    qualifications = get_lucid_service().get_qualifications(survey_number)
    json_string = json.dumps(qualifications, indent=4)
    if path:
        with open(path, "w") as file:
            file.write(json_string)
        log(f"Qualifications have been saved to {path}")
    else:
        print(json_string)


def _get_local_pandas():
    try:
        import pandas as pd

        return pd
    except ImportError:
        raise ImportError(
            "This command requires the pandas library. Install it with 'pip install pandas'"
        )


@lucid.command("studies")
@click.option("--live", is_flag=True, help="List live experiments")
@click.option("--paused", is_flag=True, help="List paused experiments")
@click.option("--completed", is_flag=True, help="List complete experiments")
@click.option("--archived", is_flag=True, help="List archived experiments")
@click.option("--pending", is_flag=True, help="List pending experiments")
@click.option("--n", default=10, help="Number of experiments to list")
@click.option("--order", default="id", help="Sort by column")
@click.pass_context
def lucid__list_studies(ctx, live, paused, completed, archived, pending, n, order):
    """
    List the studies of a Lucid survey.
    """
    pd = _get_local_pandas()
    assert n > 0 and n < 200
    allowed_statuses = []
    if live:
        allowed_statuses.append("live")
    if paused:
        allowed_statuses.append("paused")
    if completed:
        allowed_statuses.append("complete")
    if archived:
        allowed_statuses.append("archived")
    if pending:
        allowed_statuses.append("pending")
    all_studies = pd.DataFrame(
        get_lucid_service().list_studies(allowed_statuses, n, order_by=order)
    )
    if len(all_studies) == 0:
        print("No studies found with the given filters.")
        return
    all_studies["completes"] = all_studies.apply(
        lambda x: f"{x['total_completes']} / {x['expected_completes']}", axis=1
    )
    all_studies.create_date = all_studies.create_date.apply(
        lambda x: pd.to_datetime(x).strftime("%Y-%m-%d")
    )
    all_studies = all_studies[
        ["id", "create_date", "status", "locale", "completes", "total_screens", "name"]
    ]
    print(all_studies.to_markdown(index=False))


@lucid.command("submissions")
@click.argument("survey_number", required=True)
@click.option("--order", default="entry_date", help="Sort by column")
@click.pass_context
def lucid__list_submissions(ctx, survey_number, order):
    """
    List the submissions of a Lucid survey.
    """
    pd = _get_local_pandas()
    submissions = pd.DataFrame(get_lucid_service().get_submissions(survey_number))
    submissions.client_status = submissions.client_status.apply(
        lambda x: BaseLucidRecruiter.client_codes.get(x, "Unknown")
    )
    submissions.fulcrum_status = submissions.fulcrum_status.apply(
        lambda x: BaseLucidRecruiter.market_place_codes.get(x, "Unknown")
    )
    submissions.drop(columns=["panelist_id"], inplace=True)
    submissions.entry_date = pd.to_datetime(submissions.entry_date)
    submissions.last_date = pd.to_datetime(submissions.last_date)
    submissions["duration"] = (
        submissions.last_date - submissions.entry_date
    ).dt.total_seconds() / 60
    submissions.drop(columns=["last_date"], inplace=True)
    submissions = submissions.sort_values(by=order, ascending=False)
    print(submissions.to_markdown(index=False))


class ListOfStrings(click.ParamType):
    name = "list_of_strings"

    def convert(self, value, param, ctx):
        if value is None:
            return []
        return value.replace(",", " ").split()


@psynet.command("translate")
@click.argument("locales", nargs=-1)
@click.option(
    "--force", is_flag=True, help="Force retranslation of existing translations"
)
@click.option(
    "--skip-pot",
    is_flag=True,
    help="Skips the generation of the .pot file; useful for checking failed translations",
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    default=False,
    help="Continue translating even if an error occurs",
)
@click.option(
    "--translator",
    default=None,
    help="The translator to use for translation. If not specified, the default translator will be used.",
)
def translate(locales, force, skip_pot, continue_on_error, translator):
    """
    Inspects the code in the current directory and generates automatic translations for a given set of languages.

    This command should be run from the root of either an experiment or a package.
    If run from an experiment, the translations will be saved in the experiment's "locales" directory.
    If run from a package, the translations will be saved in "{package_src_directory}/locales".

    Note: Currently only .py and .html files are translated.

    Parameters
    ----------
    languages :
        The target languages, specified as space-separated language codes
    force : bool
        If True, force retranslation of existing translations
    skip_pot : bool
        If True, skip the generation of the translation template (.pot file); useful for checking failed translations
        since recreating the template takes some time, but the translation did not change.

    Example
    -------

    psynet translate fr de
        Generate translations for French and German.
    """
    import warnings

    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from psynet.translation.translate import translate_experiment, translate_package
    from psynet.translation.translators import get_translator_from_name

    translator = get_translator_from_name(translator)

    if in_python_package():
        click.echo(
            bold(f"Found a package called '{get_package_name()}' to translate")
            + f" at {os.getcwd()}."
        )
        translate_package(
            locales,
            force=force,
            skip_pot=skip_pot,
            continue_on_error=continue_on_error,
            translator=translator,
        )

    elif experiment_available():
        click.echo(bold("Found an experiment to translate") + f" at {os.getcwd()}.")
        translate_experiment(
            locales,
            force=force,
            skip_pot=skip_pot,
            continue_on_error=continue_on_error,
            translator=translator,
        )

    else:
        raise RuntimeError(
            f"The current directory {os.getcwd()} does not seem to be the root of an experiment or a package."
        )
