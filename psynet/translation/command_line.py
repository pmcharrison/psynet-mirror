import os

import click
from dallinger.config import experiment_available

from psynet.command_line import psynet as psynet_cli
from psynet.translation.translation import translate_experiment, translate_package
from psynet.utils import get_package_name, in_python_package


@psynet_cli.group("translation")
def translation():
    pass

    """Translation management commands."""


def parse_list(value):
    return value.replace(",", " ").split()


options = {
    # "experiment": click.option(
    #     "--experiment",
    #     help="Whether to translate the experiment directory",
    #     default=False,
    #     is_flag=True,
    # ),
    "languages": click.option(
        "--languages",
        help="The target languages, specified as a space or comma-separated list of language codes",
        type=parse_list,
    ),
    # "packages": click.option(
    #     "--packages",
    #     help="The target packages, specified as a space or comma-separated list of package names",
    #     default="",
    #     type=parse_list,
    # ),
}


@translation.command("generate")
@options["languages"]
def generate(languages):
    """
    Inspects the code in the current directory and generates automatic translations for a given set of languages.

    This command should be run from the root of either an experiment or a package.
    If run from an experiment, the translations will be saved in the experiment's "locales" directory.
    If run from a package, the translations will be saved in "{package_src_directory}/locales".

    Note: Currently only .py and .html files are translated.

    Parameters
    ----------
    languages :
        The target languages, specified as a space or comma-separated list of language codes

    Example
    -------

    psynet translation generate --languages fr,de
        Generate translations for French and German.
    """
    if experiment_available():
        click.echo("Translating experiment to {', '.join(languages)}...")
        translate_experiment(languages)

    elif in_python_package():
        click.echo(
            f"Translating {get_package_name()} package to {', '.join(languages)}..."
        )
        translate_package(languages)
    else:
        raise RuntimeError(
            f"The current directory {os.getcwd()} does not seem to be the root of an experiment or a package."
        )


@translation.command("export")
@options["packages"]
@options["languages"]
def export(packages, languages):
    """
    Exports package translations back to the original packages.
    The packages need to be installed in editable mode.

    Examples
    --------

    psynet translation export --packages psynet --languages fr
        Export French translations back to the PsyNet package.
    """
    for package in packages:
        click.echo(
            f"Exporting {', '.join(languages)} translations to the {package} package ..."
        )
        export_package(package, languages)


@translation.command("import")
@options["packages"]
@options["languages"]
def import_(packages, languages):
    """
    Imports translations from the specified packages into the current experiment directory.
    This command is useful if you want to use the packages' original translations as a starting point,
    but then modify them yourself.

    Examples
    --------

    psynet translation import --packages psynet --languages fr
        Import French translations from the PsyNet package.
    """
    for package in packages:
        click.echo(
            f"Importing {', '.join(languages)} translations from the {package} package ..."
        )
        import_package(package, languages)


@translation.command("check")
def check():
    """Check translation files for issues."""
    pass


def export_package(package, languages):
    pass


def import_package(package, languages):
    pass
