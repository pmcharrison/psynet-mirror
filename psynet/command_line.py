import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from shutil import rmtree, which

import click
import dallinger.command_line.utils
import psutil
import psycopg2
from dallinger import db
from dallinger.command_line.docker_ssh import (
    CONFIGURED_HOSTS,
    remote_postgres,
    server_option,
)
from dallinger.command_line.utils import verify_id
from dallinger.config import get_config
from dallinger.heroku.tools import HerokuApp
from dallinger.recruiters import ProlificRecruiter
from dallinger.version import __version__ as dallinger_version
from pkg_resources import resource_filename
from yaspin import yaspin

from psynet import __path__ as psynet_path
from psynet import __version__

from . import deployment_info
from .data import drop_all_db_tables, dump_db_to_disk, ingest_zip, init_db
from .redis import redis_vars
from .serialize import serialize, unserialize
from .utils import (
    get_args,
    make_parents,
    pretty_format_seconds,
    run_subprocess_with_live_output,
    working_directory,
)

dallinger.command_line.utils.header = ""


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

        The online human behaviour lab of the future
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
    subprocess.call("stty sane", shell=True)


###########
# prepare #
###########
@psynet.command()
def prepare():
    _prepare()


def _prepare():
    try:
        from dallinger import db

        from .experiment import import_local_experiment

        redis_vars.clear()
        db.init_db(drop_all=True)
        experiment_class = import_local_experiment().get("class")
        experiment_instance = experiment_class.new(session=None)
        experiment_instance.pre_deploy()
        db.session.commit()
        clean_sys_modules()
        return experiment_class
    finally:
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
@server_option
def experiment_variables(location, app, server):
    with db_connection(location, app, server) as connection:
        return _experiment_variables(connection, echo=True)


@contextmanager
def db_connection(location, app=None, server=None):
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
    with get_db_uri(location, app, server) as uri:
        click.echo(uri)
        return uri


@psynet.group("debug")
@click.pass_context
def debug(ctx):
    pass


@psynet.command(
    context_settings=dict(
        allow_extra_args=True,
        ignore_unknown_options=True,
    )
)
def sandbox(*args, **kwargs):
    raise click.ClickException(
        "`psynet sandbox` has been replaced with `psynet debug heroku`, please use the latter."
    )


@debug.command("local")
# @click.option("--app", default=None, help="Name of the experiment app (required for non-local deployments)")
# @click.option("--server", default=None, help="Name of the remote server (only relevant for ssh deployments)")
@click.option("--docker", is_flag=True, help="Docker mode.")
@click.option("--archive", default=None, help="Optional path to an experiment archive.")
@click.option("--legacy", is_flag=True, help="Legacy mode.")
@click.option("--no-browsers", is_flag=True, help="Skip opening browsers.")
# @click.option(
#     "--skip-flask",
#     is_flag=True,
#     help="Skip launching Flask, so that Flask can be managed externally. Does not apply when legacy=True",
# )
@click.pass_context
def debug__local(ctx, docker, archive, legacy, no_browsers):
    """
    Debug the experiment locally (this should normally be your first choice).
    """
    if not ctx:
        from click import Context

        ctx = Context(debug)

    if legacy and docker:
        raise click.UsageError(
            "It is not possible to select both --legacy and --docker modes simultaneously."
        )

    _pre_launch(
        ctx, mode="debug", archive=archive, local_=True, docker=docker, app=None
    )
    _cleanup_before_debug()

    try:
        if legacy:
            # Warning: _debug_legacy can fail if the experiment directory is imported before _debug_legacy is called.
            # We therefore need to avoid accessing config variables, calling import_local_experiment, etc.
            # This problem manifests specifically when the experiment contains custom tables.
            _debug_legacy(ctx, archive=archive, no_browsers=no_browsers)
        elif docker:
            _debug_docker(ctx, archive=archive, no_browsers=no_browsers)
        else:
            _debug_auto_reload(ctx, archive=archive, no_browsers=no_browsers)
    finally:
        kill_psynet_worker_processes()


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
    try:
        shutil.rmtree(".deploy")
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
        and not user_confirms(
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
    log("Preparing for launch...")

    redis_vars.clear()
    deployment_info.init(
        redeploying_from_archive=archive is not None,
        mode=mode,
        is_local_deployment=local_,
        is_ssh_deployment=ssh,
    )

    if ssh:
        server_info = CONFIGURED_HOSTS[server]

        ssh_host = server_info["host"]
        ssh_user = server_info.get("user")

        deployment_info.write(ssh_host=ssh_host, ssh_user=ssh_user)

    log("Running pre-launch checks...")
    run_pre_checks(mode, local_, heroku, docker, app)
    log(header)

    # Always use the Dallinger version in requirements.txt, not the local editable one
    os.environ["DALLINGER_NO_EGG_BUILD"] = "1"

    if docker:
        if Path("Dockerfile").exists():
            # Tell Dallinger not to rebuild constraints.txt, because we'll manage this within the Docker image
            os.environ["SKIP_DEPENDENCY_CHECK"] = "1"

    if not archive:
        if local_:
            run_prepare_in_subprocess()
        else:
            ctx.invoke(prepare)


@psynet.group("deploy")
def deploy():
    pass


@deploy.command("heroku")
@click.option("--app", required=True, help="Experiment id")
@click.option("--archive", default=None, help="Optional path to an experiment archive")
@click.option("--docker", is_flag=True, default=False, help="Deploy using Docker")
@click.pass_context
def deploy__heroku(ctx, app, archive, docker):
    if docker:
        _deploy__docker_heroku(ctx, app, archive)

    try:
        from dallinger.command_line import deploy as dallinger_deploy

        _pre_launch(
            ctx, mode="live", archive=archive, local_=False, heroku=True, app=app
        )
        result = ctx.invoke(dallinger_deploy, verbose=True, app=app, archive=archive)
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
@click.option("--app", required=True, help="Experiment id")
@click.option("--archive", default=None, help="Optional path to an experiment archive")
@server_option
@click.option(
    "--dns-host",
    help="DNS name to use. Must resolve all its subdomains to the IP address specified as ssh host",
)
@click.pass_context
def deploy__docker_ssh(ctx, app, archive, server, dns_host):
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

        result = ctx.invoke(
            dallinger_docker_ssh_deploy,
            mode="sandbox",  # TODO - but does this even matter?
            server=server,
            dns_host=dns_host,
            app_name=app,
            archive_path=archive,
            # config_options -- this could be useful
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
    if deployment_info.read("mode") == "live":
        _export_code(directory)


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


def _export_code(directory):
    file = directory.joinpath("code")
    with yaspin(
        text=f"Saving a snapshot of the code to {file}...", color="green"
    ) as spinner:
        shutil.make_archive(file, "zip", os.getcwd())
        spinner.ok("✔")


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


def check_prolific_payment(experiment, config):
    cents = config.get("prolific_reward_cents")
    minutes = config.get("prolific_estimated_completion_minutes")
    assert (
        experiment.var.wage_per_hour * minutes / 60 == cents / 100
    ), "Wage per hour does not match Prolific reward"


def run_pre_checks(mode, local_, heroku=False, docker=False, app=None):
    from dallinger.recruiters import MTurkRecruiter

    from .asset import DebugStorage
    from .experiment import get_experiment

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
        # Running these following tests in advance of local deployment is skipped because it confuses SQLAlchemy
        # to import the experiment in advance of the experiment launch itself, you get errors like this:
        # sqlalchemy.exc.InvalidRequestError: Table 'coin' is already defined for this MetaData instance.
        # Specify 'extend_existing=True' to redefine options and columns on an existing Table object.
        init_db(drop_all=True)

        config = get_config()
        if not config.ready:
            config.load()

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

        exp = get_experiment()

        config.set("id", exp.make_uuid(app))

        recruiter = exp.recruiter
        is_mturk = isinstance(recruiter, MTurkRecruiter)
        is_prolific = isinstance(recruiter, ProlificRecruiter)

        if mode in ["sandbox", "deploy"]:
            if isinstance(exp.asset_storage, DebugStorage):
                raise AttributeError(
                    "You can't deploy an experiment to a remote server with Experiment.asset_storage = DebugStorage(). "
                    "If you don't need assets in your experiment, you can probably remove the line altogether, "
                    "or replace DebugStorage with NoStorage. If you do need assets, you should replace DebugStorage "
                    "with a proper storage backend, for example S3Storage('your-bucket', 'your-root')."
                )
            if is_prolific:
                check_prolific_payment(exp, config)

        if mode == "sandbox":
            run_pre_checks_sandbox(exp, config, is_mturk)
        elif mode == "deploy":
            run_pre_checks_deploy(exp, config, is_mturk)


def run_pre_checks_sandbox(exp, config, is_mturk):
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
@click.option("--app", default=None, help="Name of the experiment app.")
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
            result = ctx.invoke(
                dallinger_sandbox, verbose=True, app=app, archive=archive
            )
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
@click.option("--app", required=True, help="Name of the experiment app.")
@click.option("--archive", default=None, help="Optional path to an experiment archive.")
@server_option
# @click.option("--server", default=None, help="Name of the remote server.")
# @click.option(
#     "--skip-flask",
#     is_flag=True,
#     help="Skip launching Flask, so that Flask can be managed externally. Does not apply when legacy=True",
# )
@click.pass_context
def debug__docker_ssh(ctx, app, archive, server):
    """
    Debug the experiment on a remote server via SSH.
    """
    try:
        from dallinger.command_line.docker_ssh import deploy

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

        result = ctx.invoke(
            deploy,
            mode="sandbox",
            server=server,
            app_name=app,
            config_options={},
            archive_path=archive,
        )

        _post_deploy(result)
    finally:
        _cleanup_exp_directory()


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
    from .experiment import import_local_experiment

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
    ]
    for arg in args:
        func = arg(func)
    return func


# @psynet.command()
# @click.option(
#     "--app",
#     default=None,
#     required=False,
#     help="App id",
# )
# @click.option("--local", is_flag=True, help="Export local data")
# @click.option("--path", default=None, help="Path to export directory")
# @click.option(
#     "--assets",
#     default="experiment",
#     help="Which assets to export; valid values are none, experiment, and all",
# )
# @click.option(
#     "--anonymize",
#     default="both",
#     help="Whether to anonymize the data; valid values are yes, no, or both (the latter exports both ways)",
# )
# @click.option(
#     "--n_parallel", default=None, help="Number of parallel jobs for exporting assets"
# )


@psynet.group("export")
def export():
    pass


@export.command("local")
@export_arguments
@click.pass_context
def export__local(ctx=None, **kwargs):
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
    exp_variables = ctx.invoke(experiment_variables, location="heroku", app=app)
    export_(ctx, app=app, local=False, exp_variables=exp_variables, **kwargs)


@export.command("ssh")
@click.option(
    "--app",
    required=True,
    help="Name of the app to export",
)
@server_option
@export_arguments
@click.pass_context
def export__docker_ssh(ctx, app, server, **kwargs):
    exp_variables = ctx.invoke(experiment_variables, location="ssh", app=app)
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
    assets="experiment",
    anonymize="both",
    n_parallel=None,
    docker_ssh=False,
    server=None,
    dns_host=None,
):
    """
    Export data from an experiment.

    The data is exported in three distinct formats into the 'data/data-<app>'
    directory of an experiment which has following structure:

    ::

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
    from .experiment import import_local_experiment

    log(header)

    deployment_id = exp_variables["deployment_id"]
    assert len(deployment_id) > 0

    remote_exp_label = exp_variables["label"]
    local_exp_label = import_local_experiment()["class"].label

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
        # export_root = get_from_config("default_export_root")
        export_root = "~/psynet-data/export"

        path = os.path.join(
            export_root,
            deployment_id,
            re.sub(
                "__launch.*", "", deployment_id
            )  # Strip the launch date from the path to keep things short
            + "__export="
            + datetime.now().strftime("%Y-%m-%d--%H-%M-%S"),
        )

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

    for anonymize_mode in anonymize_modes:
        _anonymize = anonymize_mode == "yes"
        _export_(
            ctx,
            app,
            local,
            path,
            assets,
            _anonymize,
            n_parallel,
            docker_ssh,
            server,
            dns_host,
        )


def _export_(
    ctx,
    app,
    local,
    export_path,
    assets,
    anonymize: bool,
    n_parallel=None,
    docker_ssh=False,
    server=None,
    dns_host=None,
):
    """
    An internal version of the export version where argument preprocessing has been done already.
    """
    database_zip_path = export_database(
        ctx, app, local, export_path, anonymize, docker_ssh, server, dns_host
    )

    # We originally thought code should be exported here. However it makes better sense to
    # export instead as part of psynet sandbox/deploy. We'll implement this soon.
    # export_code(export_path, anonymize)

    export_data(local, anonymize, database_zip_path, export_path)

    if assets != "none":
        experiment_assets_only = assets == "experiment"
        include_fast_function_assets = assets == "all"
        export_assets(
            export_path,
            anonymize,
            experiment_assets_only,
            include_fast_function_assets,
            n_parallel,
            server,
        )

    log(f"Export complete. You can find your results at: {export_path}")


def export_database(
    ctx, app, local, export_path, anonymize, docker_ssh, server, dns_host
):
    if local:
        app = "local"

    subdir = "anonymous" if anonymize else "regular"

    database_zip_path = os.path.join(export_path, subdir, "database.zip")

    log(f"Exporting raw database content to {database_zip_path}...")

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


# def export_code(export_path, anonymize):
#     subdir = "anonymous" if anonymize else "regular"
#
#     code_zip_path = os.path.join(export_path, subdir, "code.zip")
#
#     log(f"Exporting code to {code_zip_path}.")
#
#     with tempfile.TemporaryDirectory() as tempdir:
#         temp_exp_dir = make_parents(os.path.join(tempdir, "experiment"))
#         shutil.copytree(os.path.join(os.getcwd()), os.path.join(temp_exp_dir), dirs_exist_ok=True, ignore_dangling_symlinks=True, ignore=lambda src, names: names if src == "develop" else [])
#         shutil.rmtree(os.path.join(temp_exp_dir, ".git"), ignore_errors=True)
#         shutil.make_archive(
#             code_zip_path,
#             "zip",
#             temp_exp_dir,
#         )
#
#     with yaspin(text="Completed.", color="green") as spinner:
#         spinner.ok("✔")


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
    include_fast_function_assets,
    n_parallel,
    server,
):
    # Assumes we already have loaded the experiment into the local database,
    # as would be the case if the function is called from psynet export.
    from .data import export_assets as _export_assets

    log(f"Exporting assets to {export_path}...")

    include_private = not anonymize
    subdir = "anonymous" if anonymize else "regular"
    asset_path = os.path.join(export_path, subdir, "assets")

    _export_assets(
        asset_path,
        include_private,
        experiment_assets_only,
        include_fast_function_assets,
        n_parallel,
        server,
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
def load(path):
    "Populates the local database with a provided zip file."
    from .experiment import import_local_experiment

    import_local_experiment()
    populate_db_from_zip_file(path)


# Example usage: psynet generate-config --debug_storage_root ~/debug_storage
@psynet.command(
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.pass_context
def generate_config(ctx):
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

    click.echo("...updating .gitignore.")
    shutil.copyfile(
        resource_filename("psynet", "resources/experiment_scripts/.gitignore"),
        ".gitignore",
    )

    click.echo("...updating Dockerfile.")
    shutil.copyfile(
        resource_filename("psynet", "resources/experiment_scripts/Dockerfile"),
        "Dockerfile",
    )

    click.echo("...updating Dockertag.")
    with open("Dockertag", "w") as file:
        file.write(os.path.basename(os.getcwd()))
        file.write("\n")

    click.echo("...updating test.py and pytest.ini.")
    shutil.copyfile(
        resource_filename("psynet", "resources/experiment_scripts/test.py"),
        "test.py",
    )
    shutil.copyfile(
        resource_filename("psynet", "resources/experiment_scripts/pytest.ini"),
        "pytest.ini",
    )

    click.echo("...updating docs directory.")
    if Path("docs").exists():
        shutil.rmtree("docs", ignore_errors=True)
    shutil.copytree(
        resource_filename("psynet", "resources/experiment_scripts/docs"),
        "docs",
        dirs_exist_ok=True,
    )

    click.echo("...updating Docker scripts.")
    shutil.rmtree("docker", ignore_errors=True)
    shutil.copytree(
        resource_filename("psynet", "resources/experiment_scripts/docker"),
        "docker",
        dirs_exist_ok=True,
    )
    os.system("chmod +x docker/*")

    click.echo("...updating README.md.")
    shutil.copyfile(
        resource_filename("psynet", "resources/experiment_scripts/README.md"),
        "README.md",
    )


@psynet.group("destroy")
def destroy():
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
):
    if user_confirms(
        "Would you like to delete the app from the web server?", default=True
    ):
        with yaspin("Destroying app...") as spinner:
            try:
                if expire_hit in get_args(f_destroy):
                    ctx.invoke(
                        f_destroy,
                        app=app,
                        expire_hit=False,
                    )
                else:
                    ctx.invoke(
                        f_destroy,
                        app=app,
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
@click.option(
    "--expire-hit/--no-expire-hit",
    flag_value=True,
    default=None,
    help="Expire any MTurk HITs associated with this experiment.",
)
@click.pass_context
def destroy__docker_ssh(ctx, app, expire_hit):
    from dallinger.command_line import expire
    from dallinger.command_line.docker_ssh import destroy

    _destroy(
        ctx,
        destroy,
        expire,
        app=app,
        expire_hit=expire_hit,
    )


# @local.command("experiment-mode")
# @click.option("--app", required=True, help="Name of the experiment app")
# @click.pass_context
# def experiment_mode__local(ctx, app):
#     try:
#         mode = ctx.invoke(experiment_variables__local, app=app,)[
#             "deployment_config"
#         ]["mode"]
#     except Exception:
#         click.echo(
#             "Failed to communicate with the running experiment to determine the deployment mode. "
#         )
#         raise
#     click.echo(f"Experiment mode: {mode}")
#     return mode
#
#
# @heroku.command("experiment-mode")
# @click.option("--app", required=True, help="Name of the experiment app")
# @click.pass_context
# def experiment_mode__heroku(ctx, app):
#     try:
#         mode = ctx.invoke(experiment_variables__heroku, app=app,)[
#             "deployment_config"
#         ]["mode"]
#     except Exception:
#         click.echo(
#             "Failed to communicate with the running experiment to determine the deployment mode. "
#         )
#         raise
#     click.echo(f"Experiment mode: {mode}")
#     return mode
#
#
# @docker_heroku.command("experiment-mode")
# @click.option("--app", required=True, help="Name of the experiment app")
# @click.pass_context
# def experiment_mode__docker_heroku(ctx, app):
#     try:
#         mode = ctx.invoke(experiment_variables__docker_heroku, app=app,)[
#             "deployment_config"
#         ]["mode"]
#     except Exception:
#         click.echo(
#             "Failed to communicate with the running experiment to determine the deployment mode. "
#         )
#         raise
#     click.echo(f"Experiment mode: {mode}")
#     return mode
#
#
# @heroku.command("experiment-mode")
# @click.option("--app", required=True, help="Name of the experiment app")
# @click.pass_context
# def experiment_mode__docker_ssh(ctx, app):
#     try:
#         mode = ctx.invoke(experiment_variables__docker_ssh, app=app,)[
#             "deployment_config"
#         ]["mode"]
#     except Exception:
#         click.echo(
#             "Failed to communicate with the running experiment to determine the deployment mode. "
#         )
#         raise
#     click.echo(f"Experiment mode: {mode}")
#     return mode


@psynet.group("apps")
def apps():
    pass


@apps.command("ssh")
@server_option
@click.pass_context
def apps__docker_ssh(ctx, server):
    from dallinger.command_line.docker_ssh import apps

    _apps = ctx.invoke(apps, server=server)
    if len(_apps) == 0:
        click.echo("No apps found.")


@psynet.group("stats")
def stats():
    pass


@stats.command("ssh")
@server_option
@click.pass_context
def stats__docker_ssh(ctx, server):
    from dallinger.command_line.docker_ssh import stats

    ctx.invoke(stats, server=server)


def verify_id(ctx, param, app):
    return app


# The original Dallinger verify_id function forces app names to begin with dlgr-,
# which is not appropriate for us
dallinger.command_line.utils.verify_id = verify_id
